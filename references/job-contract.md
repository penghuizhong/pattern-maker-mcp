# Job contract — 一个款一个文件夹

## 结构（固定，不许自创变体）

```
jobs/<款号>/
  requirements.md      # 用户原话 + 结构单 + OPEN 项（必须先有）
  measurements.json    # 围度：引用 measurements/ 的表，或用户量体（标来源）
  design.json          # 款式参数（见下）
  outputs/v0.1/        # 本版产物
  outputs/v0.2/        # 下一版另建目录，绝不覆盖 v0.1
  verification.json    # 本版校验结果（机器门）
  approval.md          # 用户审批记录（人门，放行前必须有）
```

## design.json 字段（最小集）

- `garment`：`mens-suit` / `womens-suit` / 其他（其他品类必须先补原型说明，不能套西装参数）
- `sizes`：如 `["S","M","L","XL","2XL","3XL"]`
- `fit`：如 `classic`，并注明出处（品牌表 / 用户指定）
- `seam_allowance_mm`：缝份，缺省不许默认一个数，必须用户或工艺单给
- `construction`：结构要点，如 `half_canvas`（半毛衬）、开衩数、口袋型、扣数——**有出入的项写进 OPEN，不写进 construction 当定稿**
- `engine`：本版用的出图引擎（`freesewing` / `pattern-making-skill` / `garmentcode` / `seamly-cli`）
- `open_items`：OPEN 项清单，和 requirements.md 一致

## 版本规则

- 版本号只增不改：v0.1、v0.2……同一版本号的目录写定后不再改内容，改版就升号。
- 校验报告、放码表、SVG/DXF 都放在当版目录里，不放 job 根目录，避免“最新版到底是哪份”扯皮。
- 旧版链接、旧版文件不动。用户要看旧版，随时能找回。

## OPEN 项规则

照片与文字出入、缺后背图、缺裤子图、缺面料品牌、缺缝份、缺量体——全部是 OPEN 项。OPEN 项存在时：可以出草稿、可以出校验报告，**不能写“已定稿”、不能发工厂、不能裁样衣**。280 套西装的贴袋/翻盖袋、单扣/双扣出入就是典型 OPEN 项，样衣裁剪只等这两项答案（按用户此前的裁剪门）。

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
