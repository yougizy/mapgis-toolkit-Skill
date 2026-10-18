# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- GitHub issue templates and pull request template
- CI workflow (Linux/Windows × Python 3.9–3.12) and package build job
- `py.typed` marker and `MANIFEST.in`

## [0.2.0] — 2026-10-17

### Added
- **Annotation classes (`acls`)** — create, read and delete annotation feature classes
  (`mpaN` tables, `mptype=0`, `mplocate_arr` point geometry)
- **3D polygon geometry** — decode/encode `mptype` 8/9 (`-22` header, `-21` part markers)
- **GeoJSON** — bidirectional read/write for Point, LineString, Polygon, MultiPolygon
- **Geoprocessing** — clip, buffer, intersect, dissolve and projection (shapely/pyproj)
- **Raster** — metadata, statistics, clipping, resampling, mosaicking, raster calculator (rasterio)
- **Network analysis** — graph building, shortest path, connected components, largest component (networkx)
- **Topology checks** — invalid geometry, overlaps, gaps, dangles, duplicates
- **Batch operations** — directory-wide Shapefile ↔ HDB conversion and multi-map generation
- **Field operations** — `add_field`, `drop_field`, `update_features`
- **Line simplification** — Douglas–Peucker (`geometry.simplify`)
- **Layer style extraction** — `style.styles_from_mapx`
- **Color tooling** — extended palette decoder (1640 colors), reference color mapping,
  calibration workflow (`color-card` → PNG → `color-probe`)
- **MCP server** expanded to 36 tools; CLI expanded to 27 subcommands

### Changed
- Project renamed to `mapgis-toolkit-Skill`
- Tests expanded from 22 to 62
- Documentation reorganized for open-source release (English + Chinese)

### Fixed
- `subtype` written per geometry type (point 1 / line 2 / face 3) — fixes layers that rendered blank
- Layer ordering in `.mapx` (later subnodes draw on top)
- Read-only databases in `Program Files` opened with `?mode=ro&immutable=1`

## [0.1.0] — 2026-10-17

### Added
- HDB geometry codecs (point / polyline / region) with byte-level verification
- Shapefile read/write
- HDB database creation, feature-class CRUD, inspection
- `.mapx` generation: layers, symbols, labels, layout elements
- Index color card generator
- Initial CLI and MCP server

[Unreleased]: https://github.com/you/mapgis-toolkit-Skill/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/you/mapgis-toolkit-Skill/releases/tag/v0.2.0
[0.1.0]: https://github.com/you/mapgis-toolkit-Skill/releases/tag/v0.1.0
