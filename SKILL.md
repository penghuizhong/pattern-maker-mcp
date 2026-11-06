---
name: pattern-making
version: 0.1.2
description: "Garment pattern work in two workflows: generate a pattern from parameters with FreeSewing, or replicate and quantify a pattern from the user's own DXF. Parameters only, never coordinates computed in the agent's head; every version a new directory; a validation gate and a human approval gate before release."
---

# Pattern Making

制版 skill，两条通用流程：

1. **生成**：参数 → FreeSewing → 纸样 + 校验。
2. **复刻**：用户的 DXF → 量化 → 存档。

两条链分工是死的：FreeSewing 只生成几何，不读 DXF；ezdxf/Python 只读写 DXF、只量化，不画版型；中间用 JSON 点列接。

## 铁律

1. **Agent 只传参数、不算坐标、不编数字。** 生成链：几何由引擎算；复刻链：数只认文件里实际有的，量不出来的列 `unsupported`、不悄悄丢。对话里算出的坐标一律无效，改参数、重跑脚本才是改版。
2. **每版新目录，绝不覆盖。** 输出永远是 `outputs/v0.1/`、`outputs/v0.2/`……改版另建目录。旧版、旧链接不动。
3. **校验门 + 审批门，两道都过才能放行。** 校验门是机器门（`scripts/check_job.py` + 有 SVG/DXF 时跑 Seamlint）；审批门是人门（用户点头）。没过审批门，不能放行。草稿就是草稿。
4. **密钥走环境变量。** API key 一律走环境变量，不进 prompt、不进 job 文件、不进 git。

## 流程一：生成（参数 → FreeSewing → 纸样）

一个款一个 job 文件夹，结构见 `references/job-contract.md`：

```
jobs/<款号>/
  requirements.md      # 用户原话 + 结构单 + OPEN 项
  measurements.json    # 围度（用户给的量体数据或多码表，标明来源）
  design.json          # 款式参数：品类、码段、版型、缝份、特殊工艺
  outputs/v0.1/        # 本版产物：SVG / DXF / 校验报告
  verification.json    # 本版校验结果
  approval.md          # 用户审批记录（放行前必须有，格式见 job-contract.md）
```

1. **先写结构单，再出图。** 用户给照片、手稿或文字要求时，先按 `references/job-contract.md` 写 `requirements.md`：每条缝、褶、口袋、开衩、领型、扣数都要有出处和置信度，空白项就是没读懂，不能靠猜填。文字与图片不一致时（比如文字说翻盖口袋、图片却是贴袋），必须列为 OPEN 项。
2. **定参数。** measurements 是"人"的围度，options 是"衣服"（松量、是否收腰等）；改衣服先动 options，不动量体围度。围度一律用户给：量体数据或用户自己的多码表，job 里标明来源；agent 不猜、不凑。用户给多码表时，验算表内恒量（各码围度差全码一致），不一致就停下来问用户。缺围度先问用户要，不要用标准码顶上。
3. **出图。** FreeSewing（如 Teagan）：量体围度 + 选项进去，版型几何出来（点列、曲线、刀眼）；`.draft().render()` 出 SVG，再转 PNG 看图。曲线纪律：制版点 + 样条 + 长度拟合 + 法线缝份偏移。
4. **出 DXF（可选）。** `scripts/to-dxf-v3.py` 把引擎的 JSON 点列写成 DXF-AAMA（R12、标准层号、每片一个块、刀口双份写、# 编号；`--miter` 把缝份角改尖角）。写完按 `references/aama-dxf.md` 的回读验收清单复核。规范见 `references/aama-dxf.md`。
5. **校验。** 跑 `scripts/check_job.py`：

```bash
python3 scripts/check_job.py --job jobs/<款号>
# 放行检查（多一道门）：
python3 scripts/check_job.py --job jobs/<款号> --release
```

`--release` 要求同时满足：`verification.json` 状态为 pass、`approval.md` 里有用户明确的放行记录、本版输出目录存在且未被后续覆盖。缺任何一项，脚本退出非 0，agent 必须停下来找用户，不能自己放行。细则见 `references/validation-gate.md`。

有 SVG/DXF 产物时，另跑 Seamlint（`slnt check`）做缝长、拐点、断口、松量比检查，报告贴进 `verification.json`。Seamlint 只量不改，量不出来要写"无法量测"，不能编一个通过。

6. **交付。** 只说三件事：本版是什么（款、码段、版型）、校验过了什么（附 verification.json）、还缺什么（OPEN 项 + 下一步要用户给的东西）。没实机验证的扩展名不伪造：没在 CLO/Style3D 里打开保存过，就不写"已入 CLO/Style3D"。

## 流程二：复刻（DXF → 量化 → 存档）

用户在自己的 CAD 里手打版、导出 DXF；agent 只量、不画、不改、不编。FreeSewing 不进这条链：它是生成器、读不了 DXF，硬套等于拿猜的参数盖掉实测的数。

一个款一个 job 文件夹：

```
jobs/<款号>/
  requirements.md      # 文件来源、款名、样码、制版软件
  source.dxf           # 用户发的原文件，不动
  outputs/v0.1/        # 本版产物：量化 JSON、重画图、编号图
  verification.json    # 校验结果
  approval.md          # 用户审批记录（放行前必须有，格式见 job-contract.md）
```

1. **收文件。** 用户发 DXF，原文件存进 job 文件夹，不动它。
2. **量化。** `scripts/dxf_quantify.py --in source.dxf --out quantified.json --by-block`（按 INSERT 块分组；中文乱码加 `--decode-gbk`）：每片的包围盒、周长、面积、刀口位置、丝缕角度、片名文字。量不出来的实体列在 `unsupported` 里，不悄悄丢。
3. **核对。** 用 `scripts/dxf_plot.py --in source.dxf --out <图>.png` 重画轮廓图（ezdxf + matplotlib，按层着色、# 编号），和量化 JSON 逐片核对（轮廓、净线/裁剪线、刀口、丝缕、对折边）。闭合多段线必须按闭合标志画封口边。
4. **编号。** 每片每点给 # 号：编的是点不是线段；编号顺序 ≠ 沿线顺序；同一位置多个 # 是多条线端点重合。线段由起终两端点的编号定位；哪段配哪段，由用户定、不由工具猜。
5. **汇报口径。** 文件单位是毫米，用户用厘米：汇报用厘米，净线在前、裁剪线在后，毫米只留在 JSON 里。净线 = 成衣尺寸；层 14 = 净线，层 1 = 裁剪线，层 7 = 丝缕线。
6. **存档。** 量化 JSON + 重画图 + 编号图进当版目录，校验结果进 `verification.json`。
7. **下一步（另议，不自动做）。** 缝份配对（用户定配对表，agent 按表量）、放码（= 按量体重打版，不是缩放图纸；单码文件放不出多码，要用户给放码表或各码围度）、用户自家公式提取（按公式提取表的方法，实测值做锚，用户填公式、agent 验算；不编公式）。
