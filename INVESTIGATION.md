# BiNavi Air Alignment Investigation

Working notes for the iGPSPORT BiNavi Air custom-map alignment bug. Not committed automatically — review before staging.

## The problem

Generated `.map` files load on the iGPSPORT BiNavi Air, but features render **offset ~1.7 km SW** vs reality (verified in Cruiser by comparing a feature's reported coordinates to Google Maps; the offset is in the `.map` file itself, not the device's renderer). Stock iGPSPORT maps work correctly on the same device. Tested area: Trentino-Alto Adige (tile `IT17002604203CB27X01D01C.map`).

Note: BiNavi Air is **not** in the upstream README's "Supported Products" list (BiNavi, iGS800, iGS630/S, BSC300/T). It may have a stricter or different parser.

## Repo state

- Remote: `https://github.com/TKlerx/igpsport-map-updater.git` (TKlerx fork, used because of resume support, adaptive RAM config, automatic `maps.csv` generation, multi-region blend logic, etc.)
- Working dir: `/home/tommasopasini/igpsport-map-updater` (WSL2, Ubuntu, 7.6 GB RAM, 10 cores)
- 6 Italian tiles in `input/` (Trentino, Veneto, Centro-Nord regions); sources in `download/` (`nord-est`, `nord-ovest`, `centro` regional PBFs); 6 generated outputs in `output/`.

## Test artifacts available now

| File | Provenance |
|---|---|
| `input/IT17002604203CB27X01D01C.map` | **Stock** iGPSPORT tile (writer `mapsforge-map-writer-0.16.Q`) |
| `output/IT17002605103CB27X01D01C_.map` | Generated with writer **0.27.0** (the offset-on-device build) |
| `output/IT17002605103CB27X01D01C.map` | Generated with writer **0.16.0** (proved bytewise-identical to 0.27 at tile bodies) |

`tmp/run_it17_osmium.log` has the last successful build log.

## Tools written during investigation

In `/tmp/` (not in the repo):

- `/tmp/dump_mapheader.py` — parses the Mapsforge `.map` file header (magic, version, bbox, projection, flags, tile size, zoom intervals, `created by`). Reliable.
- `/tmp/decode_first_poi.py` — finds the first non-empty tile and decodes its first POI. **Has a bug** in way / coord parsing — useful for header-level checks only.
- `/tmp/decode_way_at_tile.py` — decodes way at a specific tile (x, y). **Also produces wrong lat/lon** for way nodes (off by ~50 km, likely due to missing data-block prefix or encoding-flag handling). The bytewise comparison it enables, however, *is* reliable.

If we want a programmatic Cruiser substitute we need to debug the way parser. The Mapsforge binary format spec is at <https://github.com/mapsforge/mapsforge/blob/master/docs/Specification-Binary-Map-File.md>.

## Hypotheses tried

### H1: Zoom-interval mismatch — RULED OUT
Both stock and generated maps use `zoom-interval-conf=13,13,13,14,14,14`. The 1.7 km offset is roughly the size of a zoom-14 tile at 45°N, which suggested this, but headers match.

### H2: Mapsforge writer version evolution (0.16.Q stock → 0.27.0 generated) — RULED OUT BY BYTEWISE TEST
The single most important finding of the session.

- Generated with writer 0.27.0: tile (4350, 2900) body bytes `00780043000151068029526f7474656e627572676572706c61747a202d205069...`
- Generated with writer 0.16.0: tile (4350, 2900) body bytes `00780043000151068029526f7474656e627572676572706c61747a202d205069...`
- **Bytewise identical.** Output of 0.16.0 and 0.27.0 is the same for this input. Switching writer versions cannot fix the offset.

(Stock map at the same tile starts `00230014ffff5108200453533432...` — different OSM data, different way ordering, different content. Expected.)

