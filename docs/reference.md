# Data and implementation reference

All commands below run from the repository root. Standalone pages in `build/` are generated locally and are not checked in.

Open **[index.html](../index.html)** for the combined, offline app. It has three tabs: **Imperialism Map**, **Victory Cycles**, and **Playoff Predictor**. Each tab keeps its own season, week, team selection, and view when you switch. Tab navigation supports clicks, Left/Right arrows, Home, and End.

The Imperialism Map uses a high-contrast tooltip above all map layers. Its county fills, territory borders, logos, and exports share the full map viewport, so zooming and panning do not leave uncolored outlines around a smaller rectangle.


A local, dependency-free starting point for football visualizations: canonical team names, numeric IDs, aliases, colors, and paths to both supplied logo collections.

- `data/teams.csv` and `data/teams.json`: one row per team with a locally available logo.
- `assets/logos/cfbd/`: all 453 numbered PNGs from CFBD.
- `assets/logos/fbs/`: all 145 PNGs from FBS-Logo-Library, with original filenames preserved.
- `data/conferences.json`: 11 conference/independent-group logos, separate from teams.
- `data/unmatched_logos.json`: preserved files without verified identities. Currently only `112358.png`.
- `data/sources/`: original lookup snapshot and source provenance.

The catalog contains 452 verified team identities. It covers multiple divisions and historical names, **not a current-season FBS membership list**. The named collection contains 134 team logos. A team's preferred `logo` uses that collection when available, falling back to CFBD. `logos` preserves both alternatives. Paths are relative to this project root; CSV aliases are pipe-separated, while JSON aliases are arrays.

## Use in Python

Run from the project root; no packages or API keys are needed:

```python
from cfb import resolve_team, logo_path

team = resolve_team("Alabama")
assert team["team_id"] == 333
print(team["school"], team["color"])
print(logo_path(333))                  # absolute path to preferred logo
print(logo_path("Alabama", "cfbd"))    # explicitly choose CFBD's version
print(resolve_team("Miami (OH)"))      # separate from Miami
```

`resolve_team` accepts numeric IDs, canonical names, slugs, and recorded aliases. It ignores case, accents, and punctuation. Unknown names raise `KeyError`; shared abbreviations such as `SDSU` raise `ValueError` with candidates. Use full names or IDs to disambiguate. Avoid joining on mascot names alone.

For pandas, load `data/teams.csv`, join on `team_id`, and use `logo` for plotting. IDs are provider identifiers, not row numbers. Keep them in external datasets rather than using filenames or display names as keys. Five supplemental identities come from ESPN and are explicitly marked `identity_source="espn"`; the remaining identities come from the CFBD snapshot.

## Where the CFBD lookup lives

The CFBD website fetches `/teams` (or `/teams/fbs`) and uses each result's `id` and `school` to construct `/logos/{id}.png`. This is visible in [its SP view](https://github.com/CFBD/cfb-web/blob/92d2bfb8efca9e87074c4927e4816fc2c1649be6/src/views/SP.vue). The supported current mapping is the [CFBD Teams API](https://github.com/CFBD/cfbd-python/blob/main/docs/TeamsApi.md), which requires an API credential.

