# PRD: Under-Reported Birds Discovery Engine (Durham County, NC)

Owner: Peter  
Status: Draft v0.1  
Last updated: 2026-01-07  
Primary user: Self (personal exploratory tool)

## 1) Summary

Build a data-driven system that:
1) estimates which bird species are **likely** to occur in Durham County, NC,
2) identifies which of those are **under-reported** in eBird relative to expectation, and
3) recommends **public-land, habitat-targeted survey locations + seasons** to increase detections,
4) provides an **interactive map** to guide field work and track progress over time.

Primary data source is eBird via eBird API 2.0 endpoints for species lists, observations, hotspots, and checklists. :contentReference[oaicite:0]{index=0}

## 2) Goals

### 2.1 Core goals
- **Likely-species list** for Durham County derived from:
  - eBird species lists in Durham + adjacent counties (baseline “regional presence”), and
  - external distribution baselines (atlas/range proxies), and
  - optional literature-based habitat constraints.
- **Under-reported ranking** that is robust to observer effort biases:
  - low absolute reporting in Durham despite strong regional presence
  - species present in atlas/range proxy but rare/absent in Durham eBird
- **Seasonality guidance**: best months / date windows to target each species.
- **Public-land targeting**: habitat and checklist-density driven suggestions restricted to public access.
- **Interactive map**:
  - checklist density heatmap
  - public lands overlay
  - hotspots + under-surveyed areas
  - per-species “where to look” suggestions

### 2.2 Non-goals (for v0)
- Modeling vagrants, pelagic species, flyover-only species, or exotics.
- Perfect detection modeling / occupancy modeling (can be v1+).
- Private land access, permission workflows, or community coordination features.

## 3) Key definitions

### 3.1 “Expected presence”
A species is “expected” for Durham if *any* of these are true:
- Appears in **adjacent-county** eBird species lists at meaningful frequency, AND habitat exists in Durham.
- Appears in an **external distribution baseline** indicating likely occurrence in/near Durham (see §5.2).
- Appears in Durham historically, but recent reporting is anomalously low (optional flag).

### 3.2 “Under-reported”
Primary definitions (your selected):
- **UR-1 (Regional mismatch):** Durham has a low reporting rate relative to adjacent counties after correcting for effort.
- **UR-2 (Atlas/range mismatch):** species present in atlas/range proxy but rare/absent in Durham eBird.

Secondary supporting signals:
- **Observer concentration bias:** checklists clustered at hotspots leaving “habitat holes”.
- **Time-of-day gap:** species is nocturnal/crepuscular but checklists are mostly daytime.
- **Habitat mismatch:** species tied to a habitat that is scarce and/or under-surveyed in Durham.

### 3.3 Adjacent counties
Adjacent counties will be discovered via eBird API “adjacent regions” endpoints (do not hardcode). :contentReference[oaicite:1]{index=1}  
(Initial expectation: Orange, Wake, Chatham, Granville, Person — but the system should compute this.)

### 3.4 Public land constraint
All recommended sites must be within public lands polygons (source TBD but should be open data).

## 4) Success metrics

### 4.1 Output quality metrics
- **Precision**: proportion of top-N ranked species that receive detections within the following season(s).
- **Actionability**: each top species has at least one public-land “where/when/how” plan.
- **Coverage**: suggested survey polygons cover major under-surveyed habitat types.

### 4.2 Field validation metrics
- Increase in Durham eBird reporting rate for top-N target species across next 6–18 months.
- New county records or “first in years” rediscoveries (self-tracked).
- Increase in checklists from under-surveyed public-land polygons.

## 5) Data sources

### 5.1 eBird API 2.0 (primary)
Use the official eBird API 2.0 endpoints, including:
- Species list for a region (`product/spplist`) :contentReference[oaicite:2]{index=2}
- Hotspots in a region (`ref/hotspot`) :contentReference[oaicite:3]{index=3}
- Recent checklists feed (`data/obs` / checklist feed endpoints) :contentReference[oaicite:4]{index=4}
- Historic observations on a date (`data/obs/historic`) for seasonality sampling :contentReference[oaicite:5]{index=5}
- Adjacent regions (`ref/geo/adjacent`) to discover county neighbors :contentReference[oaicite:6]{index=6}

Notes:
- eBird API has limits (e.g., “recent” typically up to ~30 days on some endpoints), so historical needs batching (date sampling strategy). :contentReference[oaicite:7]{index=7}

