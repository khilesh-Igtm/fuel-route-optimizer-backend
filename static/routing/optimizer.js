(function () {
    "use strict";

    const config = window.FUEL_OPTIMIZER_CONFIG || {};

    const API_ENDPOINT =
        config.apiEndpoint || "/api/v1/route/optimize/";

    const form = document.getElementById("route-form");
    const optimizeButton = document.getElementById("optimize-button");
    const buttonText = document.getElementById("button-text");
    const buttonLoader = document.getElementById("button-loader");
    const errorMessage = document.getElementById("error-message");
    const resultsSection = document.getElementById("results-section");

    let map = null;
    let routeLayer = null;
    let markerLayer = null;

    const elements = {
        distance: document.getElementById("total-distance"),
        duration: document.getElementById("total-duration"),
        stops: document.getElementById("total-stops"),
        cost: document.getElementById("total-cost"),
        stations: document.getElementById("stations-list"),
        dataQuality: document.getElementById("data-quality"),
    };

    function getNestedValue(object, path, fallback = null) {
        return path.split(".").reduce((current, key) => {
            return current && current[key] !== undefined
                ? current[key]
                : null;
        }, object) ?? fallback;
    }

    function formatNumber(value, digits = 2) {
        const number = Number(value);

        if (!Number.isFinite(number)) {
            return "--";
        }

        return number.toLocaleString("en-US", {
            minimumFractionDigits: 0,
            maximumFractionDigits: digits,
        });
    }

    function formatCurrency(value) {
        const number = Number(value);

        if (!Number.isFinite(number)) {
            return "--";
        }

        return new Intl.NumberFormat("en-US", {
            style: "currency",
            currency: "USD",
        }).format(number);
    }

    function escapeHTML(value) {
        return String(value ?? "").replace(/[&<>"']/g, (character) => {
            const entities = {
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#039;",
            };

            return entities[character];
        });
    }

    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.classList.remove("hidden");
    }

    function hideError() {
        errorMessage.textContent = "";
        errorMessage.classList.add("hidden");
    }

    function setLoading(isLoading) {
        optimizeButton.disabled = isLoading;

        buttonLoader.classList.toggle("hidden", !isLoading);

        buttonText.textContent = isLoading
            ? "Optimizing Route..."
            : "Optimize My Route";
    }

    function getCoordinates(point) {
        if (!point) {
            return null;
        }

        const latitude = Number(
            point.latitude ?? point.lat
        );

        const longitude = Number(
            point.longitude ?? point.lon ?? point.lng
        );

        if (
            !Number.isFinite(latitude) ||
            !Number.isFinite(longitude) ||
            latitude < -90 ||
            latitude > 90 ||
            longitude < -180 ||
            longitude > 180
        ) {
            return null;
        }

        return [latitude, longitude];
    }

    function initializeMap() {
        if (map) {
            return;
        }

        map = L.map("route-map", {
            scrollWheelZoom: true,
        });

        L.tileLayer(
            "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            {
                maxZoom: 19,
                attribution:
                    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            }
        ).addTo(map);

        map.setView([39.5, -98.35], 4);

        routeLayer = L.layerGroup().addTo(map);
        markerLayer = L.layerGroup().addTo(map);
    }

    function createIcon(color) {
        return L.divIcon({
            className: "",
            html: `
                <div style="
                    background:${color};
                    width:17px;
                    height:17px;
                    border:3px solid white;
                    border-radius:50%;
                    box-shadow:0 2px 7px rgba(0,0,0,0.4);
                "></div>
            `,
            iconSize: [17, 17],
            iconAnchor: [8, 8],
        });
    }

    function addMarker(coordinates, title, description, color) {
        if (!coordinates) {
            return;
        }

        L.marker(coordinates, {
            icon: createIcon(color),
        })
            .bindPopup(`
                <strong>${escapeHTML(title)}</strong>
                <br>
                ${escapeHTML(description)}
            `)
            .addTo(markerLayer);
    }

    function normalizeGeometry(geometry) {
        if (
            !geometry ||
            geometry.type !== "LineString" ||
            !Array.isArray(geometry.coordinates)
        ) {
            return [];
        }

        return geometry.coordinates
            .map((coordinate) => {
                if (!Array.isArray(coordinate) || coordinate.length < 2) {
                    return null;
                }

                const longitude = Number(coordinate[0]);
                const latitude = Number(coordinate[1]);

                if (
                    !Number.isFinite(latitude) ||
                    !Number.isFinite(longitude) ||
                    latitude < -90 ||
                    latitude > 90 ||
                    longitude < -180 ||
                    longitude > 180
                ) {
                    return null;
                }

                return [latitude, longitude];
            })
            .filter(Boolean);
    }

    function drawRoute(response) {
        initializeMap();

        routeLayer.clearLayers();
        markerLayer.clearLayers();

        const route = response.route || {};

        const coordinates = normalizeGeometry(route.geometry);

        if (coordinates.length < 2) {
            throw new Error(
                "Route geometry is missing or invalid in the API response."
            );
        }

        const polyline = L.polyline(coordinates, {
            color: "#1976d2",
            weight: 5,
            opacity: 0.85,
            lineJoin: "round",
        });

        polyline.addTo(routeLayer);

        const start = getCoordinates(route.start);
        const destination = getCoordinates(route.destination);

        addMarker(
            start || coordinates[0],
            "Starting Location",
            route.start?.address || "Journey begins here",
            "#16a36c"
        );

        addMarker(
            destination || coordinates[coordinates.length - 1],
            "Destination",
            route.destination?.address || "Journey ends here",
            "#dc4646"
        );

        const stops = response.fuel_optimization?.stops || [];

        stops.forEach((station, index) => {
            const stationCoordinates = getCoordinates(station);

            if (!stationCoordinates) {
                return;
            }

            const name = station.name || station.station_name ||
                `Fuel Station ${index + 1}`;

            const address = [
                station.address,
                station.city,
                station.state,
            ].filter(Boolean).join(", ");

            const price = station.fuel_price_per_gallon != null
                    ? `Fuel price: ${formatCurrency(station.fuel_price_per_gallon)} / gallon`
                    : "Fuel price unavailable";

            const detour = station.detour_distance_miles != null
                ? `Detour: ${formatNumber(station.detour_distance_miles)} miles`
                : "";

            const description = [address, price, detour]
                .filter(Boolean)
                .join(" | ");

            addMarker(
                stationCoordinates,
                `Fuel Stop ${index + 1}: ${name}`,
                description,
                "#f0a328"
            );
        });

        map.fitBounds(polyline.getBounds(), {
            padding: [35, 35],
            maxZoom: 8,
        });
    }

    function updateSummary(response) {
        const route = response.route || {};
        const optimization = response.fuel_optimization || {};
        const costSummary = response.cost_summary || {};

        const distance = route.distance_miles;

        const duration = route.duration_minutes;

        const numberOfStops =
            optimization.number_of_stops ??
            optimization.stops?.length ??
            0;

        const totalCost =
            costSummary.estimated_total_fuel_cost ??
            costSummary.total_fuel_cost ??
            optimization.estimated_total_fuel_cost;

        elements.distance.textContent =
            formatNumber(distance);

        if (Number.isFinite(Number(duration))) {
            const hours = Math.floor(Number(duration) / 60);
            const minutes = Math.round(Number(duration) % 60);

            elements.duration.textContent =
                `${hours}h ${minutes}m`;
        } else {
            elements.duration.textContent = "--";
        }

        elements.stops.textContent = numberOfStops;

        elements.cost.textContent =
            formatCurrency(totalCost);
    }

    function renderStations(response) {
        const stops = response.fuel_optimization?.stops || [];

        elements.stations.replaceChildren();

        if (!stops.length) {
            elements.stations.textContent =
                "No optimized fuel stops were returned for this journey.";

            return;
        }

        stops.forEach((station, index) => {
            const card = document.createElement("article");

            card.className = "station-card";

            const name = station.name ||
                station.station_name ||
                `Fuel Station ${index + 1}`;

            const address = [
                station.address,
                station.city,
                station.state,
            ].filter(Boolean).join(", ");

            const price = station.fuel_price_per_gallon != null
                    ? formatCurrency(station.fuel_price_per_gallon)
                    : "Unavailable";

            const distance = station.distance_from_start_miles != null
                ? `${formatNumber(station.distance_from_start_miles)} miles from start`
                : "";

            const detour = station.detour_distance_miles != null
                ? `${formatNumber(station.detour_distance_miles)} miles detour`
                : "";

            const information = document.createElement("div");
            information.className = "station-info";

            const heading = document.createElement("h3");
            heading.textContent = `${index + 1}. ${name}`;

            const location = document.createElement("p");
            location.textContent = address || "Location unavailable";

            information.append(heading, location);

            [distance, detour].filter(Boolean).forEach((text) => {
                const detail = document.createElement("p");
                detail.textContent = text;
                information.appendChild(detail);
            });

            if (station.coordinates_are_approximate) {
                const warning = document.createElement("p");
                warning.textContent =
                    "Station coordinates are approximate.";
                information.appendChild(warning);
            }

            const priceContainer = document.createElement("div");
            priceContainer.className = "station-price";

            const priceValue = document.createElement("span");
            priceValue.textContent = price;

            const priceLabel = document.createElement("small");
            priceLabel.textContent = "Retail fuel price";

            priceContainer.append(priceValue, priceLabel);

            card.append(information, priceContainer);

            elements.stations.appendChild(card);
        });
    }

    function renderDataQuality(response) {
        const quality = response.data_quality || {};

        const matching = response.station_matching || {};

        const messages = [];

        if (quality.warnings?.length) {
            messages.push(...quality.warnings);
        }

        if (matching.message) {
            messages.push(matching.message);
        }

        elements.dataQuality.textContent = messages.length
            ? `Data quality: ${messages.join(" | ")}`
            : "Route and fuel station data processed successfully.";
    }

    async function optimizeRoute(event) {
        event.preventDefault();

        hideError();

        const startLocation =
            document.getElementById("start-location").value.trim();

        const endLocation =
            document.getElementById("end-location").value.trim();

        const corridorWidth = Number(
            document.getElementById("corridor-width").value
        );

        const maxStations = Number(
            document.getElementById("max-stations").value
        );

        if (!startLocation || !endLocation) {
            showError("Please enter both starting and destination locations.");
            return;
        }

        if (
            !Number.isFinite(corridorWidth) ||
            corridorWidth < 1 ||
            corridorWidth > 100
        ) {
            showError("Corridor width must be between 1 and 100 miles.");
            return;
        }

        if (
            !Number.isInteger(maxStations) ||
            maxStations < 1 ||
            maxStations > 500
        ) {
            showError("Maximum stations must be between 1 and 500.");
            return;
        }

        setLoading(true);

        try {
            const response = await fetch(API_ENDPOINT, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                body: JSON.stringify({
                    start_location: startLocation,
                    end_location: endLocation,
                    corridor_width_miles: corridorWidth,
                    max_stations: maxStations,
                }),
            });

            const data = await response.json();

            if (!response.ok) {
                const message =
                    data.detail ||
                    data.error ||
                    data.message ||
                    `Request failed with status ${response.status}.`;

                throw new Error(message);
            }

            if (!data.route || !data.fuel_optimization) {
                throw new Error(
                    "The API returned an incomplete optimization response."
                );
            }

            drawRoute(data);
            updateSummary(data);
            renderStations(data);
            renderDataQuality(data);

            resultsSection.classList.remove("hidden");

            requestAnimationFrame(() => {
                if (map) {
                    map.invalidateSize();
                }
            });

            resultsSection.scrollIntoView({
                behavior: "smooth",
                block: "start",
            });

        } catch (error) {
            console.error("Route optimization error:", error);

            showError(
                error.message ||
                "Unable to optimize your route. Please try again."
            );

        } finally {
            setLoading(false);
        }
    }

    form.addEventListener("submit", optimizeRoute);

})();