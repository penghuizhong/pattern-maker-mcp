# Job contract — 一个款一个文件夹

## 根目录（固定）

所有 job 文件夹都在 `~/workspace/jobs/` 下面，一个款一个文件夹。Muse 和本地 OpenClaw 用同一套结构、同一个根目录（两台机器看到同一份文件靠同步办法，结构本身不变）。

## 结构（固定，不许自创变体）

```
~/workspace/jobs/<款号>/
  requirements.md      # 用户原话 + 结构单 + OPEN 项（必须先有）
  measurements.json    # 围度：用户给的量体数据或多码表（必须标来源）
  design.json          # 款式参数（见下）
  outputs/v0.1/        # 本版产物
    <款号>-<码>.apattern   # 纸样数据唯一源头（JSON，见 references/apattern.md）
    numbered.png           # 编号图
    verification.json      # 本版校验结果（机器门）
  outputs/v0.2/        # 下一版另建目录，绝不覆盖 v0.1
  verification.json    # 本版校验结果（机器门）
  approval.md          # 用户审批记录（人门，放行前必须有）
```

复刻链多一个原文件在 job 根目录：`source.dxf`（用户发的原文件，不动；老 job 里原名保留，如 `1.dxf`、`tshirt.dxf`）。

## .apattern（纸样数据唯一源头，v0.1.3 起）

每版定稿后转一个 `.apattern`（JSON，一个款、一个码、一个文件），放进当版目录。它顶掉 `quantified.json` + `segments.md` + `segments-anchors.json` 三个散文件——点、轮廓、线段、缝份、校验全在里面（有名有姓的点/边/线段，块内坐标 cm）。格式标准见 `references/apattern-schema.json`，说明见 `references/apattern.md`，转换工具见 `server/src/pattern_making/apattern.py`（MCP `dxf_to_apattern` / CLI `pattern apattern`）。老版的三个散文件留着不动，不重写历史。

## design.json 字段（最小集）

- `garment`：品类名（如 `t-shirt` / `trousers`），由用户定；新品类先补原型说明
- `sizes`：如 `["S","M","L","XL","2XL","3XL"]`
- `fit`：如 `classic`，并注明出处（品牌表 / 用户指定）
- `seam_allowance_mm`：缝份，缺省不许默认一个数，必须用户或工艺单给
- `construction`：结构要点，如开衩数、口袋型、扣数——**有出入的项写进 OPEN，不写进 construction 当定稿**
- `engine`：本版用的出图引擎（复刻链填 `dxf`，表示图案来自用户 DXF）
- `open_items`：OPEN 项清单，和 requirements.md 一致

## 版本规则

- 版本号只增不改：v0.1、v0.2……同一版本号的目录写定后不再改内容，改版就升号。
- 校验报告、放码表、SVG/DXF 都放在当版目录里，不放 job 根目录，避免“最新版到底是哪份”扯皮。
- 旧版链接、旧版文件不动。用户要看旧版，随时能找回。

## approval.md 格式（放行时写）

```markdown
# 审批记录

- 日期：2026-11-06
- 版本：v0.1
- 放行范围：发工厂（发工厂 / 裁样衣 / 仅内部看样，三选一）
- 放行：同意按本版放行
- 已知风险：无（有 OPEN 项未清时，逐项写明，注明"用户坚持放行"）
```

`check_job.py --release` 认这四点：文件存在、提到版本号、出现"放行"/"批准"字样、有 OPEN 项时必须写"已知风险"。缺任何一点，放行门就不开。
