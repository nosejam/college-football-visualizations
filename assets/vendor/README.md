Browser dependencies are pinned and embedded in the generated HTML so it works offline:

- Plotly.js 3.3.0, from https://cdn.plot.ly/plotly-3.3.0.min.js (MIT; see `plotly-LICENSE`).
- D3 7.9.0, from https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js (ISC; see `d3-LICENSE`).
- Plotly's `usa_110m` TopoJSON basemap, from https://cdn.plot.ly/un/usa_110m.json, used for the Albers USA projection's state outlines.

Map logic uses the pinned Plotly SVG geo projection to align logo centers and boundaries with county fills. If Plotly is upgraded, run `scripts/check_map.py` to check that alignment and containment still hold. Source URLs and content hashes are recorded in `data/sources/geography/manifest.json`.

Imperialism additionally uses TopoJSON client 3.1.0 in the browser and server 3.0.1 in the offline Node build. Both are ISC licensed; see `topojson-client-LICENSE` and `topojson-server-LICENSE`. They preserve shared county borders and avoid embedding a complete copy of region geometry for every season. Run `scripts/check_imperialism.py` when upgrading these dependencies.
