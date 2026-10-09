"use strict";

/* -------------------- CONFIGURATION -------------------- */

// When opened locally via file://, defaults to localhost:8000.
// When hosted on the web, automatically uses the same server origin.
const API_URL = (window.location.protocol === "file:")
    ? "http://127.0.0.1:8000"
    : window.location.origin;

const cityForm = document.getElementById("cityForm");
const cityInput = document.getElementById("cityInput");
const analyzeBtn = document.getElementById("analyzeBtn");
const statusText = document.getElementById("status");

const emptyState = document.getElementById("emptyState");
const dashboard = document.getElementById("dashboard");

const gridPanel = document.getElementById("detailedGridPanel");
const gridButton = document.getElementById("viewDetailedGrid");
const closeGridButton = document.getElementById("closeDetailedGrid");
const gridInfo = document.getElementById("selectedCellInfo");

let currentAnalysis = null;
let currentZone = null;

let gridMap = null;
let gridLayer = null;
let selectedRectangle = null;

/* -------------------- CITY ANALYSIS -------------------- */

cityForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const city = cityInput.value.trim();

    if (!city) {
        statusText.textContent = "Please enter a city name.";
        return;
    }

    analyzeBtn.disabled = true;
    analyzeBtn.textContent = "Analyzing...";
    statusText.textContent = "Analyzing city data...";

    try {
        const response = await fetch(API_URL + "/analyze-city", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ city: city })
        });

        if (!response.ok) {
            throw new Error("Backend returned HTTP " + response.status);
        }

        const data = await response.json();

        if (data.status === "error") {
            throw new Error(data.message || "Analysis failed.");
        }

        currentAnalysis = data;
        showDashboard(data);

    } catch (error) {
        console.error("City analysis failed:", error);

        statusText.textContent =
            error.message + ". Check that your backend is running.";

    } finally {
        analyzeBtn.disabled = false;
        analyzeBtn.textContent = "Analyze City";
    }
});

/* -------------------- DASHBOARD -------------------- */

function showDashboard(data) {
    emptyState.classList.add("hidden");
    dashboard.classList.remove("hidden");

    setText("cityName", data.city || "Unknown City");
    setText("analysisStatus", "Analysis completed");
    statusText.textContent = "City analysis completed.";

    setText("avgLST", formatValue(data.avg_lst, "°C"));
    setText("avgNDVI", formatValue(data.avg_ndvi));
    setText("highPriority", formatInteger(data.high_priority_zones));
    setText("priorityIndex", formatValue(data.priority_index));

    setText("factorHeat", formatValue(data.avg_lst, "°C"));
    setText("factorNDVI", formatValue(data.avg_ndvi));
    setText("factorBuilt", formatValue(data.built_up));

    setText(
        "factorRoad",
        data.zone && data.zone.road_density != null
            ? formatValue(data.zone.road_density)
            : "OSM unavailable"
    );

    const zones = Array.isArray(data.high_priority_zone_list)
        ? data.high_priority_zone_list
        : [];

    renderPriorityZones(zones);

    if (data.zone) {
        selectZone(data.zone, false);
    } else if (zones.length > 0) {
        selectZone(zones[0], false);
    } else {
        clearZone();
    }

    dashboard.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}

/* -------------------- ZONE SELECTION -------------------- */

function selectZone(zone, openGrid) {
    if (!zone) {
        return;
    }

    if (openGrid === undefined) {
        openGrid = true;
    }

    currentZone = zone;

    setText("zoneTitle", zone.zone_id || "Priority Zone");
    setText("zoneLocation", zone.location || "Location unavailable");
    setText("zoneLocality", zone.locality || "Locality unavailable");

    const lat = Number(zone.latitude);
    const lon = Number(zone.longitude);

    const validCoordinates =
        Number.isFinite(lat) &&
        Number.isFinite(lon) &&
        Math.abs(lat) <= 90 &&
        Math.abs(lon) <= 180;

    setText(
        "zoneCoordinates",
        validCoordinates
            ? lat.toFixed(6) + "°, " + lon.toFixed(6) + "°"
            : "--"
    );

    setText("zoneGridSize", zone.grid_size || "500m × 500m");
    setText("zoneLST", formatValue(zone.lst, "°C"));
    setText("zoneNDVI", formatValue(zone.ndvi));
    setText("zoneBuilt", formatValue(zone.built_up));

    setText(
        "zoneRoad",
        zone.road_density != null
            ? formatValue(zone.road_density)
            : "OSM unavailable"
    );

    setText("zoneScore", formatValue(zone.priority_score));

    setText(
        "recommendation",
        zone.recommendation || "No recommendation available."
    );

    const badge = document.getElementById("priorityBadge");
    const priority = zone.priority || "Unknown";

    badge.textContent = priority;
    badge.style.background = priorityBackground(priority);
    badge.style.color = priorityColor(priority);

    loadSatelliteImage(zone.satellite_url);

    if (openGrid) {
        openDetailedGrid();
    } else if (gridPanel && !gridPanel.classList.contains("hidden")) {
        drawGrid(zone);
    }
}

