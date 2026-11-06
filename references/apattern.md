# .apattern — agent 时代的纸样文件

## 一句话

`.apattern` 就是 JSON，换了个后缀。一个款、一个码、一个文件。DXF-AAMA 还是生产交换格式（给工厂/CAD），`.apattern` 是 agent 的工作源头。两边各司其职。

## 为什么不用 DXF 当工作格式

DXF 是 CAD 时代的产物，卡 agent 的地方：

- **# 号不稳定**：加线、删刀口就重排（女装原型 v2→v3 只 4 个 # 留原位）。# 是 CAD 按创建顺序编的点位 ID，不是语义身份。
- **# 号没有语义**：#24 是什么？DXF 不知道。得靠用户口头定，再另存锚点文件。
- **几何和量度分家**：线段定义、锚点、量化、校验全是外挂文件，换个版本就得重新对。
- **缝份是隐含的**：净线和裁剪线是两条线，缝份值没存在文件里，得靠量。
- **没有校验**：袖山要不要等于袖笼、领长要不要短于领围，DXF 表达不了。

## 结构（v0.1）

```json
{
  "format": "apattern",
  "version": "0.1",
  "style": "男士165-96t-shirt",
  "size": "M",
  "units": "cm",
  "source": { "dxf": "source.dxf", "note": "BUYI-TECH DXF-AAMA R12" },
  "lineage": { "derived_from": "tshirt-165-96 v0.1", "changes": ["半片改整片", "缝份 1.0 改 0.8"] },
  "pieces": {
    "front": {
      "label": "前片",
      "material": "面料",
      "quantity": 1,
      "symmetric": true,
      "sa": { "default": 0.8, "hem": 2.0 },
      "points": {
        "armpit_l": [-73.28, 4.03],
        "neckline_c": [-48.78, 19.05]
      },
      "edges": {
        "neckline": {
          "points": ["shoulder_tip_l", "neckline_c", "shoulder_tip_r"],
          "xy": [[-58.68, 29.06], "...", [-38.88, 29.06]]
        }
      },
      "segments": {
        "chest":    { "points": ["armpit_l", "armpit_r"], "method": "straight", "length": 49.00 },
        "neckline": { "points": ["shoulder_tip_l", "neckline_c", "shoulder_tip_r"], "method": "outline", "length": 31.35 }
      },
      "grainline": [[-48.78, -20.0], [-48.78, 20.0]],
      "notches": []
    }
  },
  "checks": [
    { "rule": "sleeve.cap == front.armhole + back.armhole", "value": 50.80, "expect": 50.75, "diff": 0.05, "pass": true }
  ]
}
```

## 字段说明

- **`format` / `version`**：`apattern` / `0.1`。格式自己带版本，以后改格式先升版本。
- **`style` / `size`**：款名、码。单码一个文件，放码另算。
- **`units`**：固定 `cm`。坐标是**块内坐标**（片自己的坐标系，不是 DXF 排版里的位置），所以排版怎么动，坐标不变。
- **`source`**：这个纸样从哪个 DXF 导来的。
- **`lineage`**：从哪版来、改了什么。版本沿革写在文件里，不靠文件夹名猜。
- **`pieces`**：片，键是稳定 ID（`front`、`back`、`sleeve`、`collar`……），改版也不变。
  - **`label`**：中文名（前片）。
  - **`material` / `quantity`**：面料/里料，裁几片。
  - **`symmetric`**：左右对称的片，只定一边即可（左、右袖笼是一样的）。
  - **`sa`**：缝份（cm）。`default` 是通用值，`hem` 这类具名值是那条边的缝份。
  - **`points`**：有名有姓的点（`armpit_l`、`neckline_c`），坐标就是值。**# 号只在 DXF 导入时做一次性映射，之后不用。** 同一个几何点 = 一个名字（多条线交于一点，不再编多个 #）。
  - **`outline`**：整片闭合净线（层 14），块内坐标，按顺序。这是**权威几何**：纸样从它再生。没有它，`.apattern` 出不了纸样——有名边只覆盖量过的曲线，侧缝、肩缝这些没起名的段和点的沿线顺序都不在文件里，靠猜拼不回来（2026-11-06 验证过：只靠有名边 + 直线拼，周长差 1.3–5.9 cm）。有名边是它的子弧，侧缝这些直线段从它上面读，不靠假设。
  - **`edges`**：有名有姓的边（`neckline`、`armhole_l`、`hem`）。`points` 是语义锚点（起、经、终），`xy` 是实测净线多段线（原样收 DXF 的密集点，无损；先不搞贝塞尔，简单第一）。
  - **`segments`**：有名有姓的量（`chest`、`neckline`、`armhole`），带量法（`outline` 沿净线 / `straight` 直线）和实测值。线段定义直接住在文件里，不用另建 segments.md。
  - **`grainline`**：丝缕线，两个点。
  - **`notches`**：刀口点列表。
- **`checks`**：配对校验是数据（袖山=袖笼、领长=领围×0.82），打开就验，不用人口头对。

## 哪些进 JSON，哪些不进

进：`quantified.json`（点、轮廓、缝份）+ `segments.md`（线段定义）+ `segments-anchors.json`（锚点——点本身就有名有坐标，锚点概念被吸收了）+ `verification.json` 里的校验规则。

不进：`source.dxf`（CAD 原件，二进制，生产交换格式）+ `numbered.png`（编号图）+ `requirements.md` / `approval.md` / `verification.json`（流程记录）。

## job 文件夹里的位置

```
~/workspace/jobs/<款号>/
  requirements.md
  source.dxf                  # 首版 DXF 原件
  approval.md
  outputs/
    v0.1/
      <款号>-<码>.apattern     # 每版一个 .apattern，顶掉 quantified.json + segments.md + segments-anchors.json
      numbered.png
      verification.json
    v0.2/
      source.dxf
      <款号>-<码>.apattern
      numbered.png
      verification.json
```

每版还是新目录，规矩不变。变的只是每版里面三个数据文件合成一个 `.apattern`。

## 通用性

通用靠三样：JSON 本身通用 + 这份 Schema（`references/apattern-schema.json`，格式标准）+ skill 里的读写规则。本地 OpenClaw、线上 Muse、以后任何 agent，照着 Schema 就能读写。不是私有格式，不绑任何一家。

## 工具

- `server/src/pattern_making/apattern.py`：DXF → `.apattern` 转换（`dxf_to_apattern`），以及 Schema 校验（`validate_apattern`）。
- `.apattern` → DXF-AAMA 导出：待做（v0.2）。先只做导入，生产导出还走原 DXF。

## 版本历史

- **0.1**（2026-11-06）：首版。单码、JSON、块内坐标 cm、实测多段线、缝份参数、校验规则。首个文件：tshirt-165-96 v0.2（男士 165-96 T 恤 M 码）。
  - 同日验证补洞：首版只有有名边、没有整片闭合轮廓，出不了纸样（只靠有名边 + 直线拼，周长差 1.3–5.9 cm；点的沿线顺序和没起名的段都不在文件里）。补 `outline` 字段（整片闭合净线，必填，权威几何），有名边是它的子弧。转换器加校验：轮廓周长须与量化净线周长一致（差 0.1 cm 以上报错）。
