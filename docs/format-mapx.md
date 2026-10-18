# `.mapx` 地图文档结构笔记

`.mapx` 是 **gb2312 编码的纯 XML**,可直接生成。

## 1. 整体骨架

```xml
<?xml version="1.0" encoding="gb2312" standalone="no" ?>
<datacenter>
  <root filePath="..." title="地图文档" version="MapGIS K10">
    <subnode name="地图名" mapguid="..." LegendBoardGUID="..." LegendBoardID="0"
             type="Map" class="CreateMap@GisCartoPrj.dll">
      <viewExtent xmin="..." ymin="..." xmax="..." ymax="..."/>
      ...
      <subnode name="图层名" type="SFeatureLayer" geometryType="3"
               class="CreateGLayer@GisCartoPrj.dll">
        <url>gdbp://MapGISLocalPlus/库名/sfcls/要素类名</url>
        <subnode name="统一专题图" type="SimpleTheme"
                 class="CreateGTheme@GisCartoPrj.dll">
          <state>VISIBLE</state>
          <geomInfoType>3</geomInfoType>
          <geoInfo><regInfo ... fillclr="15" .../></geoInfo>
        </subnode>
        <label name="noname" type="SimpleLabel" class="CreateGLabel@GisCartoPrj.dll">
          <state>VISIBLE</state>
          <labelExpression>NAME</labelExpression>
          <geoInfo><annInfo height="11" iclr="6" .../></geoInfo>
        </label>
      </subnode>

      <layout class="CreateLayOut@GisCartoPrj.dll">
        <height>297</height><width>210</width>
        <elements>
          <element type="PolygonElement" ...>   <!-- 图廓 -->
          <element ... type="MapElement" MapGuid="..." MapName="...">
          <element type="TextElement" ...>
          <element type="NorthArrowElement" ...>
        </elements>
      </layout>
    </subnode>
  </root>
</datacenter>
```

## 2. 图层

| 属性 | 含义 |
|---|---|
| `geometryType` | **1 点 / 2 线 / 3 面** |
| `class` | `CreateGLayer@GisCartoPrj.dll` |
| `url` | `gdbp://<数据源>/<库名>/sfcls/<要素类名>`;HDB 用 `MapGISLocalPlus` |

**绘制顺序:subnode 写在后面的图层画在上面。**
常见的正确顺序(底 → 顶):面 → 湖泊 → 河流 → 界线 → 注记点。

`<state>` 必须为 `VISIBLE`。

## 3. 符号

| 几何 | 节点 | 关键属性 |
|---|---|---|
| 面 | `regInfo` | `fillclr`(填充色索引)、`patclr`(边框色)、`outpenw` |
| 线 | `linInfo` | `outclr`(**三值** `"r;g;b"` 形式的索引,单值会导致线不渲染)、`outpenw`(**三值**) |
| 点 | `pntInfo` | `id`(符号号)、`fillclr`、`scale` |

**颜色**:见 `colors.py`。`.mapx` 只接受**颜色库索引**;真彩色两种写法实测都会变黑。

## 4. 标注

```xml
<label name="noname" type="SimpleLabel" class="CreateGLabel@GisCartoPrj.dll">
  <state>VISIBLE</state>
  <labelExpression>NAME</labelExpression>
  <geoInfo><annInfo height="11" width="11" iclr="6" .../></geoInfo>
</label>
```

* `labelExpression` 只用字段名(不需要方括号)。
* `iclr` 是文字颜色索引。
* 面要素的标注默认落在面内;若想让标注落在驻地,可另建点图层承载标注。

## 5. 专题图

`MultiClassTheme`(分段)结构已验证,但**在部分 MapGIS 环境会被忽略**,
表现为所有要素回落 `defaultInfo`(默认填充色,常见为黑/白)。

**稳妥做法**:每个类别拆成独立要素类,各自用 `SimpleTheme` 单色。

## 6. 版面

* 坐标单位 **mm**,原点在**页面左下角**。
* `MapElement` 的 `LogicRect` 是页面位置,`viewRect` 是地理范围;
  两者比例应一致,否则地图会留白或被裁。
* A4 纵向 = `210 × 297`。
* 图例官方样本里没有,MapGIS 由「版面编辑 → 图例」生成,且生成后不再连接数据。

## 7. 其他坑

| 坑 | 现象 | 原因 |
|---|---|---|
| 写 `geometryType=3` 但库里 subtype=1 | 打开后图层变成点、不显示 | MapGIS 保存时按库内 subtype 回写 |
| 在 MapGIS 里保存过 `.mapx` | 版面元素丢失、图层类型被改 | 保存会重写文档 |
| `outpenw` 写单值 | 线完全不画 | 官方样本用三值 |
| 真彩色写进 `fillclr` | 全黑 | 只接受索引 |
| 模板图层没有 `SimpleTheme` | 图层无符号 → 黑 | 必须补一个符号节点 |