For an offline starting point, this project uses [CFBNumbers' public CFBD-derived snapshot](https://github.com/CFBNumbers/logos/blob/main/cfblogos.csv). Its CSV has an extra leading row-index field not represented in the header, and uses Latin-1 encoding; the builder accounts for both. The snapshot is historical: conference/division values are intentionally excluded from the output, and school names/colors may also need seasonal updates. Logos are the versions present in the supplied repositories; collection completeness and current branding are not guaranteed.

Five numbered logos absent from the snapshot were identified through ESPN's public team endpoint: `https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/{id}`. The IDs are 2019 (Allen), 2206 (Edward Waters), 110243 (UT Permian Basin), 110254 (Davenport), and 124180 (Bluefield State University). `112358` returned no team and remains unmatched.

## Rebuild and validate

```sh
python3 scripts/build_catalog.py
python3 -m unittest discover -s tests -v
```

The rebuild uses only checked-in files and never accesses the network. Explicit filename exceptions live in `scripts/build_catalog.py`. All PNGs must appear exactly once across team logos, conference/group logos, and the unmatched report. Tests also check PNG chunk checksums, unique IDs/slugs, representative aliases, missing names, and ambiguous abbreviations.

Source repositories:

- [Lou34964/FBS-Logo-Library](https://github.com/Lou34964/FBS-Logo-Library/tree/main/CFB%20Logos)
- [CFBD/cfb-web](https://github.com/CFBD/cfb-web/tree/master/public/logos)

Exact downloaded repository commits are recorded in `data/sources/provenance.json`. Original logo bytes and filenames are preserved. Logos remain the property of their respective owners; source availability does not grant trademark rights. CFBD repository license text is retained in `data/sources/cfb-web-LICENSE`.

## Wins and losses, 2016–2025

`data/season_records.csv` (also JSON) contains **1,312 team-season rows for 137 programs** across the last ten completed seasons. Scope is every **FBS member in each season**, including transitional programs. Records include all opponents, conference championship games, bowls, and playoff games. January postseason games belong to the preceding fall season. The ongoing 2026 season is excluded.

`data/decade_records.csv` (also JSON) aggregates those records by team. `seasons` counts FBS membership rows; `seasons_played` excludes canceled seasons. Programs that joined or left FBS have fewer than ten seasons: totals exclude their FCS years. Do not interpret missing seasons as winless seasons. For example, Idaho appears through 2017, while James Madison starts in 2022. UAB has no 2016 row because it had not yet resumed play.

```python
from cfb import load_season_records

alabama = load_season_records("Alabama")
records_2025 = load_season_records(season=2025)
```

```python
import pandas as pd

records = pd.read_csv("data/season_records.csv")
# Already includes school and the preferred local logo path.
wins = records.pivot(index="school", columns="season", values="wins")
# Leave absent FBS seasons as NaN; do not fill them with zeros.
```

Fields include `season`, `team_id`, canonical `school`, `source_school`, that season's `conference`, `wins`, `losses`, `ties`, `games`, `win_pct`, conference record splits, `status`, `record_source`, `source_url`, `logo`, and `logo_source`. Win percentage is `(wins + ties / 2) / games`, rounded to six decimals; zero-game seasons have a null percentage. Conference splits are ESPN's `vsconf` record and can follow different championship-game conventions from overall totals; unavailable splits are null. Source names/conference labels reflect the provider's historical endpoint and can use renamed branding.

The larger FBS collection is preferred in every output wherever available. Of the 137 programs, only Delaware, Missouri State, and Idaho lack a logo in that collection and use CFBD's fallback.

### Sources and special seasons

The primary source is ESPN's public [historical standings endpoint](https://site.api.espn.com/apis/v2/sports/football/college-football/standings?season=2025), queried once per season. These are provider-reported competition records, not a reconstruction of NCAA sanctions or vacated-win adjustments. Each row links its source. All downloaded responses are archived in `data/sources/records/` as gzip files, with retrieval timestamps, URLs, and SHA-256 checksums in `manifest.json`.

Three documented 2020 adjustments live in `data/sources/records/adjustments.json`:

- UConn and Old Dominion: explicit 0–0 rows marked `did_not_play`, based on [UConn's cancellation announcement](https://uconnhuskies.com/news/2020/8/5/uconn-football-announces-cancellation-of-2020-season-due-to-risks-associated-with-covid-19) and [Old Dominion's announcement](https://odusports.com/news/2020/08/10/old-dominion-athletics-announces-cancellation-of-fall-sports-season). Both are absent from ESPN standings.
- New Mexico State: 1–1, marked `spring_season`, from [the school's 2020-21 statistics](https://nmstatesports.com/sports/football/stats/2020-21). ESPN lists 0–0. Those spring games are assigned to 2020 rather than combined with fall 2021.

### Audit and reproduction

[SportsDataverse's CFBD-derived schedules](https://github.com/sportsdataverse/cfbfastR-data/tree/main/schedules/csv) provide an additional check. **Every overall FBS record in 2023–2025 matches the completed-game results.** The downloaded 2016–2022 schedule files contain only regular-season games, so they cannot fully validate overall records. Their 518 differences are retained in `data/records_coverage.json`, alongside New Mexico State's missing spring games, rather than used to overwrite standings. This report also lists yearly team counts and membership gaps. The 2020 schedule lacks the two canceled programs and New Mexico State; all other yearly team sets match.

Refresh sources from the network, then rebuild:

```sh
python3 scripts/fetch_records.py
python3 scripts/build_records.py
python3 -m unittest discover -s tests -v
```

For an offline rebuild, skip `fetch_records.py`. The three reviewed adjustments are preserved when sources are refreshed. Fetching uses only Python's standard library and needs no API key.

## Campus coordinates and nearest-team county map

Open **[build/closest-teams.html](../build/closest-teams.html)** directly in a browser. It is a standalone HTML/JavaScript Plotly visualization with all libraries, data, basemap, and logo images embedded. It works offline over `file://`, with no server, API key, or build step. The file is about 21 MB because it contains the county geometry and PNG logos. Zoom or pan, inspect counties on hover, select teams, toggle logos/boundaries, or export an SVG with the logos included.

The map uses the **136 FBS teams in the 2025 records**. Coordinates are available for **all 452 catalog schools**, including schools outside FBS:

- `data/school_locations.csv` / `.json`: `team_id`, school, institution, IPEDS `unitid`, `latitude`, `longitude`, city/state/country, location kind, source year, and source URL.
- `data/county_assignments.csv` / `.json`: all **3,144 counties and county equivalents**, nearest team ID/name/color, county reference coordinates, and distance in kilometers. FIPS codes are five-character strings; preserve leading zeros when importing CSV.
- `data/counties.geojson`: display boundaries with county IDs and assignments.
- `data/team_regions.geojson`: unions of each team's assigned counties.
- `data/map_coverage.json`: coverage and logo-placement exceptions.

```python
from cfb import load_school_locations

locations = {r["team_id"]: r for r in load_school_locations()}
print(locations[333]["latitude"], locations[333]["longitude"])
```

### Coordinate sources

Coordinates describe **main campuses, not stadiums**. The [NCES IPEDS HD2024 directory](https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx?gotoReportId=7&rtid=1&year=2024) supplies 445 coordinates. Six renamed/merged or closed schools use the archived 2021 directory: Lock Haven, Alderson-Broaddus, Bloomsburg, Clarion, Edinboro, and California (PA). Canadian school Simon Fraser uses an explicitly sourced campus-coordinate override; it is not in the FBS map. A location in the catalog does not imply the institution or its football program remains active.

The reviewed crosswalk in `data/sources/geography/team_institutions.json` links team IDs to institutional IDs and names. It distinguishes similarly named schools and branch campuses (for example, Texas is UT Austin, California is UC Berkeley, Arizona State is Tempe, and Miami is Coral Gables). No fuzzy matching runs during a rebuild. The separate `location_overrides.json` records the Canadian exception.

### Distance and logo placement

Each county takes the primary color of the closest main-campus point, measured by the **haversine great-circle distance** from its [Census Gazetteer internal reference point](https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html). An internal reference point is not necessarily the geometric centroid. Ties resolve to the smaller team ID. The JavaScript calculates the assignments and checks them against the saved Python results. Colors come from the existing catalog's primary-color snapshot, and FBS logos remain preferred.

Coverage is the **50 states plus Washington, D.C.**, including Alaska/Hawaii insets, independent cities, Louisiana parishes, Alaska county equivalents, and Connecticut's nine planning regions. Territories are excluded. The [Census 2025 cartographic boundary file](https://www.census.gov/geographies/mapping-files/2025/geo/carto-boundary-file.html) supplies the polygons. Shared edges are simplified together to avoid introducing artificial cracks between counties; reference points/distances retain their original precision.

A logo's center is always its campus coordinate. Its size is capped so its rectangle fits inside an inscribed circle centered at that point, bounded by the nearest projected boundary of the team's region. This is recomputed after zooming, panning, and resizing. Logos never move to a region's centroid. Large regions do not guarantee large logos: proximity to a coast, an internal hole, or a competing county can limit the size. Extremely small logos become easier to see when zooming.

Whole-county assignment makes the centered-logo requirement impossible for **eight teams**. Stanford, California, UCLA, North Carolina, Houston, Eastern Michigan, and Georgia State have campuses inside counties assigned to another team. Miami receives no counties at all. These locations are shown as dots rather than displaced or overflowing logos, and the team selector explains each case. The other **128 campuses** receive fitted logos.

This shows geographic proximity, not fan support, recruiting reach, travel time, or state/conference boundaries.

### Rebuilding and checking the map

Coordinate and assignment files are checked in. Generate the standalone HTML locally; rebuild dependencies are listed in `requirements.txt`:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/build_geography.py
.venv/bin/python -m unittest discover -s tests -v
```

To refresh downloaded inputs first, run `python3 scripts/fetch_geography.py`. Downloads, source URLs, timestamps, and content hashes live under `data/sources/geography/`. Edit `maps/template.html` and `maps/map.js`, then rerun the builder to regenerate `build/closest-teams.html`. The JavaScript relies on the pinned Plotly projection for SVG overlay alignment; check it before upgrading Plotly.

Optional browser validation uses Playwright and an installed Chrome/Chromium:

```sh
.venv/bin/pip install playwright
.venv/bin/python scripts/check_map.py --browser /usr/bin/google-chrome
```

The check opens the actual HTML through `file://`, verifies that it makes no network requests, checks all fitted logo corners against their region paths, and exercises hover/click, team selection, toggles, zoom/reset, SVG download, and a mobile viewport. Numerical tests verify all county assignments, complete coordinate coverage, source checksums, and exact county-union geometry.

## Football imperialism

Open **[build/imperialism.html](../build/imperialism.html)** directly in a browser. It is a second standalone, offline Plotly map with:

- A **season dropdown for 2016–2026**.
- A **week slider across the bottom of the map**, starting with Preseason.
- Previous/next week controls and Play/Pause.
- County hover details showing the current owner and original school, a team inspector, a county-count leaderboard, and each week's land-winning games.
- Zoom/pan, logo/border toggles, and SVG export with the chosen season/week and logos.

The initial view is **2026, Week 8**, with completed results through October 24, 2026 Eastern time (October 25 UTC). This is a saved results snapshot; it does not query live scores when opened. The 2026 preseason roster has 138 FBS programs, including Sacramento State and North Dakota State as classified by the source.

### Imperialism rules

Each season starts fresh. Every county is assigned to the closest FBS **main campus for that season**, using the same coordinates and county reference points as the proximity map. When a completed game has a winner, that winner receives **all land currently held by the loser**, including any land the loser previously conquered. Beating a landless team changes nothing. A landless team can reenter by beating a landholder. FCS and lower-division raiders are included; they start without land and can acquire it by winning. Ties, unfinished games, and canceled games move no land. Completed games are replayed in kickoff order, with game ID breaking an exact timestamp tie.

Starting membership follows each historical season, including transitional programs and the canceled 2020 programs. Idaho seeds land through 2017 and can be an FCS raider thereafter. A school need not receive a county under the whole-county nearest-reference-point method; it can still acquire land later. Every frame accounts for all 3,144 counties exactly once.

The border groups remain the original preseason territories. A conquered territory takes its current owner's primary catalog color and logo. Unlike the campus-centered proximity map, **imperialism logos sit inside each original territory**, so the same winning school can appear across several captured regions, matching the presentation of the [RedditCFB reference](https://cdn.redditcfb.com/imperialism/FBS/archive/2026-10-18.png). Label anchors are interior points in the largest connected part of a territory, with separate anchors for Alaska/Hawaii where applicable. Logos resize to fit their regions as the map view changes. Using main campuses and modern Census geography means this implementation's exact starting borders can differ from the reference.

FBS-Logo-Library remains preferred. **58 higher-resolution ESPN fallback logos** cover landholders without an FBS-library asset, including historical FCS raiders; the original small CFBD PNGs remain a fallback if a new claimant's large logo has not yet been downloaded. The separate asset manifest records their sources and hashes. Colors and logos reflect the existing catalog/current asset versions, not historical branding for each season.

### Weeks, bowls, playoffs, and spring 2021

The slider includes Preseason, then Week 0 where played, followed by Week 1 and subsequent weeks. Week 1 contains **Labor Day weekend**, including years when that Saturday falls in August. Weeks run Tuesday–Monday in America/New_York. Bowl/playoff weeks continue the regular-season sequence rather than resetting to 1; they are labeled Postseason. The 2020 timeline includes its postponed spring 2021 games, labeled Spring. Weeks with no completed games are omitted. The range updates when the season changes.

The new [SportsDataverse unified schedule feed](https://github.com/sportsdataverse/cfbfastR-cfb-data/tree/main/cfb/cfb_schedules/parquet) includes regular season, bowls, playoffs, and spring-season games. It fixes the postseason coverage limitation in the older schedule archives used for the win/loss audit. For all ten completed seasons, its FBS game totals match the existing season-record data, including the New Mexico State spring adjustment.

### Files and rebuilding

- `cfb/imperialism.py`: pure-Python transfer engine and week numbering.
- `data/imperialism.json`: starting assignments for each distinct roster, weekly ownership snapshots, and conquest events. Owners are aligned with each geography's ordered `seeds` array, and county assignments align with `county_ids`.
- `data/imperialism_games.json.gz`: normalized completed games used for replay.
- `data/imperialism_coverage.json`: season coverage, raiders, last available result, and independent FBS record comparison.
- `data/counties.topojson`: shared county topology used by the browser to draw original territory borders without embedding separate geometry for every season.
- `data/sources/imperialism/`: downloaded season schedules, retrieval timestamps, source URLs/checksums, and fallback-logo manifest.
- `maps/imperialism-template.html` and `maps/imperialism.js`: editable UI sources.

The builder needs Python dependencies and Node.js (Node 18+ works). TopoJSON build code is vendored; no npm installation is needed.

```sh
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/build_imperialism.py
.venv/bin/python -m unittest discover -s tests -v
```

To refresh results from the network, run `python3 scripts/refresh_results.py`. If new landholders need large logos, run `python3 scripts/fetch_imperialism_logos.py` after rebuilding, then rebuild once more to embed those assets. Changing the template or JavaScript also requires rebuilding the HTML.

Optional browser validation:

```sh
.venv/bin/python scripts/check_imperialism.py --browser /usr/bin/google-chrome
```

Validation covers all 11 season selectors, preseason and postseason, county conservation, landless reentry, chronological conquest chains, ties, Labor Day/UTC week boundaries, saved-source checksums, and the real 2016 Iowa → North Dakota State → South Dakota State → James Madison land chain. Browser checks additionally exercise rapid slider/season changes, playback, week stepping, hover/click, logo containment, SVG export, mobile layout, and absence of network requests.

Imperialism concept: [u/nbingham196](https://www.reddit.com/user/nbingham196/). Reference image: RedditCFB. This is an independent implementation, not an official recreation of RedditCFB's map.

## Victory Cycles (circles of suck): interactive win network

Open **[build/circles-of-suck.html](../build/circles-of-suck.html)** directly in a browser. The season dropdown and bottom week slider use the same **2016–2026** snapshot and week conventions as imperialism. Results are cumulative through the chosen week; the initial view is 2026 Week 8. The page works offline, including its background cycle searches. Links between the three visualizations are available in each page's footer.

Suggested interaction:

1. **Click a team logo**, or choose a team in the sidebar. The graph defaults to that team’s whole connected group, so circles can span many hops.
2. Use **1 hop** to narrow the graph to direct opponents, then **+1 hop** to include opponents of opponents; expand again as needed, or choose **All connected**. Connections follow games in either direction, while arrows always point **winner → loser**. **Entire network** clears the focus.
3. Click **Find smallest & largest circles** to find the smallest circle and search for the largest within the current view. With a team selected, the default also requires that team to appear in the circle; uncheck the requirement to search anywhere in its neighborhood.
4. For an intermediate size, enter a number (for example **5**) under **Or find exactly** and click **Find this length**. **Another circle** browses matching loops. These searches use the same team requirement and network scope.
5. Click the **Smallest** or **Largest** result card to display that circle in order, with only its cycle edges. The proof panel lists a real score and date for every step, including the win that closes the loop. **Back to network** restores the exploratory graph.

Nodes can be dragged, and the SVG can be panned/zoomed. Team names can be shown, arrows expose scores, and **Save SVG** exports the current graph or circle with embedded logos, arrowheads, and season/week labels.

### What counts as a circle?

A circle is a **simple directed cycle**: each team beat the next, the final team beat the first, and no team is repeated. Games need not occur in cycle order in the real season, but every game must have happened by the selected week. Repeated wins over an opponent share an arrow. The default minimum size is **two teams**, matching **Allow circles of 2+ teams**. This permits A → B → A if each team won a meeting; turning the checkbox off raises the minimum to three. Neither setting limits how long a circle can be. Neighborhood hop count and circle length are separate controls. Ties and unfinished games do not create edges.

**FBS teams** shows only that season's FBS roster and results between those schools. **FBS + their opponents** additionally shows schools that have played an FBS team by the selected week, plus available games between those included teams. This expanded view is not an exhaustive all-divisions network. Supplemental ESPN metadata identifies UT Rio Grande Valley, Long Island University, and West Georgia, which were absent from the original logo catalog; initials stand in for missing logos. Existing FBS-library logos remain preferred.

### Search guarantees

The shortest eligible directed cycle is found **exactly** using breadth-first searches. Searches can require the selected team and can exclude two-team rematch pairs.

A longest simple cycle is much harder to compute. Full-FBS season/week reference results are precomputed with **SciPy/HiGHS integer optimization**, using cycle covers, subtour cuts, and connectivity constraints. Each snapshot saves an actual cycle, a valid upper bound, and a flag indicating whether optimality was proved. The page validates that a reference fits the current teams, edges, minimum size, and selected-team requirement before using it. An optimum for the full FBS graph can also certify a filtered view if its entire optimal cycle remains in that view.

Other views use a cancellable **Web Worker** with exact enumeration/pruning under a time budget: initially 1.8 seconds, or 8 seconds per **Search longer** request. A found circle is always real, but a timed-out longest search is labeled **Best found**, with a bound on how many teams a larger circle could contain. It is labeled **Proven longest** only after the search is exhausted, a certified upper bound is met, or a valid certified reference applies. More searching preserves the incumbent and changes the traversal order. Changing season, week, scope, or team cancels the old search and clears stale results.

For the default **2026 Week 8 FBS graph**, the smallest cycle has **3 teams** and the proven longest has **101 teams**. Some late-2020 full-FBS reference snapshots remain bounded rather than proved; they receive the same honest best-found treatment as difficult filtered searches. See `data/circles_coverage.json` for reference coverage.

### Building and verifying

Viewing the generated file requires no dependencies. Rebuilding the page from the checked-in game data and reference cache uses Python's standard library:

```sh
python3 scripts/build_circles.py
```

Editable files are `maps/circles-template.html`, `maps/circles.js`, `maps/circles-algorithms.js`, and `maps/circles-worker.js`. The same graph algorithms run in the browser, its embedded worker, and the Node tests. SVG rendering uses the existing vendored D3 library. No network access is needed while using the page.

To recompute offline reference cycles after updating the game archive, install the optional solver dependencies and run:

```sh
python3 -m pip install -r requirements.txt
python3 scripts/compute_circles.py
python3 scripts/refine_circles.py   # optional extra proof effort on difficult graphs
python3 scripts/build_circles.py
```

`compute_circles.py` checkpoints its results and reuses matching completed proofs. Repeated snapshots with identical directed edges share a result. The builder verifies the game-archive hash and refuses to reuse stale references after game data changes. Supplemental identity responses and their source hashes live in `data/sources/circles/`; refresh those with `python3 scripts/fetch_circles_metadata.py` if needed.

Validation:

```sh
.venv/bin/python -m unittest discover -s tests -v
node tests/test_circles_algorithms.cjs
.venv/bin/python scripts/check_circles.py --browser /usr/bin/google-chrome
```

Checks include real scores for every cached cycle edge, no repeated teams, cumulative week cutoffs, exact shortest results, integer-solver bounds, and 180 comparisons of the browser algorithm with exhaustive enumeration on random small graphs. Browser checks exercise all 11 seasons, logo focus, hop expansion, required-team searches, proven 2026 extrema, rematch pairs, worker cancellation, arrow direction/closure, SVG export, mobile layout, and no external requests. The optional solver unit test skips when SciPy is absent; page generation and viewing do not need SciPy.

### Finding the five-team Michigan example

Choose **2026**, **Week 6** (or Week 7), and **Michigan**. Leave the neighborhood at **All connected** and **Must include Michigan** checked. Enter **5** and select **Find this length**. At Week 6 this returns:

| Winner | Loser | Score | Date |
| --- | --- | --- | --- |
| Michigan | Oklahoma | 17–10 | September 12, 2026 |
| Oklahoma | Texas | 27–24 | October 10, 2026 |
| Texas | Ohio State | 24–23 | September 12, 2026 |
| Ohio State | Iowa | 31–14 | October 3, 2026 |
| Iowa | Michigan | 20–19 | September 26, 2026 |

The Oklahoma–Texas game completes the circle in Week 6. All five wins are checked against the archived season results. With a focused team, the displayed circle and proof begin at that team. Exact-size searches return up to 50 matching simple cycles initially; Another circle browses them. Search longer can collect more. “No matching circle” is reported only if the search is exhausted; a timed-out empty search remains inconclusive. The browser algorithm is checked against 200 additional exhaustive small-graph cases for exact sizes, required teams, duplicate rotations, continuation, and timeouts.

## Building the combined page

`index.html` embeds both visualizations and their libraries/data. It can be opened directly over `file://` or copied by itself to another folder; no server, sibling files, network calls, or API keys are required. Its size is about 25 MiB because it contains both offline views and their logos. The individual map and graph HTML files remain available.

After changing either visualization, regenerate that standalone file first, then the bundle:

```sh
# When the Imperialism Map source changes:
.venv/bin/python scripts/build_imperialism.py
# When the circles source changes:
python3 scripts/build_circles.py
# Package the latest versions into the combined page:
python3 scripts/build_visualizations.py
```

The app shell sources are `maps/visualizations-template.html` and `maps/visualizations.js`. Each view has an isolated embedded document so its element IDs, styles, SVG markers, event handlers, and search worker cannot collide with the other view. The graph is loaded on its first tab activation, and both views stay mounted to preserve state. Map playback pauses when its tab is hidden. A small embedded header keeps the season controls, while the shared title and tab bar remain visible above the active view.

Map rendering corrections live in `maps/imperialism.js` and `maps/imperialism-template.html`:

- Hover information uses a fixed-position, dark-background/white-text card at document level, above borders, logos, and controls. It hides during dragging, changes of week/season, and tab switches.
- Plotly's Albers USA fit rectangle is expanded to the full visible plot viewport, including its background/hit-test axes; overlays use a matching viewport clip. That keeps the actual territory color visible along zoomed/panned edges.
- Logo sizes also respect the viewport edges. SVG export expands the recreated Plotly clip in the same way, so exports match the displayed colors.

For the combined-page regression checks, install the optional browser-check dependencies and run:

```sh
.venv/bin/pip install playwright Pillow
.venv/bin/python scripts/check_visualizations.py --browser /usr/bin/google-chrome
```

The checks exercise both tabs, keyboard navigation, independent state preservation, the verified Michigan five-team circle, SVG downloads, mobile layout, and an isolated copy of the single HTML file. Map regressions are checked with actual screenshot pixels at land locations beyond the old fill rectangle, after both zoom and pan, plus tooltip colors and top-layer placement. No external network requests are allowed during browser checks.

### Refreshing results

Run from the repository root:

```bash
.venv/bin/python scripts/refresh_results.py
```

This downloads completed ESPN daily scoreboards for FBS, FCS, Division II, and Division III since the previous results snapshot, archives the responses and their checksums, updates the current-season schedule, and rebuilds both standalone pages and `index.html`. It preserves historical cycle proofs and computes only changed graphs. Install `requirements.txt` into the active Python environment for all build and solver dependencies. The page remains an offline snapshot, so refresh it in the browser after rebuilding. If no completed results changed, it leaves saved files unchanged. A newly added game absent from the saved schedule stops the refresh with an explicit error rather than guessing team identities.

### Daily updates on GitHub

`.github/workflows/update-results.yml` runs daily at **13:17 UTC** (9:17 a.m. Eastern daylight time / 8:17 a.m. Eastern standard time) and also provides an **Actions → Update football results → Run workflow** button. Once pushed to the repository's default branch with Actions enabled, it installs the build dependencies, refreshes results, rebuilds both tabs, runs data and cycle tests, and commits changed datasets and the combined `index.html`. Generated standalone pages stay in the ignored `build/` directory. Days without changed results produce no commit. Failed downloads, builds, or checks stop the job before it pushes anything.

The workflow requests `contents: write` using GitHub's built-in token; no ESPN API key or personal token is needed. Repository rules must allow the bot to push to the default branch. The project is published from `nosejam/college-football-visualizations`; the current workflow includes deployment in the same run. GitHub schedules can be delayed and public-repository schedules can be disabled after 60 days of inactivity; check the Actions tab if updates stop. See [GitHub's scheduled workflow documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

The updater targets the latest imported football season, including its following-January postseason. A new season's schedules, membership, and build year range still need to be imported before that season starts. This workflow updates repository files; publishing the site is a separate setup. If GitHub Pages is used, deploy it explicitly from this workflow: commits made with `GITHUB_TOKEN` do not trigger a separate Pages build. See [GitHub's Pages publishing documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).

## Theme and cycle browsing

The app has a shared light/dark switch. It follows the device preference until overridden, remembers the choice when storage is available, and updates already loaded and lazily loaded views. SVG exports use the selected theme.

Victory Cycles is a neutral display name for the familiar fan concept “circles of suck,” not a claim of originality. Add several teams using the dropdown or graph logos; removable chips show the selection. By default each selected team must occur on the same simple directed cycle. Small collections list all cycles found; beyond 50, the list retains the five longest and five shortest found. Searches stop at a time/work budget and explicitly distinguish complete enumeration from partial results. Precomputed longest-cycle proofs remain usable only when valid for the active scope and all required teams. Shortest-cycle proofs with several required teams require exhaustive search; otherwise they are labeled shortest found.

If no matching cycle is found, one selected team shows its one-hop opponents. Two selected teams show a shortest path through played matchups in either direction, retaining actual win arrows. More selections combine shortest paths from the first selected team. If no connection exists, immediate opponent networks are shown with an explanation. A bounded search finding nothing does not claim that a cycle cannot exist.

## Game-by-game Elo

`cfb/elo.py` implements season-local win/loss Elo using `E_home = 1 / (1 + 10 ** ((R_away - R_home) / 400))`, then `delta = 32 * (actual - E_home)`. Add delta to the home rating and subtract it from the away rating. Actual is 1, 0.5, or 0 for a home win, tie, or loss. Each season resets all teams to 1500; no home advantage, point-margin factor, or previous-season carryover is used. These are project choices, using the [standard Elo equations](https://www.stat.cmu.edu/cmsac/football/2-elo-intro.html).

`scripts/build_elo.py` reads the normalized completed-game archive and the imperialism timeline, then writes deterministic `data/team_elo.json.gz`. The archive includes source SHA-256, model parameters, pre/post values after every game, and week-end snapshots, using all available games across divisions. The source coverage is broader in later years; this is not a claim of a complete all-divisions schedule for every season. Ratings update at full precision; saved values are rounded to three decimals and displayed to one decimal. Equal kickoff times are ordered by game ID. Rebuilding from results avoids double-counting on repeated refreshes and replays corrections through subsequent games.

Within each season, `team_ids` determines the ordering of the `frames[].ratings` arrays. `games[]` has `home_id`, `away_id`, `before: [home, away]`, and `after: [home, away]` for every completed game. Browser frames contain an `elo` map keyed by team ID for FBS teams and their opponents. Browser game records contain winner/loser pre/post Elo; these are game-time values, while a logo ring shows the rating at the end of the selected week. Identity metadata in `teams.json` remains independent of season-dependent ratings.

The ring scale is computed across the entire selected FBS or FBS-plus-opponents scope at that week, never just the displayed cycle or neighborhood. Red is the lowest, green the highest, and amber is the midpoint (or every team if all ratings are tied). An outer selection outline is separate from the Elo ring. The tooltip and accessible node label provide numeric Elo, so meaning is not conveyed by color alone. Exports preserve the rings and print their rating range.

## Playoff Predictor

The current predictor covers 2026 and uses the existing offline builder, worker, scenario controls and schedule sources. Predictive SP+ power (with an identified Elo fallback/comparison) is separate from objective Poisson-binomial Strength of Record selection. SP+ remains fixed in each simulated season. Objective ranks, résumé explanations, SOS, projected records, separate bid types and bye probabilities are available; simulations default to 50,000. National selection and unresolved conference ties are deterministic. Complete conference tiebreaker sequences remain a flagged approximation. Old Elo playoff-elimination bounds are disabled for objective selection.

See [the complete objective model and operating instructions](objective-predictor.md) for architecture, modified files, credential configuration, weekly SP+ snapshots, refresh commands, calibration/held-out evaluation, ranking rules, qualification, performance, tests and limitations. It supersedes the original Elo-based selection methodology. The old pure Elo projection remains exported only as a comparison/test baseline.

## Static deployment and schedule worker

Playoff Predictor is the first/opening tab. Explicit `#imperialism`, `#circles`, and `#predictor` links remain supported. `.github/workflows/update-results.yml` combines scheduled schedule/result refresh, build validation, snapshot commits, and Pages publication; all runs check the weekly SP+ cache server side, while manual/scheduled runs additionally refresh schedules and results first. Only `build/site` is uploaded as a Pages artifact. The deploy job requires the successful build and uses the `github-pages` environment with GitHub's built-in Pages/OIDC permissions.

`cfb/schedules.py` handles provider normalization and semantic merging. Known scores cannot be rolled back by stale mirrors or unfinalized feeds; authoritative ESPN finals can correct scores. Future kickoff changes, cancellations, and newly announced postseason matchups are imported. Schedule feeds are checked for regular and postseason games for all current FBS members; daily scoreboards include FBS, FCS, Division II, and Division III. Empty postseason feeds are valid before pairings are announced. Completed records without scores are not invented, and future-dated finals cannot leak into observed snapshots. The current-season primary schedule continues to be a Parquet file with the same audited manifest.

No input files are changed until all required live downloads and merges succeed. Meaningful changes archive the old base and source responses, write the new schedule and checksums, set `build_pending`, and run the shared build. A successful build clears that flag. No-op retries still rebuild when pending, preventing an interrupted local run from stranding an outdated app. GitHub failures before the deployment job do not replace the last published version.