/* -------------------- PRIORITY ZONE CARDS -------------------- */

function renderPriorityZones(zones) {
    const container = document.getElementById("priorityZonesList");

    container.replaceChildren();

    if (zones.length === 0) {
        const message = document.createElement("div");

        message.className = "empty-zone-message";
        message.textContent =
            "No high-priority zones were returned by the backend.";

        container.appendChild(message);
        return;
    }

    zones.forEach(function (zone, index) {
        const card = document.createElement("button");

        card.type = "button";
        card.className = "priority-zone-item";

        const rank = document.createElement("div");
        rank.className = "priority-zone-rank";
        rank.textContent = String(index + 1);

        const info = document.createElement("div");
        info.className = "priority-zone-info";

        const name = document.createElement("strong");
        name.textContent = zone.zone_id || "Priority Zone " + (index + 1);

        const coordinates = document.createElement("span");

        const lat = Number(zone.latitude);
        const lon = Number(zone.longitude);

        const validCoordinates =
            Number.isFinite(lat) &&
            Number.isFinite(lon) &&
            Math.abs(lat) <= 90 &&
            Math.abs(lon) <= 180;

        coordinates.textContent = validCoordinates
            ? lat.toFixed(5) + "°, " + lon.toFixed(5) + "°"
            : "Coordinates unavailable";

        const description = document.createElement("small");
        description.textContent = "Click to select and open grid";

        info.append(name, coordinates, description);

        const scoreInfo = document.createElement("div");
        scoreInfo.className = "priority-zone-score";

        const score = document.createElement("strong");
        score.textContent = formatValue(zone.priority_score);

        const priority = document.createElement("span");
        priority.textContent = zone.priority || "HIGH";

        scoreInfo.append(score, priority);
        card.append(rank, info, scoreInfo);

        card.addEventListener("click", function () {
            selectZone(zone, true);

            document.getElementById("zoneTitle").scrollIntoView({
                behavior: "smooth",
                block: "center"
            });
        });

        container.appendChild(card);
    });
}

/* -------------------- GRID OPEN / CLOSE -------------------- */

gridButton.addEventListener("click", openDetailedGrid);

closeGridButton.addEventListener("click", function () {
    gridPanel.classList.add("hidden");
});

function openDetailedGrid() {
    if (!currentZone) {
        alert("Analyze a city and select a priority zone first.");
        return;
    }

    gridPanel.classList.remove("hidden");

    if (typeof L === "undefined") {
        gridInfo.textContent =
            "Leaflet could not load. Check your internet connection.";
        return;
    }

    drawGrid(currentZone);

    requestAnimationFrame(function () {
        if (gridMap) {
            gridMap.invalidateSize();
        }
    });
}

/* -------------------- MAP INITIALIZATION -------------------- */

function initializeGridMap(lat, lon) {
    if (gridMap) {
        return;
    }

    gridMap = L.map("detailedGridMap");

    L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    {
        maxZoom: 19,
        attribution: "Tiles &copy; Esri"
    }
).addTo(gridMap);

    gridLayer = L.layerGroup().addTo(gridMap);

    gridMap.setView([lat, lon], 18);
}

/* -------------------- DRAW DETAILED GRID -------------------- */