### 5.2 External “expected presence” baselines (secondary)
Pick one or two lightweight sources for v0:
- **NC-GAP terrestrial vertebrate distributions** (breeding birds coverage in NC) :contentReference[oaicite:8]{index=8}
- **USGS Breeding Bird Survey (BBS)** for regional presence trends/occurrence context :contentReference[oaicite:9]{index=9}
- Optional: **North American Breeding Bird Atlas Explorer** as an atlas-data hub (not necessarily NC-specific data, but useful framework) :contentReference[oaicite:10]{index=10}
- Optional (if you later want coastal/estuarine polygon data; probably not needed for Durham): NOAA ESI birds polygons (not a priority) :contentReference[oaicite:11]{index=11}

### 5.3 Habitat layers (keep it sane)
Minimum viable set:
- Land cover (e.g., NLCD classes)
- Wetlands (e.g., NWI)
- Hydrography (streams/rivers/lakes)
- Public lands polygons (state/county/federal)
That’s enough to model “wetland specialist vs forest interior vs early successional”, etc.

## 6) System outputs

### 6.1 Ranked target list (per species)
For each species:
- Under-report score (overall + components: UR-1, UR-2, bias terms)
- Evidence summary: adjacent-county frequency, Durham counts, atlas/range proxy flag
- Seasonality: best months / weeks (with confidence)
- Habitat tags: wetlands / mature forest / early successional / riparian / open fields, etc.
- Public-land candidate sites (top 3–10) with map links + notes
- Field protocol: time-of-day, listening strategy, playback policy (default: none), weather cues

### 6.2 Interactive map (Durham County)
Layers:
- Public lands polygons
- Hotspots (points)
- Checklist density heatmap / hex grid
- Under-surveyed polygons (public land + low checklist density + target habitat)
- Per-species predicted habitat suitability (toggle)
Interactions:
- Click polygon → see “why this is a target” + recommended species + best month
- Click species → show best sites + times + recent similar detections in adjacent counties

## 7) Core algorithms

### 7.1 Effort normalization (medium aggressive)
Compute effort-adjusted observation rates using:
- number of checklists
- total duration (sum of effort hours) where available
- distance traveled where available
- number of unique observers
For each county and each month, estimate “effort mass”.

### 7.2 Adjacent-county expectation
For each species:
- compute presence rate in adjacent counties (effort-adjusted)
- compute Durham presence rate (effort-adjusted)
- UR-1 score = f(adjacent_rate, durham_rate, uncertainty)

### 7.3 Atlas/range proxy expectation
If species is predicted present by external baseline in/near Durham:
- UR-2 score = penalty if Durham eBird rate is near-zero after sufficient effort

### 7.4 Observer behavior models (explicit)
- **Hotspot clustering index**: fraction of checklists within top X hotspots; identify “cold zones”
- **Habitat sampling gap**: checklist density per habitat class vs habitat area
- **Time-of-day gap**: distribution of checklist start times; flag taxa whose detectability peaks in under-sampled windows (night/dawn/dusk)

### 7.5 Final ranking
Final Under-Reported Score:
- w1 * UR-1 + w2 * UR-2 + w3 * HabitatGap + w4 * TimeGap
with guardrails:
- exclude vagrants/exotics/flyover-only species via taxonomy filters + heuristic rules
- prefer species with clear habitat signal and feasible detectability on public land

## 8) Implementation plan (phased)

### Phase 0 — Repo integration + scaffolding (1–2 days)
- Inventory existing eBird API scripts in your repo
- Create a unified python module: `src/ebird_client.py` that wraps calls
- Define region discovery workflow (Durham + adjacent counties via API) :contentReference[oaicite:12]{index=12}

### Phase 1 — Data collection + caching (3–7 days)
- Pull:
  - species lists for Durham + adjacent counties (baseline “regional presence”) :contentReference[oaicite:13]{index=13}
  - hotspots + coordinates :contentReference[oaicite:14]{index=14}
  - checklist feed sampling (and/or “historic observations on date” sampling) for seasonality :contentReference[oaicite:15]{index=15}
- Store in a local cache (SQLite recommended):
  - tables: regions, species, hotspots, checklists, observations, effort_summary

### Phase 2 — Under-report scoring v0 (3–7 days)
- Compute effort mass by county-month
- Compute UR-1 (Durham vs adjacent)
- Add UR-2 if external baseline is included (start with a single baseline to keep scope sane)
- Build per-species seasonality curves (month histogram normalized by effort)

### Phase 3 — Habitat + public land targeting (5–10 days)
- Ingest minimal GIS layers
- Compute checklist density raster/hex grid
- Intersect with public lands polygons
- Generate candidate survey polygons per habitat type
- Associate species↔habitat using:
  - literature tags (manual seed dictionary)
  - empirical correlations (species detections vs habitat class in adjacent counties)

