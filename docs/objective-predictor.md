# Objective playoff predictor (model `objective-sor-1`)

The predictor asks which teams earn qualification under a declared mathematical résumé policy and the 2026 CFP format. It does not predict committee votes. Predictive power and résumé achievement are separate. The Imperialism and Victory Cycles pages retain their existing Elo calculations.

## Architecture and changed files

- `cfb/ratings.py`: CFBD response validation, explicit alias matching, snapshot freshness and scale metadata.
- `scripts/refresh_ratings.py`: authenticated server-side download, weekly request throttle, atomic cache replacement, timestamped archives, failure preservation.
- `data/sources/ratings/aliases.json`: explicit provider-name → canonical team ID overrides. Other names use unambiguous catalog aliases, never fuzzy matches. CFBD `/ratings/sp` supplies names, not stable IDs. Unknown names are reported; ambiguous names cannot silently choose an identity.
- `scripts/calibrate_predictor.py`, `data/sources/ratings/calibration.json` and `calibration.svg`: chronological pregame baseline fitting, validation, held-out Brier/log loss and reliability bins/plot. Recalibration is explicit, not part of the daily worker.
- `data/sources/predictor/objective_model.json`: fixed reference strengths, near-tie tolerance and model version.
- `data/sources/predictor/rules_2026.json`: season-specific qualification data and disclosed conference approximations.
- `scripts/build_predictor.py`: embeds only saved public ratings, calibration and neutral-site flags in the offline page; coverage is included in `data/predictor_coverage.json`.
- `maps/predictor-model.js`: rating-provider abstraction, cached probabilities, log-space Poisson-binomial SOR, deterministic national ranking, objective Monte Carlo simulation. The old Elo selection model remains exported as `projectLegacy` for reproducible comparisons; the UI Elo choice changes predictive ratings while keeping objective selection.
- `maps/predictor.js` and `predictor-template.html`: rating selector, 2,000-run default, seed, separate power/résumé columns, bid/bye probabilities, team explanations, scheduled title-game controls, warnings and snapshot labels.
- `.github/workflows/update-results.yml`: server-side weekly ratings check before the existing daily results/build/deploy pipeline. Only the refresh step receives the secret.
- `scripts/compare_predictor.cjs` and `data/predictor_comparison.json`: seeded current-season SP+/objective, Elo/objective and original Elo-selection forecasts, including expected places by conference and top qualification probabilities.
- `tests/test_ratings.py`, `tests/test_objective_predictor.cjs`, `scripts/check_predictor.py`: data/provider, probability, ranking, qualification, simulation and browser checks. Generated `index.html` incorporates these changes.

## Credentials and updates

Set `CFBD_API_KEY` in the environment used to run Python. On GitHub, use repository **Settings → Secrets and variables → Actions → New repository secret**, named `CFBD_API_KEY`. Never use a frontend environment variable, paste a key into HTML, or commit it. Surrounding whitespace and an optional Bearer prefix are normalized; invalid internal whitespace is rejected without printing the value. No key or authenticated request header is saved in snapshots.

```bash
.venv/bin/python scripts/refresh_ratings.py --year 2026
.venv/bin/python scripts/build.py
```

The existing daily Action calls the refresh function, but an SP+ download occurs only when the cache is at least seven days old. This is one request to `GET https://api.collegefootballdata.com/ratings/sp?year=2026`, not one request per team. There are no browser or simulation API calls. `--force` bypasses the seven-day throttle for an explicit refresh; use within your subscription's limits. The manual GitHub workflow also offers a `force_ratings` checkbox. Authentication failures, access restrictions, 429 responses and network/data errors preserve the old snapshot, with no immediate retry storm. API error bodies and credentials are not logged. The cached snapshot is stale after ten days and the UI explicitly falls back to Elo. A lower-coverage response cannot replace a more complete cached response; responses covering less than 80% of FBS are rejected.

Snapshots live in `data/sources/ratings/sp_2026.json` and `snapshots/2026/<UTC timestamp>.json`; they include season, source, retrieval time, overall/component ratings, raw response hash, mapped/missing coverage and unmatched names. The endpoint has **no week parameter**. A current snapshot is never passed off as historical pregame data. Earlier week selections use Elo unless the embedded snapshot actually predates that week. This first implementation embeds the latest snapshot; archives enable a future historical snapshot picker. A successful ratings refresh forces a rebuild even when game results are unchanged.

