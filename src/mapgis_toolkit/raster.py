"""栅格工具(基于 rasterio)。

功能:
    - 元数据查询(尺寸、波段、CRS、分辨率、范围)
    - 波段统计(min/max/mean/std,可抽样)
    - 按范围/矢量裁剪
    - 导出为 PNG(可选)

依赖:`pip install rasterio numpy`
"""

from __future__ import annotations

import os
from typing import Optional, Sequence

try:
    import numpy as np
    import rasterio
    from rasterio.mask import mask as _rio_mask
    from rasterio.windows import from_bounds
except ImportError as exc:  # pragma: no cover
    raise ImportError("需要 rasterio:npm/pip install rasterio") from exc


class RasterError(RuntimeError):
    """栅格操作异常。"""


def info(path: str) -> dict:
    """栅格元数据。"""
    if not os.path.exists(path):
        raise RasterError("文件不存在: %s" % path)
    with rasterio.open(path) as ds:
        return {
            "path": path,
            "width": ds.width,
            "height": ds.height,
            "bands": ds.count,
            "dtype": ds.dtypes[0],
            "crs": ds.crs.to_string() if ds.crs else None,
            "resolution": list(ds.res),
            "bounds": list(ds.bounds),
            "nodata": ds.nodata,
        }


def stats(path: str, band: int = 1, sample_step: int = 1) -> dict:
    """波段统计;``sample_step`` > 1 时抽样以加速大图。"""
    with rasterio.open(path) as ds:
        data = ds.read(band, out_shape=(
            max(1, ds.height // sample_step),
            max(1, ds.width // sample_step)))
        arr = data.astype("float64")
        nodata = ds.nodata
        if nodata is not None:
            arr = arr[arr != nodata]
        if arr.size == 0:
            return {"band": band, "count": 0}
        return {
            "band": band,
            "count": int(arr.size),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
        }


def clip(path: str, out_path: str, bbox: Optional[Sequence[float]] = None,
         geojson_path: Optional[str] = None) -> dict:
    """裁剪栅格:``bbox`` 为 ``(xmin, ymin, xmax, ymax)``;或用 GeoJSON 掩膜。"""
    with rasterio.open(path) as ds:
        if geojson_path:
            import json
            from shapely.geometry import shape
            with open(geojson_path, "r", encoding="utf-8") as f:
                gj = json.load(f)
            geoms = [shape(feat["geometry"]) for feat in gj.get("features", [gj])]
            geoms = [g.__geo_interface__ for g in geoms]
            data, transform = _rio_mask(ds, geoms, crop=True)
            profile = ds.profile.copy()
            profile.update(height=data.shape[1], width=data.shape[2],
                           transform=transform)
        elif bbox:
            window = from_bounds(*bbox, transform=ds.transform)
            data = ds.read(window=window)
            transform = rasterio.windows.transform(window, ds.transform)
            profile = ds.profile.copy()
            profile.update(height=data.shape[1], width=data.shape[2],
                           transform=transform)
        else:
            raise RasterError("需要 bbox 或 geojson_path 之一")
        profile.update(driver="GTiff", compress="lzw")
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(data)
    return {"ok": True, "out": out_path, "height": data.shape[1],
            "width": data.shape[2]}


def export_png(path: str, out_png: str, band: int = 1) -> str:
    """单波段导出为 8 位 PNG(线性拉伸到 0-255)。"""
    from PIL import Image
    with rasterio.open(path) as ds:
        arr = ds.read(band).astype("float64")
        nodata = ds.nodata
        valid = arr[arr != nodata] if nodata is not None else arr
        if valid.size == 0:
            raise RasterError("波段全为 nodata")
        lo, hi = np.percentile(valid, 2), np.percentile(valid, 98)
        if hi <= lo:
            hi = lo + 1
        norm = np.clip((arr - lo) / (hi - lo) * 255, 0, 255).astype("uint8")
        Image.fromarray(norm).save(out_png)
    return out_png


def resample(src: str, dst: str, scale: float = 1.0,
             res: Optional[Sequence[float]] = None) -> dict:
    """重采样(按比例或目标分辨率)。"""
    with rasterio.open(src) as ds:
        out_h = max(1, int(ds.height * scale))
        out_w = max(1, int(ds.width * scale))
        if res:
            out_w = max(1, int(round(ds.width * ds.res[0] / res[0])))
            out_h = max(1, int(round(ds.height * ds.res[1] / res[1])))
        data = ds.read(out_shape=(ds.count, out_h, out_w),
                       resampling=rasterio.enums.Resampling.bilinear)
        profile = ds.profile.copy()
        transform = ds.transform * ds.transform.scale(
            ds.width / out_w, ds.height / out_h)
        profile.update(height=out_h, width=out_w, transform=transform)
        with rasterio.open(dst, "w", **profile) as out:
            out.write(data)
    return {"ok": True, "out": dst, "height": out_h, "width": out_w}


def reproject(src: str, dst: str, dst_crs: str) -> dict:
    """栅格投影转换。"""
    from rasterio.warp import calculate_default_transform, reproject as _rp
    with rasterio.open(src) as ds:
        transform, width, height = calculate_default_transform(
            ds.crs, dst_crs, ds.width, ds.height, *ds.bounds)
        profile = ds.profile.copy()
        profile.update(crs=dst_crs, transform=transform, width=width, height=height)
        with rasterio.open(dst, "w", **profile) as out:
            for band in range(1, ds.count + 1):
                _rp(source=rasterio.band(ds, band), destination=rasterio.band(out, band),
                    src_transform=ds.transform, src_crs=ds.crs,
                    dst_transform=transform, dst_crs=dst_crs,
                    resampling=rasterio.enums.Resampling.bilinear)
    return {"ok": True, "out": dst, "crs": dst_crs, "width": width, "height": height}


def mosaic(paths: Sequence[str], dst: str, resampling=None) -> dict:
    """把多个栅格镶嵌成一个(需坐标系一致)。"""
    from rasterio.merge import merge
    resampling = resampling or rasterio.enums.Resampling.nearest
    sources = [rasterio.open(p) for p in paths]
    try:
        arr, transform = merge(sources, resampling=resampling)
        profile = sources[0].profile.copy()
        profile.update(height=arr.shape[1], width=arr.shape[2],
                       transform=transform)
        with rasterio.open(dst, "w", **profile) as out:
            out.write(arr)
    finally:
        for s in sources:
            s.close()
    return {"ok": True, "out": dst, "inputs": len(paths),
            "height": arr.shape[1], "width": arr.shape[2]}


def calculator(expr: str, out_path: str, bands: Sequence[str],
               ref_path: str) -> dict:
    """栅格计算器:``expr`` 中的变量对应 ``bands``(如 ``"b1 - b2"``)。

    ``ref_path`` 提供尺寸/坐标系/仿射变换等元数据。
    """
    if not bands:
        raise RasterError("bands 不能为空")
    with rasterio.open(ref_path) as ref:
        arrays = {}
        for i, name in enumerate(bands):
            with rasterio.open(name) as ds:
                if ds.width != ref.width or ds.height != ref.height:
                    raise RasterError("参与计算的栅格尺寸不一致: %s" % name)
                arrays["b%d" % (i + 1)] = ds.read(1).astype("float64")
        try:
            result = eval(expr, {"__builtins__": {}}, dict(arrays, np=np))
        except Exception as exc:
            raise RasterError("表达式计算失败: %s" % exc) from exc
        profile = ref.profile.copy()
        profile.update(dtype="float32", count=1)
        with rasterio.open(out_path, "w", **profile) as out:
            out.write(np.asarray(result, dtype="float32"), 1)
    return {"ok": True, "out": out_path, "expr": expr}