### Phase 4 — Interactive map (5–10 days)
- Build a small local web app:
  - backend: FastAPI (or Flask)
  - frontend: Leaflet (or similar)
- Serve GeoJSON layers + API endpoints:
  - `/species`
  - `/species/{id}`
  - `/map/layers`
- Include a “survey plan export” (Markdown + GPX)

## 9) Data model (SQLite sketch)

- regions(region_code, name, type, parent_code)
- species(species_code, common_name, sci_name, category_flags)
- hotspots(loc_id, name, lat, lon, region_code)
- checklists(submission_id, loc_id, obs_dt, duration_min, distance_km, protocol, n_observers, region_code)
- observations(submission_id, species_code, count, obs_dt, lat, lon, breeding_code?, validated?)
- effort_summary(region_code, year, month, checklists, effort_hours, observers)

## 10) Risks & mitigations

- **API limits / incomplete historical coverage**
  - Use date sampling strategy rather than brute-force daily pulls
  - Cache aggressively and incrementally refresh
- **False “under-reported” due to true absence**
  - Require “expected presence” evidence + habitat availability check
- **Public lands polygon quality**
  - Start with a single authoritative dataset; document limitations
- **Overfitting to adjacent counties**
  - Keep weights tunable; allow “regional ring” expansion (2-hop neighbors) later

## 11) Deliverables

- `docs/PRD_underreported_birds_durham.md` (this file)
- `src/` modules for:
  - ebird API wrapper
  - scoring + seasonality
  - GIS + targeting
- `data/cache.sqlite`
- `outputs/targets_ranked.csv`
- `outputs/species_dossiers/{species_code}.md`
- `app/` interactive map (local)

---

## 12) Future Features

### 12.1 Seasonal Target Filtering (Month Selector)

**Status:** Planned
**Priority:** Medium
**Depends on:** Phase 2 seasonality curves, habitat rules

#### Problem Statement

The map UI includes a month dropdown filter, but it currently has no effect. Users cannot filter the target species list by season, making it harder to plan surveys for the current month.

#### Desired Behavior

When a user selects a month (e.g., "January"):
1. The species list filters to show only species that are **good survey targets** for that month
2. Species are considered targetable in a month if:
   - Their `seasonality` indicates presence (e.g., "winter" species show in Dec/Jan/Feb)
   - OR they are year-round residents
3. The under-reported ranking is preserved within the filtered list

#### Data Requirements

**Input:** `seasonality` field in `data/species_habitat_rules.json`
```json
"nswowl": {
  "seasonality": ["winter"],
  ...
}
```

**Output:** `best_months` column in `targets_ranked.csv`
```csv
species_code,common_name,...,best_months
nswowl,Northern Saw-whet Owl,...,"[12,1,2]"
```

#### Seasonality → Month Mapping

| Seasonality Tag | Months |
|-----------------|--------|
| `winter` | 12, 1, 2 |
| `spring` | 3, 4, 5 |
| `summer` | 6, 7, 8 |
| `fall` | 9, 10, 11 |
| `breeding` | 4, 5, 6, 7 |
| `migration` | 3, 4, 5, 9, 10, 11 |
| `year-round` | 1–12 (or empty = show always) |

Species with no `seasonality` field default to year-round (always shown).

#### Implementation Steps

1. **scoring.py**: Add `best_months` field to `SpeciesScore` dataclass
2. **habitat_model.py** or new module: Add `seasonality_to_months()` mapping function
3. **__main__.py**: Populate `best_months` from habitat rules when writing CSV
4. **write_scores_csv()**: Include `best_months` column as JSON array
5. **server.py**: Already handles `best_months` in `load_targets()` — no changes needed
6. **Frontend JS**: Already filters by `best_months` — no changes needed

#### Acceptance Criteria

- [ ] Selecting "January" shows only winter/year-round species
- [ ] Selecting "June" shows only summer/breeding/year-round species
- [ ] Selecting "All Months" shows all species (current behavior)
- [ ] Species without seasonality data appear in all months
- [ ] Dossiers display "Best Months" section when available

#### Future Enhancements (v1+)

- **eBird frequency data**: Replace/augment manual seasonality tags with actual eBird bar chart data showing when species are reported in the region
- **Detection probability weighting**: Weight months by detection probability, not just presence
- **Dynamic re-ranking**: Optionally re-rank species by "under-reported score for this month" based on monthly effort data

