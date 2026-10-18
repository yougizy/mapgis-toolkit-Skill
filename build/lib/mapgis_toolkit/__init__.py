"""mapgis-toolkit —— 逆向 MapGIS 10 文件格式的工具库。

模块:
    geometry  MapGIS 几何二进制编解码(mpshape)
    shp       ESRI Shapefile 读写(纯标准库)
    hdb       MapGIS 地理数据库(.hdb,SQLite)建库/写入/读取/体检
    mapx      地图文档(.mapx,XML)生成
    layout    .mapx 版面元素(图廓/地图框/文字/指北针)
    colors    颜色编码与颜色库索引
    cli       命令行入口
"""

__version__ = "0.2.0"

from . import (geometry, shp, hdb, mapx, layout, colors, geojson, ops,
               color_probe, batch, style, raster, network, topology,
               annotation, three_d)  # noqa: F401

__all__ = ["geometry", "shp", "hdb", "mapx", "layout", "colors",
           "geojson", "ops", "color_probe", "batch", "style",
           "raster", "network", "topology", "annotation", "three_d",
           "__version__"]
