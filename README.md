# mapgis-toolkit

**English** | [简体中文](README.zh-CN.md)

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-62%20passed-brightgreen.svg)](tests/)

**Read, write, inspect and build MapGIS 10 `.hdb` databases and `.mapx` map documents from Python — without MapGIS Desktop, GDAL, or any proprietary runtime.**

MapGIS is a widely used GIS platform in China, but its desktop application exposes no scripting API. This project reverse-engineers its file formats so that data conversion, validation and map generation can be automated:

- `.hdb` — a SQLite database holding feature classes, annotation classes, raster catalogs and metadata
- `.mapx` — a gb2312-encoded XML map document describing layers, symbols, labels and layout elements

All formats were derived from MapGIS 10.8 sample data and validated byte-for-byte where possible.

> This is an independent, community project. It is **not** affiliated with or endorsed by Zondy Cyber / MapGIS.

## Features

| Area | What you get |
|---|---|
| **Geometry** | Point / polyline / region binary codecs, Douglas–Peucker simplification, centroid |
| **Databases** | Create databases from a template, feature-class CRUD, attribute and spatial queries, statistics, integrity inspection and repair |
| **Interchange** | Shapefile ↔ HDB ↔ GeoJSON, plus batch directory conversion |
| **Map documents** | Layer generation with symbols and labels, simple themes, layout elements (neatline, map frame, text, north arrow) |
| **Annotation classes** | Read / write `acls` annotation features (text, position, font size, color) |
| **3D** | Decode / encode 3D polygon geometry (`mptype` 8/9) |
| **Raster** | Metadata, statistics, clipping, resampling, mosaicking, raster calculator (rasterio) |
| **Analysis** | Clip, buffer, intersect, dissolve, projection (shapely / pyproj); network analysis (networkx); topology checks |
| **Interfaces** | 27 CLI subcommands · Python library · 36 MCP tools |

## Install

```bash
git clone https://github.com/you/mapgis-toolkit-Skill.git
cd mapgis-toolkit-Skill
pip install -e .
```

Optional extras:

```bash
pip install -e ".[mcp]"     # MCP server
pip install -e ".[geo]"     # shapely + pyproj
pip install -e ".[raster]"  # rasterio + numpy
pip install -e ".[net]"     # networkx
pip install -e ".[color]"   # Pillow (color card probing)
pip install -e ".[all]"     # everything
```

Requirements: Python 3.9+. The core format codecs use only the standard library.

## Quick start

### Command line

```bash
python -m mapgis_toolkit.cli --help

# inspect a database
python -m mapgis_toolkit.cli info    data.hdb
python -m mapgis_toolkit.cli inspect data.hdb

# convert
python -m mapgis_toolkit.cli export  data.hdb  rivers out.shp
python -m mapgis_toolkit.cli import  data.hdb  rivers rivers.shp --type Line

# query
python -m mapgis_toolkit.cli query   data.hdb  cities --where NAME=南昌市
python -m mapgis_toolkit.cli stats   data.hdb  cities --field AREA

# repair
python -m mapgis_toolkit.cli repair  data.hdb
```

### Python

```python
from mapgis_toolkit import hdb, shp

# create a database from any MapGIS empty database template
con = hdb.new_database("template.hdb", "out.hdb")

shape_type, features = shp.read_shp("rivers.shp")
hdb.add_feature_class(con, "rivers", "Line", features,
                      fields=[("NAME", "TEXT", 0, "Name")], srid=8)

report = hdb.inspect(con)
print(report["ok"], report["problems"])
con.close()
```

### Building a map document

```python
from mapgis_toolkit import layout, mapx

layer = mapx.make_layer(
    template_xml, "cities", "gdbp://MapGISLocalPlus/out/sfcls/cities",
    fill={"fillclr": 15}, label_expr="NAME", label_visible=True,
)

page = layout.layout(210.0, 297.0, "\n".join([
    layout.polygon_element(10, 20, 200, 278, fillclr=9, outpenw=0.7),
    layout.text_element("My map", 16, 285, height=8, color=6),
    layout.map_element(mapx.DEFAULT_GUID, "main", (14, 30, 196, 270),
                       (113.5, 24.4, 118.5, 30.1)),
]))

mapx.build_mapx("out.mapx", "My map", layer, (113.5, 24.4, 118.5, 30.1),
                layout_xml=page)
```

A complete end-to-end example (a provincial administrative map with 11 prefecture-level divisions, rivers, lakes, legend and neatline) lives in [`examples/build_jiangxi_mapx.py`](examples/build_jiangxi_mapx.py).

### MCP server

```bash
python -m mapgis_toolkit.mcp_server
```

Client configuration:

```json
{
  "mcpServers": {
    "mapgis-toolkit": {
      "command": "python",
      "args": ["-m", "mapgis_toolkit.mcp_server"],
      "env": { "PYTHONPATH": "<path-to-repo>/src" }
    }
  }
}
```

The server exposes tools for database inspection, queries, import/export, annotation and 3D reading, topology checks, raster operations, batch conversion, and map-document generation.

## Format notes

The reverse-engineered details are documented for anyone who wants to extend the toolkit:

- [`docs/format-hdb.md`](docs/format-hdb.md) — table layout, geometry encoding, metadata
- [`docs/format-mapx.md`](docs/format-mapx.md) — document structure, layers, symbols, layout
- [`docs/capability-map.md`](docs/capability-map.md) — coverage matrix against 290 help pages / 1317 feature headings

## Known limitations

- **Color indices.** `fillclr` / `iclr` accept color-library indices only; true-color values render black. The base 256-color table is stored encoded and cannot be decoded from `Pcolor.lib`. Use the color-card workflow (`color-card` → export PNG → `color-probe`) to build a calibration table.
- **Legends.** Official samples contain no legend XML; legends are drawn with basic `PolygonElement` primitives.
- **Saving in MapGIS.** Re-saving a generated `.mapx` in MapGIS rewrites `geometryType` from the database and may clear layout elements. Generate with the toolkit and treat the file as read-only.
- **Themes.** `MultiClassTheme` is ignored in some builds; splitting categories into separate feature classes with a `SimpleTheme` is more reliable.
- **Runtime features.** Service publishing, map tiles, interactive editing and 3D rendering depend on the MapGIS runtime and are out of scope.

## Contributing

Issues and pull requests are welcome. Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) first.

```bash
python -m unittest discover -s tests
```

Some tests require a MapGIS empty database as a template; set `MG_TEMPLATE` to its path, otherwise those tests are skipped.

## License

[MIT](LICENSE)
