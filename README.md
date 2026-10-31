# College Football Visualizations

[Open the website](https://nosejam.github.io/college-football-visualizations/) · [Source repository](https://github.com/nosejam/college-football-visualizations)

Open **[index.html](index.html)** in a browser. **Playoff Predictor is the opening tab**; direct links such as `#imperialism` and `#circles` still open the other views. The offline app includes an **Imperialism Map**, **Victory Cycles**, and **Playoff Predictor**, with independent views and week controls. The predictor currently covers the 2026 season. No server or installation is needed to use it.

The saved results currently cover 2016–2026 through **2026 Week 8 (October 24)**. The map starts each season with counties assigned to the nearest FBS main campus; winners take their opponents' land. The graph uses winner-to-loser arrows and finds cycles across as many teams as the selected results support.

## Ideas and attribution

These concepts are **not original to this project**. Football imperialism maps and “circles of suck” are established college-football fan traditions. The map is inspired by community work such as [RedditCFB’s imperialism maps](https://cdn.redditcfb.com/imperialism/FBS/archive/2026-10-18.png). **Victory Cycles** is this app’s name for the directed win cycles commonly called “circles of suck”; renaming the tab does not claim a new concept.

This project extends those ideas with interactive season/week selection, map exploration, selectable cycles, multiple required teams, game-by-game evidence, and offline use. A shared light/dark switch follows your device preference initially and remembers your choice when browser storage is available.

Cycle searches list all found results when there are 50 or fewer. Larger sets show the **five longest and five shortest found**, with overlaps listed once. The page distinguishes complete enumeration from bounded searches, where more cycles may exist. Add teams using the dropdown or logos; by default every selected team must belong to the same cycle. If none is found, one team shows its immediate opponents; two teams show their shortest played-game connection with actual winner-to-loser arrows. With more teams, the app joins shortest connections from the first selected team. Disconnected selections show immediate opponent networks and explain the missing connection.

## Elo ratings

Logo rings in Victory Cycles run from **red (lowest Elo)** through amber to **green (highest Elo)**. The legend uses all teams in the selected scope and week, so choosing a team or cycle does not rescale its color. Hover a logo for its rating; the proof panel also shows both teams’ ratings immediately after each listed game. Rings and their legend are included in SVG exports and work in both themes.

This project uses [standard win/loss Elo](https://www.stat.cmu.edu/cmsac/football/2-elo-intro.html), with these explicit choices: every team starts each season at **1500**, **K = 32**, scale **400**, a tie counts as **0.5**, and there are no home-field or score-margin adjustments. All available completed games, including opponents’ other games, are replayed in kickoff order, then game ID. Each team gains exactly the points its opponent loses. Years are calculated independently; ratings use only results available through the selected week. Coverage of lower divisions varies by year with the saved schedules.

`data/team_elo.json.gz` contains model parameters, pre/post ratings for every completed game, and weekly snapshots aligned to each season’s `team_ids`. It is rebuilt automatically with the app and daily result updates. Browser data also exposes `CFB_CIRCLES_DATA.seasons[year].frames[index].elo[teamId]`, and rendered nodes have `elo` and `eloColor` parameters.

## Playoff Predictor (2026)

The opening tab lists every FBS team and starts sorted by objective résumé rank. SP+ is the default predictive source when a current snapshot is available, with an explicit Elo fallback/comparison. Power rank predicts strength; Strength of Record evaluates achievement against each team's schedule. Columns include SOR, SOS, projected record/rank, conference title, automatic bid, at-large bid, total qualification, bye and championship probabilities. The default view shows objective rank, SP+ power, logo/name, four scenario controls and the three main probabilities. Use Columns to add other metrics; choices are remembered on this browser. The compact table fills the available screen, with an Expand table view. Model explanations are collapsed below it. Select a team name for its résumé explanation.

Future checkboxes fix actual matchups and the opponent's corresponding loss. Conflicting picks use the latest edit. Week changes clear picks; rating-method changes preserve them. SP+ stays fixed during simulations. Use 2,000–50,000 simulations (default 2,000) with a reproducible seed; the background worker remains cancellable.

Qualification follows the [2026 CFP format](https://collegefootballplayoff.com/sports/2024/5/29/12-team-format), using deterministic SOR rankings as its authority, without committee randomness or conference bonuses. Conference tiebreakers remain an explicitly flagged approximation. Sampled zero/all hits are not elimination/clinching proofs. The SP+ probability mapping is an **unvalidated transfer** from a chronologically tested pregame Elo baseline; historical pregame SP+ snapshots are unavailable.

[Full model documentation, API credentials, refresh commands, calibration results, tests and limitations](docs/objective-predictor.md).

## Project layout

| Path | Purpose |
| --- | --- |
| `index.html` | Generated, self-contained app to open or publish |
| `maps/` | Editable HTML templates and JavaScript |
| `cfb/` | Team lookup, game simulation, Elo, and cycle algorithms |
| `scripts/` | Fetchers, builders, and optional browser checks |
| `data/` | Team identities, results, geography, exports, and source provenance |
| `assets/` | Logos, vendored libraries, and license notices |
| `tests/` | Data and algorithm regression checks |
| `.github/workflows/` | Daily result update workflow |
| `docs/reference.md` | Detailed data sources, methodology, and interface documentation |

`build/` contains generated standalone pages when you rebuild. It and the local `.venv/` environment are ignored by Git. Only the combined `index.html` needs to be published; the app embeds its data and assets.

## Build or update

Use Python 3.11 and Node.js 24 for the same environment as the daily workflow:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# Offline rebuild from saved inputs:
python scripts/build.py

# Fetch newly completed results and rebuild:
python scripts/refresh_results.py
```

The refresh command needs no API key and leaves files unchanged when results have not changed. Refresh the browser after rebuilding. To also generate the original closest-campus map, run `python scripts/build.py --include-closest-map`; its standalone page is `build/closest-teams.html`.

## GitHub Pages and the scheduled data worker

The project is prepared for **GitHub Pages**, publishing only the self-contained app. `scripts/package_site.py` creates `build/site/index.html`, `.nojekyll`, and `version.json` (data timestamp, default tab, and app checksum). Source data, archives, and the local Python environment are not served by Pages.

[The workflow](.github/workflows/update-results.yml) deploys on pushes to `main`, runs the data worker daily at **13:17 UTC** (9:17 a.m. Eastern daylight / 8:17 a.m. Eastern standard), and supports **Actions → Refresh data and publish site → Run workflow**. The worker is a GitHub Actions job, not a browser worker or a separate paid service. No ESPN API key or personal GitHub token is required in repository secrets.

The worker downloads the current unified schedule, every FBS team's regular/postseason ESPN schedules, and recent all-division scoreboards. It imports new matchups, rescheduled kickoffs, cancellations, final scores, and score corrections while preserving verified results against stale inputs. Changed inputs are archived with checksums; JSON responses are gzip compressed. Semantic no-ops produce no data commit. The app rebuilds Elo, maps, cycles, and playoff projections, then runs all data and algorithm checks before the workflow commits changed data/app files and deploys the Pages artifact. A failed download, build, check, or push stops publication, leaving the previous live version available. An interrupted local build is marked pending and retried by the next refresh.

For another repository, enable **Settings → Pages → Source: GitHub Actions** and permit the bot's `contents: write` permission to push to `main`. The deploy job uses GitHub's built-in `pages: write` and `id-token: write` permissions. Deployment is part of the same workflow because bot commits made with `GITHUB_TOKEN` do not trigger another workflow. GitHub's schedule may run late, and inactive public repositories can have schedules disabled after 60 days; check the Actions tab if updates stop.

To run the worker locally, activate the environment and run `python scripts/refresh_results.py`; use `--force-build` to rebuild even with unchanged inputs. It targets the latest imported season, including the following January. A new season still needs its membership, predictor rules, and build year range reviewed before importing it; the job does not invent those policies.

## Validate

With the virtual environment activated:

```bash
python -m unittest discover -s tests -v
node tests/test_circles_algorithms.cjs
node tests/test_predictor_model.cjs
```

For optional UI checks, install `playwright` and `Pillow`, rebuild first, then run `python scripts/check_visualizations.py`, `python scripts/check_victory_features.py`, `python scripts/check_elo.py`, and `python scripts/check_predictor.py` with Chrome/Chromium installed. The latter covers light/dark persistence, multi-team cycles, result lists, and no-cycle network/path fallbacks. Separate check scripts cover the standalone pages; `check_map.py` also requires `--include-closest-map` during the build.

The [data and implementation reference](docs/reference.md) covers team aliases and IDs, logo sources, historical win/loss records, campus locations, county assignments, map rules, cycle guarantees, and all rebuild commands. Keep source data and licenses with the project: they support offline rebuilds and source-integrity checks. Logos remain the property of their owners.
