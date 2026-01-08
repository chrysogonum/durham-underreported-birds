# Durham Under-Reported Birds

A data-driven tool for discovering under-reported bird species in Durham County, NC. Identifies species that are likely present based on adjacent county data and habitat availability, but are under-observed in local eBird records.

## Features

- **Under-reported species ranking** - Identifies birds that should occur in Durham based on regional patterns but have low local reporting rates
- **Habitat-based scoring** - Augments observer data with habitat availability analysis on public lands
- **Interactive map server** - Local Leaflet-based map with toggleable layers for public lands, checklist density, survey targets, and species spots
- **Species dossiers** - Detailed markdown reports for top target species with scoring breakdown and survey recommendations
- **Spot guides** - Trail-accessible birding locations with specific habitat requirements, parking/access info, timing, and detection tips
- **eBird API integration** - Fetches real observation data from eBird with local SQLite caching
- **Offline demo mode** - Run analyses using fixture data without API access

## Installation

```bash
# Clone the repository
git clone https://github.com/chrysogonum/durham-underreported-birds.git
cd durham-underreported-birds

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

### Demo Mode (No API Key Required)

Run with included fixture data to see how it works:

```bash
# Generate ranked species list
python -m bird_targets demo --fixtures tests/fixtures --out outputs/_demo

# Export GeoJSON layers and species dossiers
python -m bird_targets export --fixtures tests/fixtures --out outputs/_demo

# Start the interactive map server
python -m bird_targets serve --fixtures tests/fixtures --out outputs/_demo --port 8000
```

Then open http://localhost:8000 in your browser.

### Real eBird Data

To analyze real eBird data, you'll need an [eBird API key](https://ebird.org/api/keygen):

```bash
# Set your API key
export EBIRD_API_KEY=your_api_key_here

# Fetch data for Durham and adjacent counties (cached locally)
python -m bird_targets fetch --out data/ebird_cache --years 5

# Run analysis on cached data
python -m bird_targets run --cache data/ebird_cache --out outputs/real_5y

# Start the map server
python -m bird_targets serve --fixtures tests/fixtures --out outputs/real_5y
```

## CLI Commands

### `demo` - Run with fixture data
```bash
python -m bird_targets demo --fixtures <path> --out <path> [options]
```
Options:
- `--habitat-rules <path>` - Path to species habitat rules JSON
- `--observer-weight <float>` - Weight for observer-based scoring (default: 0.7)
- `--habitat-weight <float>` - Weight for habitat-based scoring (default: 0.3)

### `fetch` - Download eBird data
```bash
python -m bird_targets fetch --out <cache_path> [options]
```
Options:
- `--years <int>` - Years of historical data to fetch (default: 5)

### `run` - Analyze cached eBird data
```bash
python -m bird_targets run --cache <cache_path> --out <output_path> [options]
```

### `export` - Generate GeoJSON and dossiers
```bash
python -m bird_targets export --fixtures <path> --out <path>
```

### `serve` - Start map server
```bash
python -m bird_targets serve --fixtures <path> --out <path> [--port 8000]
```

## How Scoring Works

The tool calculates an **under-reported score** for each species using two signals:

### Observer-Based Expectation (default weight: 70%)
Compares reporting rates between Durham and adjacent counties (Orange, Wake, Chatham, Granville, Person). Species commonly reported in neighboring counties but rare in Durham score higher.

### Habitat-Based Expectation (default weight: 30%)
Uses species habitat requirements matched against Durham's public lands (Duke Forest, Eno River State Park, Falls Lake, etc.). Species whose preferred habitats are well-represented locally get a habitat boost.

**Combined Score:**
```
expected = (0.7 × observer_expected) + (0.3 × habitat_expected)
under_reported = max(0, expected - observed)
```

### Regional Plausibility Filter
To avoid ranking vagrants, species must either:
- Appear in ≥3 adjacent counties, OR
- Have ≥25 total observations across adjacent counties

## Output Files

After running analysis:

```
outputs/
├── targets_ranked.csv          # All species ranked by under-reported score
├── layers/
│   ├── public_lands.geojson    # Public land boundaries
│   ├── checklist_density.geojson  # Hotspot checklist counts
│   ├── survey_targets.geojson  # Priority survey areas
│   └── species_spots.geojson   # Trail-accessible birding spots
├── species_dossiers/
│   ├── woothr.md               # Wood Thrush dossier
│   └── ...
└── spot_guides/
    ├── bkbwar.md               # Black-and-white Warbler spot guide
    ├── woothr.md               # Wood Thrush spot guide
    └── ...                     # Guides for species with spot data
```

### Spot Guides

Each spot guide includes:
- **Why Under-Reported?** - Scoring breakdown showing observer rates, habitat availability, and the under-reporting gap
- **What Habitat Exactly** - Specific habitat requirements
- **Where to Look** - Top 3-10 trail-accessible locations with parking info
- **When to Survey** - Best months and time of day
- **How to Detect** - Calls, songs, and behavioral cues

### CSV Columns
| Column | Description |
|--------|-------------|
| `species_code` | eBird species code |
| `common_name` | Species common name |
| `observer_expected_score` | Expected rate from adjacent counties |
| `habitat_expected_score` | Expected rate from habitat model |
| `expected_score` | Combined expected score |
| `observed_score` | Actual Durham reporting rate |
| `underreported_score` | Gap between expected and observed |

## Project Structure

```
bird_targets/
├── __main__.py      # CLI entry point
├── scoring.py       # Under-reported score calculations
├── habitat_model.py # Habitat-based expectation model
├── export.py        # GeoJSON and dossier generation
├── server.py        # Leaflet map server
├── ebird_client.py  # eBird API wrapper
└── fetcher.py       # Data fetching and SQLite caching

data/
└── species_habitat_rules.json  # Habitat preferences for ~33 species

tests/
├── fixtures/        # Sample data for testing
└── test_*.py        # Test suites
```

## Development

```bash
# Run tests
pytest

# Run linter
ruff check .

# Format code
ruff format .

# Full verification (lint + test + demo)
make verify
```

## Adjacent Counties

The tool automatically analyzes these counties adjacent to Durham:
- Orange County
- Wake County
- Chatham County
- Granville County
- Person County

## Species with Habitat Rules

The habitat model includes rules for ~33 species commonly under-reported in the NC Piedmont:

**Owls:** Barred Owl, Eastern Screech-Owl, Great Horned Owl, Northern Saw-whet Owl

**Forest Birds:** Wood Thrush, Ovenbird, Kentucky Warbler, Worm-eating Warbler, Hooded Warbler, Summer Tanager, Scarlet Tanager

**Woodpeckers:** Pileated Woodpecker, Red-headed Woodpecker, Hairy Woodpecker

**Wetland/Riparian:** Virginia Rail, Sora, Louisiana Waterthrush, Prothonotary Warbler

**Open Country:** Northern Bobwhite, Loggerhead Shrike, Prairie Warbler

**Raptors:** Red-shouldered Hawk, Cooper's Hawk

See `data/species_habitat_rules.json` for the full list and habitat associations.

## License

MIT

## Acknowledgments

- [eBird](https://ebird.org) for the observation data API
- [Leaflet](https://leafletjs.com) for the mapping library
