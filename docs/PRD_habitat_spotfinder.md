Inputs
Existing outputs (targets_ranked.csv, public_lands.geojson, survey_targets.geojson)
A small, editable “habitat rules” file per species (you already started this in Phase F)
One access/trails source to start:
Prefer OpenStreetMap trails (free, no accounts, easy)
Don’t touch AllTrails yet (licensing + scraping issues)
Output
For each species code:
outputs/<run>/spot_guides/{species_code}.md containing:
“What habitat exactly” (very specific)
“Where in Durham to try” (top 3–10 named places)
“How to access” (trailhead / parking / nearest trail segment)
“When” (month + time-of-day if known)
“How to detect” (calls, behavior)
And a map layer:
outputs/<run>/layers/species_spots.geojson
points for suggested trail-accessible spots
properties: species_code, place_name, why_here, confidence
Constraints
Public land only
No more than 2–3 habitat layers initially
Keep it offline-testable with fixtures, but support real runs too
Success
Clicking a bird shows specific spot recommendations (not generic habitat text)