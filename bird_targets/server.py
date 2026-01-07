"""Web server module for serving GeoJSON layers and map interface."""

from __future__ import annotations

import json
import socket
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable

# Available layers
AVAILABLE_LAYERS = ["public_lands", "checklist_density", "survey_targets"]


def get_index_html() -> str:
    """Generate the HTML page with Leaflet map and layer toggles."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Durham Under-Reported Birds</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
        #map { height: calc(100vh - 60px); width: 100%; }
        .header {
            height: 60px;
            background: #2c3e50;
            color: white;
            display: flex;
            align-items: center;
            padding: 0 20px;
            justify-content: space-between;
        }
        .header h1 { font-size: 1.2rem; }
        .controls {
            display: flex;
            gap: 15px;
        }
        .control-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .control-item input { cursor: pointer; }
        .control-item label { cursor: pointer; font-size: 0.9rem; }
        .legend {
            position: absolute;
            bottom: 30px;
            right: 10px;
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            z-index: 1000;
            font-size: 0.85rem;
        }
        .legend h4 { margin-bottom: 8px; }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
            margin: 4px 0;
        }
        .legend-color {
            width: 16px;
            height: 16px;
            border-radius: 3px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Durham Under-Reported Birds - Survey Map</h1>
        <div class="controls">
            <div class="control-item">
                <input type="checkbox" id="toggle-public-lands" checked>
                <label for="toggle-public-lands">Public Lands</label>
            </div>
            <div class="control-item">
                <input type="checkbox" id="toggle-checklist-density" checked>
                <label for="toggle-checklist-density">Checklist Density</label>
            </div>
            <div class="control-item">
                <input type="checkbox" id="toggle-survey-targets" checked>
                <label for="toggle-survey-targets">Survey Targets</label>
            </div>
        </div>
    </div>
    <div id="map"></div>
    <div class="legend">
        <h4>Legend</h4>
        <div class="legend-item">
            <div class="legend-color" style="background: #27ae60;"></div>
            <span>Public Lands</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #e74c3c;"></div>
            <span>High Density Hotspot</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #f39c12;"></div>
            <span>Medium Density</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #3498db;"></div>
            <span>Low Density</span>
        </div>
    </div>

    <script>
        // Initialize map centered on Durham County, NC
        const map = L.map('map').setView([36.0, -78.95], 11);

        // Add OpenStreetMap tiles
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(map);

        // Layer groups
        const layers = {
            publicLands: L.layerGroup().addTo(map),
            checklistDensity: L.layerGroup().addTo(map),
            surveyTargets: L.layerGroup().addTo(map)
        };

        // Style functions
        function publicLandsStyle(feature) {
            return {
                fillColor: '#27ae60',
                weight: 2,
                opacity: 1,
                color: '#1e8449',
                fillOpacity: 0.3
            };
        }

        function surveyTargetsStyle(feature) {
            const priority = feature.properties.survey_priority;
            const colors = { high: '#e74c3c', medium: '#f39c12', low: '#3498db' };
            return {
                fillColor: colors[priority] || '#95a5a6',
                weight: 2,
                opacity: 1,
                color: '#2c3e50',
                fillOpacity: 0.4,
                dashArray: '5, 5'
            };
        }

        function densityPointStyle(feature) {
            const density = feature.properties.density_class;
            const colors = { high: '#e74c3c', medium: '#f39c12', low: '#3498db' };
            return {
                radius: density === 'high' ? 10 : density === 'medium' ? 7 : 5,
                fillColor: colors[density] || '#95a5a6',
                color: '#2c3e50',
                weight: 1,
                opacity: 1,
                fillOpacity: 0.8
            };
        }

        // Load layers
        async function loadLayer(name, layerGroup, styleFunc, isPoint = false) {
            try {
                const response = await fetch('/layers/' + name);
                const geojson = await response.json();

                if (isPoint) {
                    L.geoJSON(geojson, {
                        pointToLayer: (feature, latlng) => {
                            return L.circleMarker(latlng, styleFunc(feature));
                        },
                        onEachFeature: (feature, layer) => {
                            const props = feature.properties;
                            layer.bindPopup(
                                '<b>' + props.name + '</b><br>' +
                                'Checklists: ' + props.checklist_count + '<br>' +
                                'Density: ' + props.density_class
                            );
                        }
                    }).addTo(layerGroup);
                } else {
                    L.geoJSON(geojson, {
                        style: styleFunc,
                        onEachFeature: (feature, layer) => {
                            const p = feature.properties;
                            let h = '<b>' + p.name + '</b>';
                            if (p.area_acres) h += '<br>Area: ' + p.area_acres;
                            if (p.survey_priority) h += '<br>' + p.survey_priority;
                            if (p.type) h += '<br>Type: ' + p.type;
                            layer.bindPopup(h);
                        }
                    }).addTo(layerGroup);
                }
            } catch (err) {
                console.error('Failed to load layer:', name, err);
            }
        }

        // Load all layers
        loadLayer('public_lands', layers.publicLands, publicLandsStyle);
        loadLayer(
            'checklist_density', layers.checklistDensity, densityPointStyle, true
        );
        loadLayer('survey_targets', layers.surveyTargets, surveyTargetsStyle);

        // Toggle handlers
        const $ = (id) => document.getElementById(id);
        $('toggle-public-lands').addEventListener('change', (e) => {
            if (e.target.checked) map.addLayer(layers.publicLands);
            else map.removeLayer(layers.publicLands);
        });

        $('toggle-checklist-density').addEventListener('change', (e) => {
            if (e.target.checked) map.addLayer(layers.checklistDensity);
            else map.removeLayer(layers.checklistDensity);
        });

        $('toggle-survey-targets').addEventListener('change', (e) => {
            if (e.target.checked) map.addLayer(layers.surveyTargets);
            else map.removeLayer(layers.surveyTargets);
        });
    </script>
</body>
</html>
"""


class MapServerHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the map server."""

    def __init__(
        self,
        layers_path: Path,
        *args,
        **kwargs,
    ) -> None:
        self.layers_path = layers_path
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args) -> None:
        """Override to suppress default logging."""
        pass

    def send_json(self, data: dict | list, status: int = 200) -> None:
        """Send a JSON response."""
        content = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)

    def send_html(self, html: str, status: int = 200) -> None:
        """Send an HTML response."""
        content = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        """Handle GET requests."""
        path = self.path.rstrip("/")

        if path == "" or path == "/":
            self.send_html(get_index_html())

        elif path == "/layers":
            self.send_json(AVAILABLE_LAYERS)

        elif path.startswith("/layers/"):
            layer_name = path[8:]  # Remove "/layers/" prefix
            if layer_name in AVAILABLE_LAYERS:
                geojson_file = self.layers_path / f"{layer_name}.geojson"
                if geojson_file.exists():
                    with open(geojson_file) as f:
                        data = json.load(f)
                    self.send_json(data)
                else:
                    self.send_json({"error": "Layer file not found"}, 404)
            else:
                self.send_json({"error": "Unknown layer"}, 404)

        else:
            self.send_json({"error": "Not found"}, 404)


def create_handler(layers_path: Path) -> Callable:
    """Create a handler class with the layers path bound."""
    return partial(MapServerHandler, layers_path)


def is_port_available(port: int) -> bool:
    """Check if a port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("", port))
            return True
        except OSError:
            return False


def run_server(
    layers_path: Path,
    port: int = 8000,
    quiet: bool = False,
) -> HTTPServer:
    """Start the map server.

    Args:
        layers_path: Path to the layers directory containing GeoJSON files
        port: Port to listen on
        quiet: If True, suppress startup message

    Returns:
        The HTTPServer instance (useful for testing)
    """
    handler = create_handler(layers_path)
    server = HTTPServer(("", port), handler)

    if not quiet:
        print(f"Starting server at http://localhost:{port}")
        print(f"Serving layers from: {layers_path}")
        print("Press Ctrl+C to stop")

    return server
