"""Web server module for serving GeoJSON layers and map interface."""

from __future__ import annotations

import csv
import json
import socket
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable

# Available layers
AVAILABLE_LAYERS = ["public_lands", "checklist_density", "survey_targets"]

# Month names for filter
MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


def get_index_html() -> str:
    """Generate the HTML page with Leaflet map, sidebar, and layer toggles."""
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
        .app-container {
            display: flex;
            height: calc(100vh - 50px);
        }
        .sidebar {
            width: 280px;
            background: #f8f9fa;
            border-right: 1px solid #dee2e6;
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
        }
        .sidebar-header {
            padding: 12px;
            background: #e9ecef;
            border-bottom: 1px solid #dee2e6;
        }
        .sidebar-header h3 { font-size: 0.95rem; margin-bottom: 8px; }
        .filter-row {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        .filter-row select {
            flex: 1;
            padding: 4px 8px;
            border: 1px solid #ced4da;
            border-radius: 4px;
            font-size: 0.85rem;
        }
        .bird-list {
            flex: 1;
            overflow-y: auto;
            padding: 8px 0;
        }
        .bird-item {
            padding: 10px 12px;
            cursor: pointer;
            border-bottom: 1px solid #e9ecef;
            transition: background 0.15s;
        }
        .bird-item:hover { background: #e9ecef; }
        .bird-item.selected { background: #d4edda; border-left: 3px solid #28a745; }
        .bird-name { font-weight: 500; font-size: 0.9rem; }
        .bird-score {
            font-size: 0.75rem;
            color: #6c757d;
            margin-top: 2px;
        }
        .detail-panel {
            width: 320px;
            background: white;
            border-left: 1px solid #dee2e6;
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
        }
        .detail-header {
            padding: 12px;
            background: #343a40;
            color: white;
            font-weight: 500;
        }
        .detail-content {
            flex: 1;
            overflow-y: auto;
            padding: 12px;
            font-size: 0.85rem;
            line-height: 1.5;
        }
        .detail-content h1 { font-size: 1.1rem; margin-bottom: 12px; }
        .detail-content h2 { font-size: 0.95rem; margin: 12px 0 8px; }
        .detail-content h3 { font-size: 0.9rem; margin: 10px 0 6px; }
        .detail-content p { margin-bottom: 8px; }
        .detail-content ul { margin-left: 18px; margin-bottom: 8px; }
        .detail-content table {
            width: 100%;
            border-collapse: collapse;
            margin: 8px 0;
            font-size: 0.8rem;
        }
        .detail-content th, .detail-content td {
            border: 1px solid #dee2e6;
            padding: 4px 8px;
            text-align: left;
        }
        .detail-content th { background: #f8f9fa; }
        .detail-placeholder {
            color: #6c757d;
            text-align: center;
            padding: 40px 20px;
        }
        .map-container { flex: 1; position: relative; }
        #map { height: 100%; width: 100%; }
        .header {
            height: 50px;
            background: #2c3e50;
            color: white;
            display: flex;
            align-items: center;
            padding: 0 16px;
            justify-content: space-between;
        }
        .header h1 { font-size: 1rem; }
        .controls { display: flex; gap: 12px; }
        .control-item {
            display: flex;
            align-items: center;
            gap: 4px;
            font-size: 0.8rem;
        }
        .control-item input { cursor: pointer; }
        .control-item label { cursor: pointer; }
        .legend {
            position: absolute;
            bottom: 20px;
            right: 10px;
            background: white;
            padding: 8px;
            border-radius: 4px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            z-index: 1000;
            font-size: 0.75rem;
        }
        .legend h4 { margin-bottom: 6px; font-size: 0.8rem; }
        .legend-item { display: flex; align-items: center; gap: 6px; margin: 3px 0; }
        .legend-color { width: 14px; height: 14px; border-radius: 2px; }
        .highlight-layer {
            stroke: #9b59b6 !important;
            stroke-width: 4 !important;
            fill-opacity: 0.6 !important;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Durham Under-Reported Birds</h1>
        <div class="controls">
            <div class="control-item">
                <input type="checkbox" id="toggle-public-lands" checked>
                <label for="toggle-public-lands">Public Lands</label>
            </div>
            <div class="control-item">
                <input type="checkbox" id="toggle-checklist-density" checked>
                <label for="toggle-checklist-density">Hotspots</label>
            </div>
            <div class="control-item">
                <input type="checkbox" id="toggle-survey-targets" checked>
                <label for="toggle-survey-targets">Survey Areas</label>
            </div>
        </div>
    </div>
    <div class="app-container">
        <div class="sidebar">
            <div class="sidebar-header">
                <h3>Target Species</h3>
                <div class="filter-row">
                    <select id="month-filter">
                        <option value="">All Months</option>
                        <option value="1">January</option>
                        <option value="2">February</option>
                        <option value="3">March</option>
                        <option value="4">April</option>
                        <option value="5">May</option>
                        <option value="6">June</option>
                        <option value="7">July</option>
                        <option value="8">August</option>
                        <option value="9">September</option>
                        <option value="10">October</option>
                        <option value="11">November</option>
                        <option value="12">December</option>
                    </select>
                </div>
            </div>
            <div class="bird-list" id="bird-list"></div>
        </div>
        <div class="map-container">
            <div id="map"></div>
            <div class="legend">
                <h4>Legend</h4>
                <div class="legend-item">
                    <div class="legend-color" style="background: #27ae60;"></div>
                    <span>Public Lands</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #e74c3c;"></div>
                    <span>High Priority</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #f39c12;"></div>
                    <span>Medium Priority</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #9b59b6;"></div>
                    <span>Selected Target</span>
                </div>
            </div>
        </div>
        <div class="detail-panel">
            <div class="detail-header">Species Details</div>
            <div class="detail-content" id="detail-content">
                <div class="detail-placeholder">
                    Select a bird from the list to view details
                </div>
            </div>
        </div>
    </div>

    <script>
        // State
        let allTargets = [];
        let surveyTargetsData = null;
        let selectedBird = null;
        let highlightLayer = null;
        let map = null;
        let layers = {};

        // Initialize map (wrapped in try-catch for resilience)
        try {
            if (typeof L !== 'undefined') {
                map = L.map('map').setView([36.0, -78.95], 11);
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '&copy; OpenStreetMap'
                }).addTo(map);

                // Layer groups
                layers = {
                    publicLands: L.layerGroup().addTo(map),
                    checklistDensity: L.layerGroup().addTo(map),
                    surveyTargets: L.layerGroup().addTo(map),
                    highlight: L.layerGroup().addTo(map)
                };
            }
        } catch (e) {
            console.error('Map initialization failed:', e);
        }

        // Style functions
        function publicLandsStyle() {
            return {
                fillColor: '#27ae60', weight: 2, opacity: 1,
                color: '#1e8449', fillOpacity: 0.3
            };
        }

        function surveyTargetsStyle(feature) {
            const p = feature.properties.survey_priority;
            const colors = { high: '#e74c3c', medium: '#f39c12', low: '#3498db' };
            return {
                fillColor: colors[p] || '#95a5a6', weight: 2, opacity: 1,
                color: '#2c3e50', fillOpacity: 0.4, dashArray: '5, 5'
            };
        }

        function densityPointStyle(feature) {
            const d = feature.properties.density_class;
            const colors = { high: '#e74c3c', medium: '#f39c12', low: '#3498db' };
            return {
                radius: d === 'high' ? 10 : d === 'medium' ? 7 : 5,
                fillColor: colors[d] || '#95a5a6',
                color: '#2c3e50', weight: 1, opacity: 1, fillOpacity: 0.8
            };
        }

        function highlightStyle() {
            return {
                fillColor: '#9b59b6', weight: 4, opacity: 1,
                color: '#8e44ad', fillOpacity: 0.5
            };
        }

        // Load GeoJSON layer
        async function loadLayer(name, layerGroup, styleFunc, isPoint = false) {
            if (!map || !layerGroup) return;
            try {
                const res = await fetch('/layers/' + name);
                const geojson = await res.json();
                if (name === 'survey_targets') surveyTargetsData = geojson;

                if (isPoint) {
                    L.geoJSON(geojson, {
                        pointToLayer: (f, ll) => L.circleMarker(ll, styleFunc(f)),
                        onEachFeature: (f, layer) => {
                            const p = f.properties;
                            layer.bindPopup('<b>' + p.name + '</b><br>Checklists: ' +
                                p.checklist_count + '<br>Density: ' + p.density_class);
                        }
                    }).addTo(layerGroup);
                } else {
                    L.geoJSON(geojson, {
                        style: styleFunc,
                        onEachFeature: (f, layer) => {
                            const p = f.properties;
                            let h = '<b>' + p.name + '</b>';
                            if (p.survey_priority) h += '<br>' + p.survey_priority;
                            if (p.area_acres) h += '<br>Area: ' + p.area_acres + ' ac';
                            layer.bindPopup(h);
                        }
                    }).addTo(layerGroup);
                }
            } catch (e) { console.error('Failed to load layer:', name, e); }
        }

        // Load layers (only if map initialized)
        if (map) {
            loadLayer('public_lands', layers.publicLands, publicLandsStyle);
            loadLayer(
                'checklist_density', layers.checklistDensity, densityPointStyle, true
            );
            loadLayer('survey_targets', layers.surveyTargets, surveyTargetsStyle);
        }

        // Toggle handlers
        const $ = (id) => document.getElementById(id);
        $('toggle-public-lands').addEventListener('change', (e) => {
            if (!map) return;
            if (e.target.checked) map.addLayer(layers.publicLands);
            else map.removeLayer(layers.publicLands);
        });
        $('toggle-checklist-density').addEventListener('change', (e) => {
            if (!map) return;
            if (e.target.checked) map.addLayer(layers.checklistDensity);
            else map.removeLayer(layers.checklistDensity);
        });
        $('toggle-survey-targets').addEventListener('change', (e) => {
            if (!map) return;
            if (e.target.checked) map.addLayer(layers.surveyTargets);
            else map.removeLayer(layers.surveyTargets);
        });

        // Load targets
        async function loadTargets() {
            const list = $('bird-list');
            list.innerHTML = '<div class="detail-placeholder">Loading...</div>';
            try {
                const res = await fetch('/targets');
                if (!res.ok) throw new Error('HTTP ' + res.status);
                allTargets = await res.json();
                renderBirdList();
            } catch (e) {
                console.error('Failed to load targets:', e);
                list.innerHTML = '<div class="detail-placeholder">Error</div>';
            }
        }

        // Render bird list
        function renderBirdList() {
            const month = $('month-filter').value;
            const list = $('bird-list');
            list.innerHTML = '';

            const filtered = allTargets.filter(bird => {
                if (!month) return true;
                if (!bird.best_months || bird.best_months.length === 0) return true;
                return bird.best_months.includes(parseInt(month));
            });

            filtered.forEach(bird => {
                const div = document.createElement('div');
                const sel = selectedBird === bird.species_code ? ' selected' : '';
                div.className = 'bird-item' + sel;
                div.setAttribute('data-species', bird.species_code);
                div.innerHTML = '<div class="bird-name">' + bird.common_name +
                    '</div><div class="bird-score">Score: ' +
                    bird.underreported_score + '</div>';
                list.appendChild(div);
            });
        }

        // Select bird by species code
        function selectBird(speciesCode) {
            selectedBird = speciesCode;
            renderBirdList();
            highlightSurveyTargets();
            loadDossier(speciesCode);
        }

        // Event delegation for bird list clicks (more reliable in Safari)
        $('bird-list').addEventListener('click', function(e) {
            const item = e.target.closest('.bird-item');
            if (item) {
                const speciesCode = item.getAttribute('data-species');
                if (speciesCode) {
                    selectBird(speciesCode);
                }
            }
        });

        // Highlight survey targets
        function highlightSurveyTargets() {
            if (!map || !layers.highlight) return;
            layers.highlight.clearLayers();
            if (!surveyTargetsData) return;

            // Highlight high-priority survey targets
            L.geoJSON(surveyTargetsData, {
                style: highlightStyle,
                filter: (f) => f.properties.survey_priority === 'high'
            }).addTo(layers.highlight);
        }

        // Load dossier
        async function loadDossier(speciesCode) {
            const content = $('detail-content');
            try {
                const res = await fetch('/dossiers/' + speciesCode);
                if (res.ok) {
                    const md = await res.text();
                    content.innerHTML = markdownToHtml(md);
                } else {
                    content.innerHTML =
                        '<div class="detail-placeholder">No dossier</div>';
                }
            } catch (e) {
                content.innerHTML =
                    '<div class="detail-placeholder">Load error</div>';
            }
        }

        // Simple markdown to HTML converter
        function markdownToHtml(md) {
            let html = md
                .replace(/^### (.*$)/gm, '<h3>$1</h3>')
                .replace(/^## (.*$)/gm, '<h2>$1</h2>')
                .replace(/^# (.*$)/gm, '<h1>$1</h1>')
                .replace(/[*][*](.*?)[*][*]/g, '<strong>$1</strong>')
                .replace(/[*](.*?)[*]/g, '<em>$1</em>')
                .replace(/^- (.*$)/gm, '<li>$1</li>')
                .replace(/(<li>.*<[/]li>)/s, '<ul>$1</ul>')
                .replace(/\\n\\s*\\n/g, '</p><p>')
                .replace(/[|](.+)[|]/g, (match) => {
                    const cells = match.split('|').filter(c => c.trim());
                    if (cells.some(c => c.match(/^-+$/))) return '';
                    const tag = match.includes('---') ? 'th' : 'td';
                    return '<tr>' + cells.map(c =>
                        '<' + tag + '>' + c.trim() + '</' + tag + '>'
                    ).join('') + '</tr>';
                });
            // Wrap tables
            html = html.replace(/(<tr>.*?<[/]tr>)+/gs, '<table>$&</table>');
            return '<p>' + html + '</p>';
        }

        // Month filter handler
        $('month-filter').addEventListener('change', renderBirdList);

        // Initialize
        loadTargets();
    </script>
</body>
</html>
"""


class MapServerHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the map server."""

    def __init__(
        self,
        out_path: Path,
        *args,
        **kwargs,
    ) -> None:
        self.out_path = out_path
        self.layers_path = out_path / "layers"
        self.dossiers_path = out_path / "species_dossiers"
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
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(content)

    def send_text(self, text: str, status: int = 200) -> None:
        """Send a plain text response."""
        content = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def load_targets(self) -> list[dict]:
        """Load targets from CSV file."""
        csv_file = self.out_path / "targets_ranked.csv"
        if not csv_file.exists():
            return []

        targets = []
        with open(csv_file, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                target = {
                    "species_code": row["species_code"],
                    "common_name": row["common_name"],
                    "expected_score": float(row["expected_score"]),
                    "observed_score": float(row["observed_score"]),
                    "underreported_score": float(row["underreported_score"]),
                    "best_months": [],  # Default empty, can be extended
                }
                # Add best_months if column exists
                if "best_months" in row and row["best_months"]:
                    try:
                        target["best_months"] = json.loads(row["best_months"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                targets.append(target)
        return targets

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

        elif path == "/targets":
            targets = self.load_targets()
            self.send_json(targets)

        elif path.startswith("/dossiers/"):
            species_code = path[10:]  # Remove "/dossiers/" prefix
            dossier_file = self.dossiers_path / f"{species_code}.md"
            if dossier_file.exists():
                with open(dossier_file) as f:
                    content = f.read()
                self.send_text(content)
            else:
                self.send_text("Dossier not found", 404)

        else:
            self.send_json({"error": "Not found"}, 404)


def create_handler(out_path: Path) -> Callable:
    """Create a handler class with the output path bound."""
    return partial(MapServerHandler, out_path)


def is_port_available(port: int) -> bool:
    """Check if a port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("", port))
            return True
        except OSError:
            return False


def run_server(
    out_path: Path,
    port: int = 8000,
    quiet: bool = False,
) -> HTTPServer:
    """Start the map server.

    Args:
        out_path: Path to the output directory (containing layers/ and dossiers/)
        port: Port to listen on
        quiet: If True, suppress startup message

    Returns:
        The HTTPServer instance (useful for testing)
    """
    handler = create_handler(out_path)
    server = HTTPServer(("", port), handler)

    if not quiet:
        print(f"Starting server at http://localhost:{port}")
        print(f"Serving from: {out_path}")
        print("Press Ctrl+C to stop")

    return server