References: [CFBD ratings endpoint](https://api.collegefootballdata.com/api/ratings), [Connelly's point-scale description](https://www.espn.com/college-football/story/_/id/45842676/college-football-2025-breakthrough-bounce-back-teams).

## Game model and calibration

For SP+-rated opponents, `margin = SP_A − SP_B + site × HFA`, where site is +1 for home, −1 for away, 0 for neutral. SP+ overall is a point-based strength measure; component fields are not summed or substituted for the overall rating. Ratings must be finite and within a broad sanity bound (±100); the point-unit interpretation is recorded with its source. SP+ values remain fixed throughout a simulated season. A forced result changes records, conference standings, head-to-head and SOR, not SP+.

The saved historical data lack archived pregame SP+. **The SP+ mapping is therefore an unvalidated point-scale transfer from an independently fitted pregame Elo baseline.** No final-season SP+ ratings were downloaded or used to evaluate earlier games. This limitation is prominent in the UI; current SP+ forecasts must not be advertised as historically calibrated SP+ probabilities.

Training uses 5,162 FBS-v-FBS games from 2016–2022, with pregame, season-reset Elo computed chronologically from preceding results only. Fit actual home scoring margin on pregame Elo difference and a non-neutral home indicator, obtaining 0.16109 points/Elo, HFA 4.0766 points and residual sigma 18.9680. Compare `normalCDF(margin/sigma)` against logistic regression fitted to the same pregame Elo difference/site inputs. Select by 2023 validation log loss, and report untouched 2024–2025 test games (1,606 games). Logistic won validation. Its SP+ mapping uses its Elo slope divided by the fitted points/Elo scale; HFA remains the fitted point adjustment. This transfer has no SP+-specific accuracy guarantee.

Held-out scores (lower is better):

| Model | Brier | Log loss |
|---|---:|---:|
| Calibrated pregame Elo logistic | 0.2104 | 0.6069 |
| Calibrated pregame Elo normal | 0.2107 | 0.6077 |
| Original Elo probability | 0.2280 | 0.6480 |

`calibration.json` contains training boundaries, parameters, sample counts and reliability bins; `calibration.svg` plots held-out reliability. Regenerate with `scripts/calibrate_predictor.py`; matplotlib is an optional development-only dependency for the figure. No prediction clipping is applied. A tiny numerical floor used to evaluate log loss does not alter predictions. Opposite-side probabilities sum to one. First-round CFP games use the higher seed's home field; later rounds are neutral. Conference title sites use supplied venue flags or configured hosting policy.

Missing SP+ teams are never assigned an average SP+ rating. A game missing either SP+ rating uses calibrated Elo explicitly. The UI reports how many selection-schedule matchups have missing SP+. Reference-team SOR uses the corresponding Elo reference for a missing opponent. Lower-division Elo and mixed-source comparisons are extrapolations, not independently validated. Elo comparison predictions update Elo after each future game, retaining the original K=32 update. SOR opponent strengths remain fixed at the chosen week's snapshot for both providers.

## Strength of Record and ranking

For each opponent, compute a fixed contender reference's win probability at the evaluated team's venue. The declared reference is **SP+ +20 points**, with **Elo 1625** for Elo opponents (approximately +20 points using the fitted scale). These are policy/model assumptions, not parameters fitted to reproduce a committee. They remain unchanged across scenarios. The `modelConfig` API and JSON configuration allow explicit sensitivity comparisons; changing reference strength is not hidden in a user pick.

Build the Poisson-binomial win distribution using log-space dynamic programming:

`D_new[k] = (1−p)D_old[k] + pD_old[k−1]`.

Then `SOR = −ln(sum(D[k] for k >= achieved wins))`. Log-sum-exp avoids underflow for tiny tails. This assumes game independence conditional on fixed ratings. Precompute tails for each team's scheduled regular season; cache each possible added championship opponent/site. Only indexing by simulated wins and deterministic ranking is needed per simulation. Conference championships count in the final résumé; CFP games do not count toward selection. Games after Selection Day are excluded. SOS difficulty = one minus the reference's mean win probability; higher is harder. Quality wins use the independent top-25 power list; weak losses are losses to lower-power opponents. These fields are explanatory, not weighted ranking bonuses.

Sort by SOR, form an anchored near-tie group within `ln(1.01)` of its highest score (tail probability ratio within 1%), and order that group by SOS difficulty, within-group head-to-head win differential, predictive power, then canonical ID. Anchoring makes the order transitive. The 1% policy avoids letting insignificant numerical differences dominate; it is **not empirically validated**, and is configurable. Tests compare references +15/+20/+25 and tolerances 0/1%/5%; probability totals and determinism must hold, but rankings need not be invariant. There is no blanket conference bonus or arbitrary weighted résumé formula.

Objective rank is the deterministic completed-plus-fixed-results résumé at the selected week. Raw SOR rank is shown separately. Projected national rank and W–L average complete simulations through Selection Day, including title games where applicable. They are not a ranking constructed from average SOR. Team-name explanations include the current scenario résumé, head-to-head outcomes, quality wins, weaker-opponent losses, conference wins and projected title participation/results.

## Qualification and uncertainty

The 2026 data specify 12 places: four designated conference champions, highest-ranked eligible G6 **team** (not necessarily its champion), and Notre Dame if objective top 12, then highest remaining objective ranks. Automatic and at-large events are mutually exclusive and sum to total qualification. Selected teams are seeded in objective rank order; automatic qualifiers below national rank 12 are at the bottom. Four byes and fixed bracket pairings; no rematch avoidance. [Official 2026 format](https://collegefootballplayoff.com/sports/2024/5/29/12-team-format).

Conference participants are simulated from conference records, not overall record or a preset matchup. Existing Sun Belt divisions and ACC alternate-schedule equivalence are retained. **Complete official conference tiebreaker sequences are not implemented.** Every tied qualifying slot records a conference warning; the existing head-to-head/common-opponent/opponent-conference-percentage approximation then uses a stable ID instead of a lottery. Results affected by these approximations remain explicitly conditional on them. Full conference books, unscheduled Pac-12 flex matchups, and independent eligibility-ban verification remain limitations. Only 2026 predictor rules were previously supported; historical map/cycle seasons are preserved, but hypothetical historical playoff formats are not added.

Simulations condition on all completed games and fixed future results, not probability multipliers. Scheduled championship picks apply only if those exact participants reach the title game. A user pick cannot invent a championship participant. Common deterministic per-game draws prevent unrelated games' random numbers from shifting when a pick changes. Results are reproducible for a fixed seed, model configuration, rating snapshot and schedule. The worker remains cancellable and supplies progress every 500 trials; 2k/5k/20k/50k runs are available, with 2,000 selected by default. The table defaults to 11 columns, with persistent optional columns and an expanded view; model notes are collapsed below it.

Conference elimination retains exact optimistic standings feasibility. Old Elo ranking bounds **do not prove SOR elimination** and are disabled in objective selection. When the regular season and all title games are complete, the selection is deterministic, allowing verified 0%/100% qualification. When at most ten modeled regular/title outcomes remain uncertain, a separate exhaustive enumeration (up to 1,024 completions) verifies qualification or elimination, including varying title participants and conditional picks. It uses every binary completion for proof only, not equal-weighted probability estimation; draws with zero probability are conservatively included. For larger unfinished seasons, general SOR proofs are not implemented: zero/all Monte Carlo hits show `~0%`/`~100%`, not mathematical status. Tooltips give an approximate sampling interval; they do not cover model uncertainty. No random committee decisions are injected.

## Validation

```bash
.venv/bin/python -m unittest discover -s tests -v
node tests/test_predictor_model.cjs
node tests/test_objective_predictor.cjs
node tests/test_circles_algorithms.cjs
node scripts/compare_predictor.cjs 2000 --sensitivity
.venv/bin/python scripts/build.py
.venv/bin/python scripts/check_predictor.py
.venv/bin/python scripts/check_visualizations.py
```

Tests cover parsing, explicit/ambiguous mappings, missing/invalid/stale snapshots, HTTP errors/cache preservation/request throttle, neutral/home/complementary probabilities, held-out calibration, stable log tails, schedule/record comparisons, reference/tolerance sensitivity, actual and forced results, frozen SP+, 2026 bid/seeding/Notre Dame/nonchampion G6 cases, probability conservation and deterministic simulation. Existing Elo and graph tests remain in place. Browser checks exercise scenario mirroring/conflicts, sorting, rating switching, explanation panels, mobile scrolling, independent tabs and offline operation.

Validation recorded 2026-10-28: live CFBD retrieval matched **138/138 FBS teams**, with the national-average aggregate excluded. Both automatic weekly-cache and explicit forced-refresh cloud paths were exercised. A 50,000-run offline browser forecast plus pick/rating-switch checks took about 14 seconds on the development machine; performance varies by device. The saved comparison uses 2,000 runs per model and 1,000 per reference/tolerance sensitivity case; it is illustrative scenario output, not historical predictive validation.

Final validation: **37 Python tests passed**; the existing Elo/selection and graph suites, the new objective predictor suite (including bounded exhaustive proofs), and both predictor/tab browser regression scripts passed. The offline browser also verified fixed SP+ across forced outcomes, retained picks across method switches, the then-default 50,000 runs, and no runtime network requests or page errors.

Display update (2026-10-31): default 2,000 runs; a compact screen-filling table with 11 default columns, remembered optional columns, an expanded view, and model explanations collapsed below the table. Browser regression checks cover 20+ visible desktop rows, column selection/reset/persistence, expanded view, scenario controls and mobile overflow.