### H3: Bbox / tile-grid origin mismatch — CONFIRMED 2026-05-14
Inheriting the stock-map bbox (H3(b)) reduced the on-device / Cruiser offset from ~1.7 km SW to **~3 m residual** (below Cruiser's DMS display precision). The bbox in the `.map` header is what the BiNavi Air uses to anchor its tile grid. Tile-aligned values from the GEOCODE decode are ~2.5 km W / ~1.1 km S of the bbox the stock maps were built with, and that shift propagates 1:1 to every rendered feature.

This is the only remaining structural difference between stock and generated:

| | Stock | Generated (baseline) | H3(a) drop --bounding-box |
|---|---|---|---|
| header bbox | `10.360, 45.655 → 12.500, 47.110` (hand-cropped, round) | `10.327, 45.645 → 12.524, 47.100` (tile-aligned from GEOCODE) | `9.195, 43.730 → 13.929, 47.100` (full nord-est extent) |
| span | 2.14° × 1.46° | 2.20° × 1.46° | 4.73° × 3.37° |

Baseline generated bbox is shifted **~2.5 km west, ~1.1 km south** of stock bbox (vectorially ~2.7 km SW). The reported on-device offset is ~1.7 km SW — same direction, similar magnitude. The renderer likely uses the header bbox to compute its tile-grid origin; a shifted bbox would produce a consistent geographic offset.

#### H3(a): Drop `--bounding-box` — ran 2026-05-14, 15m21s, exit 0
Result: bbox in header became the **entire regional-polygon extent** (~all of NE Italy: 9.20°-13.93° lon × 43.73°-47.10° lat), not the IT17 tile region. Without `--bounding-box`, Mapsforge derives the bbox from the post-polygon-clip data extent — and the `--bounding-polygon` is the nord-est region, not the tile. This is *not* a clean test of "tile-aligned vs not"; it's "tile-aligned vs huge."

Useful only if you want to know whether the renderer survives an oversized header bbox. For an isolated test, run H3(b).

#### H3(b): Inherit stock bbox — ran 2026-05-14, 10m04s, exit 0 — CONFIRMED
Implemented as a generic feature: `run.sh` exports `ORIGINAL_MAPS_DIR`; for each tile, `script.sh` looks for `$ORIGINAL_MAPS_DIR/$ORIGINAL_NAME` and, if it's a valid Mapsforge map, reads its header bbox via `misc/read_map_bbox.py` and uses that for `--bounding-box`. Falls back to the GEOCODE tile-aligned bbox if no stock map is present. Osmium pre-clip still keyed on GEOCODE.

Output header bbox (IT17): `10.360000, 45.655000 → 12.500000, 47.100050`. Three of four edges match stock exactly; the top edge is clamped to 47.100050 (vs stock 47.110000) because Mapsforge writes `min(--bounding-box, data_extent)` and the nord-est polygon doesn't reach 47.110°. The ~1.1 km strip this loses at the top of the tile is not worth widening the polygon for.

Cruiser verification (2026-05-14, three samples across the IT17 tile):

| sample area | cruiser | ground truth | delta dir | magnitude |
|---|---|---|---|---|
| Trento city  | 46.07037, 11.11418 | 46.07038812, 11.11419608 | SW | ~2.3 m |
| Val di Fiemme | 46.47611, 11.31488 | 46.47609098, 11.31488342 | NW | ~2.1 m |
| Bolzano area | 46.53291, 11.49069 | 46.53290675, 11.49059428 | E | ~7.3 m |

Directions scatter (SW / NW / E) and magnitudes vary 2-7 m — the signature of click-point disagreement between Cruiser and Google Maps, not a systematic map shift. A real residual offset would push every sample in the same direction with comparable magnitude. The 1.7 km SW offset is fully resolved; remaining differences are within click-jitter / display-rounding tolerance.

## Changes committed as part of the fix

1. **Line endings** — `.gitattributes` forces LF for `*.sh` so the WSL checkout (which has `core.autocrlf=true`) doesn't reintroduce CRLF and break `#!/bin/bash\r`.
2. **`POLY_FILES` → `POLY_GROUPS`** rename in `script.sh` (lines 87, 148, 580). Outer global array vs per-tile array collision. Pre-fix bug: on iteration 2+ the outer array got clobbered → empty `--bounding-polygon "file="` → osmosis `OsmosisRuntimeException`. Only the first tile in a multi-tile run got correct polygons. Real upstream bug.
3. **`curl -sL` → `curl -fsL`** on the Mapsforge jar download. Original silently writes a 9-byte "Not Found" body if the URL 404s. `-f` makes curl fail loudly.
4. **`osmium extract` pre-clip** before the osmosis call. Caches `download/{source-basename}-{TILE_GEOCODE}.osm.pbf` (mtime-invalidated). Falls back to the full PBF if `osmium` isn't installed. ~13 min total for IT17 vs ~3 h without — roughly 10-14× speedup. Requires `osmium-tool`.
5. **Stock-bbox inheritance** — `run.sh` exports `ORIGINAL_MAPS_DIR`; `script.sh` reads the matching stock map's header bbox via `misc/read_map_bbox.py` and uses it for `--bounding-box`. Fallback to the GEOCODE tile-aligned bbox if no stock map. **This is the alignment fix.**

## Side observations (not blocking)

- `MAP_WRITER_THREADS` only parallelizes the *tile-write* phase. The dominant cost (PBF scan, polygon clip, tag transform, node/way indexing) is single-threaded regardless. The big win is pre-clipping the PBF, which is what `osmium extract` now does.
- Stock iGPSPORT bboxes are hand-rounded (10.360, 47.110…) and **not** tile-aligned. They produce correct on-device rendering, so the BiNavi Air doesn't require tile-aligned bbox values.
- Top-edge clipping (47.100050 vs stock 47.110000 for IT17): caused by `min(--bounding-box, data_extent)` and the nord-est Geofabrik polygon stopping short of 47.110°. Loses ~1.1 km strip at the top. Closing it would require a wider `--bounding-polygon` source; not worth it.
- We don't know how iGPSPORT *computes* the round-number bbox. A future investigation could try to derive it from the GEOCODE alone, which would let the tool work without a stock map to inherit from.

## Useful commands

```bash
# Inspect a .map header
python3 misc/dump_mapheader.py input/IT17002604203CB27X01D01C.map output/IT17002605103CB27X01D01C.map

# Read just the bbox (used by script.sh)
python3 misc/read_map_bbox.py input/IT17002604203CB27X01D01C.map

# Logged rebuild via the wrapper (knobs at the top of runtest.sh)
./runtest.sh

# Plain rebuild of a single tile (resume mode skips the others)
rm -f output/IT17002605103CB27X01D01C.map
./run.sh input --resume

# Kill a runaway build
pkill -9 -f "mapsforge-map-writer"; pkill -9 -f "script.sh"; pkill -9 -f "run.sh input"
```

## Misc tile geometry notes

- Zoom 13: tile width ≈ 4.9 km at equator, ~3.5 km at 45°N. Tile height similar.
- Zoom 14: half that — ~1.7 km at 45°N. (Hence the original "zoom-14 tile" hunch for H1.)
- IT17 GEOCODE `3CB27X01D01C` decodes to: `MIN_LON_X=4331, MAX_LAT_Y=2877, LON_SPAN=50, LAT_SPAN=49` → tile grid x=[4331,4380] y=[2877,2925] at zoom 13.
- Trento city center (~46.07°N, 11.12°E) is at tile (4350, 2917) — well inside the IT17 bbox.