function drawGrid(zone) {
    const lat = Number(zone.latitude);
    const lon = Number(zone.longitude);

    const validCoordinates =
        Number.isFinite(lat) &&
        Number.isFinite(lon) &&
        Math.abs(lat) <= 90 &&
        Math.abs(lon) <= 180;

    if (!validCoordinates) {
        gridInfo.textContent =
            "The selected zone does not contain valid coordinates.";
        return;
    }

    if (typeof L === "undefined") {
        gridInfo.textContent = "Leaflet map library is not available.";
        return;
    }

    initializeGridMap(lat, lon);

    gridLayer.clearLayers();
    selectedRectangle = null;

    gridMap.setView([lat, lon], 18);

    /*
     * Display 25 approximate cells.
     * Each cell is approximately 100m x 100m.
     * These are visual cells, not individual satellite analyses.
     */

    const metresPerDegreeLat = 111320;

    const metresPerDegreeLon =
        111320 * Math.cos(lat * Math.PI / 180);

    if (Math.abs(metresPerDegreeLon) < 0.01) {
        gridInfo.textContent = "Unable to calculate grid at this latitude.";
        return;
    }

    const dLat = 100 / metresPerDegreeLat;
    const dLon = 100 / metresPerDegreeLon;

    const firstLat = lat - 2.5 * dLat;
    const firstLon = lon - 2.5 * dLon;

    const normalStyle = {
        color: "#176b45",
        weight: 1.5,
        fillColor: "#65b985",
        fillOpacity: 0.25
    };

    const selectedStyle = {
        color: "#e67e22",
        weight: 3,
        fillColor: "#f5b041",
        fillOpacity: 0.5
    };

    for (let row = 0; row < 5; row++) {
        for (let col = 0; col < 5; col++) {
            const south = firstLat + row * dLat;
            const north = south + dLat;
            const west = firstLon + col * dLon;
            const east = west + dLon;

            const cellName = "R" + (row + 1) + "-C" + (col + 1);

            const rectangle = L.rectangle(
                [[south, west], [north, east]],
                normalStyle
            );

            rectangle.bindTooltip(cellName);

            rectangle.on("click", function () {
                if (selectedRectangle) {
                    selectedRectangle.setStyle(normalStyle);
                }

                selectedRectangle = rectangle;
                rectangle.setStyle(selectedStyle);

                const centerLat = (south + north) / 2;
                const centerLon = (west + east) / 2;

                gridInfo.textContent =
                    cellName + " selected | Approx. 100m × 100m | " +
                    "Center: " + centerLat.toFixed(6) + ", " +
                    centerLon.toFixed(6) + " | " +
                    "Southwest: " + south.toFixed(6) + ", " +
                    west.toFixed(6) + " | " +
                    "Northeast: " + north.toFixed(6) + ", " +
                    east.toFixed(6);
            });

            rectangle.addTo(gridLayer);
        }
    }

    setText(
        "gridMapTitle",
        (zone.zone_id || "Priority Zone") + " — Detailed Grid"
    );

    gridInfo.textContent =
        "25 approximate cells displayed. Click any cell to inspect its coordinates.";

    gridMap.invalidateSize();
}

/* -------------------- SATELLITE IMAGE -------------------- */

function loadSatelliteImage(url) {
    const image = document.getElementById("zoneSatellite");
    const placeholder = document.getElementById("satellitePlaceholder");

    image.style.display = "none";
    image.removeAttribute("src");
    placeholder.style.display = "flex";

    if (!url) {
        placeholder.textContent =
            "Satellite image unavailable: no image URL was provided by the backend.";
        return;
    }

    placeholder.textContent = "Loading satellite image...";

    image.onload = function () {
        image.style.display = "block";
        placeholder.style.display = "none";
    };

    image.onerror = function () {
        image.style.display = "none";
        placeholder.style.display = "flex";
        placeholder.textContent = "Satellite image could not be loaded.";
    };

    image.src = url;
}

/* -------------------- RESET SELECTED ZONE -------------------- */

function clearZone() {
    currentZone = null;

    [
        "zoneTitle",
        "zoneLocation",
        "zoneLocality",
        "zoneCoordinates",
        "zoneLST",
        "zoneNDVI",
        "zoneBuilt",
        "zoneRoad",
        "zoneScore",
        "recommendation"
    ].forEach(function (id) {
        setText(id, "--");
    });

    setText("zoneGridSize", "500m × 500m");
    setText("priorityBadge", "--");

    document.getElementById("zoneSatellite").style.display = "none";
    document.getElementById("satellitePlaceholder").style.display = "flex";

    gridPanel.classList.add("hidden");

    if (gridLayer) {
        gridLayer.clearLayers();
    }
}

/* -------------------- HELPER FUNCTIONS -------------------- */

function setText(id, value) {
    const element = document.getElementById(id);

    if (element) {
        element.textContent = value;
    }
}

function formatValue(value, suffix) {
    if (suffix === undefined) {
        suffix = "";
    }

    if (value === undefined || value === null || value === "") {
        return "--";
    }

    const number = Number(value);

    if (Number.isFinite(number)) {
        return number.toFixed(2) + suffix;
    }

    return String(value) + suffix;
}

function formatInteger(value) {
    if (value === undefined || value === null || value === "") {
        return "--";
    }

    const number = Number(value);

    return Number.isFinite(number) ? String(Math.round(number)) : "--";
}

function priorityBackground(priority) {
    const value = String(priority).toLowerCase();

    if (value === "high") return "#f8e6e4";
    if (value === "medium") return "#f8f0df";
    if (value === "low") return "#e5f0e8";

    return "#eef1ef";
}

function priorityColor(priority) {
    const value = String(priority).toLowerCase();

    if (value === "high") return "#b7443d";
    if (value === "medium") return "#b37a20";
    if (value === "low") return "#4b8060";

    return "#68736d";
}