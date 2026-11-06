---
name: pattern-making
version: 0.1.5
description: "Garment pattern work: replicate and quantify a pattern from the user's own DXF. Parameters only, never coordinates computed in the agent's head; every version a new directory; a validation gate and a human approval gate before release."
---

# Pattern Making

制版 skill，一条通用流程：**复刻**——用户的 DXF → 量化 → 存档。

几何和校验不在文字里做，在 `server/` 的工具里做：MCP 服务器（`pattern serve`，stdio）优先，`pattern` CLI 备用。安装见 `server/README.md`。目录架构（整棵树、分层边界、加东西往哪放）见 README.md 的「目录架构」一节，这里不重复贴。

| 工具（MCP） | CLI | 用途 |
|---|---|---|
| `quantify_dxf` | `pattern quantify` | DXF → 量化 JSON（含每片 # 号坐标） |
| `plot_numbered_dxf` | `pattern plot` | DXF → 编号图 PNG |
| `write_dxf_aama` | `pattern write-dxf` | JSON 点列 → DXF-AAMA |
| `reanchor_segments` | `pattern reanchor` | 锚点 → 新版 DXF 的线段重量 |
| `dxf_to_apattern` | `pattern apattern` | DXF + 线段 → `.apattern`（agent 时代纸样文件） |
| `draft_pattern` | `pattern draft` | 量体 + 选项 → 新码 `.apattern`（参数制版） |
| `check_job` | `pattern check` | 校验门（`--release` 多一道放行门） |

## 铁律

1. **Agent 只传参数、不算坐标、不编数字。** 数只认文件里实际有的，量不出来的列 `unsupported`、不悄悄丢。对话里算出的坐标一律无效，改参数、重跑工具才是改版。
2. **每版新目录，绝不覆盖。** 输出永远是 `outputs/v0.1/`、`outputs/v0.2/`……改版另建目录。旧版、旧链接不动。
3. **校验门 + 审批门，两道都过才能放行。** 校验门是机器门（`check_job` 工具 + 有 SVG/DXF 时跑 Seamlint）；审批门是人门（用户点头）。没过审批门，不能放行。草稿就是草稿。
4. **密钥走环境变量。** API key 一律走环境变量，不进 prompt、不进 job 文件、不进 git。

## 流程：复刻（DXF → 量化 → 存档）

用户在自己的 CAD 里手打版、导出 DXF；agent 只量、不画、不改、不编。

一个款一个 job 文件夹（根目录 `~/workspace/jobs/`，见 `references/job-contract.md`）：

```
~/workspace/jobs/<款号>/
  requirements.md      # 文件来源、款名、样码、制版软件
  source.dxf           # 用户发的原文件，不动
  outputs/v0.1/        # 本版产物：.apattern、编号图
    <款号>-<码>.apattern   # 纸样数据唯一源头（顶掉 quantified.json + segments.md + segments-anchors.json）
    numbered.png
    verification.json
  verification.json    # 校验结果
  approval.md          # 用户审批记录（放行前必须有，格式见 job-contract.md）
```

1. **收文件。** 用户发 DXF，原文件存进 job 文件夹，不动它。
2. **量化。** `quantify_dxf` 工具（CLI：`pattern quantify --in source.dxf --out quantified.json --by-block`；按 INSERT 块分组；中文乱码加 `--decode-gbk`）：每片的包围盒、周长、面积、刀口位置、丝缕角度、片名文字，以及每个 `# N` 标签对应的 POINT 坐标（`numbered_points`，与轮廓点同一套模型空间坐标）。量不出来的实体列在 `unsupported` 里，不悄悄丢。缝份由工具直接算（`seam_allowance_mm`：每个净线轮廓点到最近裁剪线段的垂距，分布值，median 是该片的主缝份；省道处读数会偏大，那是省尖到裁剪线的距离，不是缝份）。**缝份一律读工具的垂距，绝不用包围盒差算**——斜边上包围盒差会把 1.0 cm 的缝份算成 1.45 cm。
3. **核对。** 用 `plot_numbered_dxf` 工具（CLI：`pattern plot --in source.dxf --out <图>.png`）重画轮廓图（ezdxf + matplotlib，按层着色、# 编号），和量化 JSON 逐片核对（轮廓、净线/裁剪线、刀口、丝缕、对折边）。闭合多段线必须按闭合标志画封口边。图按 CAD 的 Y-up 方向出（不翻转 Y 轴），与 DXF 在 CAD 里的朝向一致——翻转过一次（2026-11-06，`invert_yaxis` 把图画倒了），不要再加回去。**排版默认紧凑**（2026-11-06 用户定）：工具把各片排成 2 列、5 cm 间距的紧凑网格，而不是照 DXF 的 INSERT 位置画——CAD 的排版间距太大（v0.3 原排版 175×184 cm，紧凑后 110×99 cm），看图费劲；同行各片按块内坐标底边对齐，同件衣服的前/后片因此胸围线（腋点水平线）自动对齐。想看 DXF 原排版时加 `--no-compact`（MCP：`compact=false`）。# 号按角色着色（净线拐点橙、裁剪线拐点黑、工艺线端点灰、刀口红、打孔紫），不要只按 # 自身的层着色（层 2 几乎全是黑，分不开）；同点同角色的多个 # 合并成一个 `#A/#B` 标签（一个点多个编号是 CAD 按创建顺序给每条线端点编 ID，多条线交于一点就有多个 #，几何上是同一个点），不同角色同点则分开标色。# 号重叠时工具自动错开（贪心避让 + 细引线指回原点），不要手工一个个挪。
4. **编号。** 每片每点给 # 号：编的是点不是线段；编号顺序 ≠ 沿线顺序；同一位置多个 # 是多条线端点重合。线段由起终两端点的编号定位；哪段配哪段，由用户定、不由工具猜。**对称线**（层 6，或几何上左右对称的片）：有对称线的片，左、右袖笼是一样的，只定一边即可，另一边相同（不用两边各定一条；两边都量只是验证对称）。**# 号跨版本不稳定**（加线/删刀口会重排，2026-11-06 v2→v3 仅 4 个 # 留原位）：用户定义的线段须另存**锚点**——端点的块内坐标（cm，`segments-anchors.json`），新版本到货后用 `reanchor_segments` 工具（CLI：`pattern reanchor --anchors segments-anchors.json --in new.dxf`）按锚点就近匹配新 #（0.3 cm 内）再量，不要只记 # 号；匹配不上的锚点要报出来，不要悄悄丢。`reanchor` 量法：每条线段在锚点文件里存一个 `method`（`outline` 沿净线量弧线，`straight` 量直线），工具优先按存的方法量；没存时才按启发式判别（弦在片外的按弧线、在片内的按直线）。两端点投影到同一条净线（层 14）上时沿净线量弧线长（领围/袖笼/袖山/下摆/中长），否则量直线（胸围/腰围等横向半围）。**注意**：有的文件把领围/袖笼的 # 编在裁剪线（层 1）上（如 165-96 T 恤 #2–#5、#24–#27），工具会把它们投影到净线上再量（投影距 ≤2.0 cm，缝份 1.0 cm 在内）；一个块里有多片（前+后）或一个文件有多个块（前/后/袖/领各一块，如 165-96 v0.2）时，工具按 # 所在的净线分片量，不混片。
5. **汇报口径。** 文件单位是毫米，用户用厘米：汇报用厘米，净线在前、裁剪线在后，毫米只留在 JSON 里。净线 = 成衣尺寸；层 14 = 净线，层 1 = 裁剪线，层 7 = 丝缕线。
6. **出 `.apattern`。** 每版定稿后，用 `dxf_to_apattern` 工具（CLI：`pattern apattern --in source.dxf --anchors segments-anchors.json --quantified quantified.json --names names.json --meta meta.json --out <款号>-<码>.apattern`）把本版转成 `.apattern`——agent 时代的纸样文件（JSON，一个款、一个码、一个文件；有名有姓的点/边/线段，顶替不稳定的 DXF # 号；缝份是参数；配对校验是数据）。格式标准见 `references/apattern-schema.json`，说明见 `references/apattern.md`。点名是人定的（哪个 # 是腋点、哪个是领口中点），`names.json` 里写清楚，工具不编名字。转换器会重测每条线段、核对每条边的弧长和线段长，差 0.05 cm 以上就报错，不悄悄写错数据。转完的 `.apattern` 是本版纸样数据的唯一源头，进当版目录；`quantified.json`、`segments.md`、`segments-anchors.json` 不再另存（老版的留着不动，不重写历史）。
7. **存档。** `.apattern` + 编号图进当版目录，校验结果进 `verification.json`。
8. **下一步（另议，不自动做）。** 缝份配对（用户定配对表，agent 按表量）、放码（= 按量体重打版，不是缩放图纸；单码文件放不出多码，要用户给放码表或各码围度）、用户自家公式提取（按公式提取表的方法，实测值做锚，用户填公式、agent 验算；不编公式）、`.apattern` → DXF-AAMA 导出（生产用，目前还走原 DXF）。

## 流程：出纸样（自然语言 → 参数制版）

用户说一句话要纸样（“帮我出一个 T 恤纸样”），agent 问清关键信息再出图，不是放码、不是缩放，是按量体重新打版。

**需求模型**在 `requirements/<款式>.json` 里：量体（人：胸围、身高，必填；肩宽、腰围，选填）+ 选项（衣服：版型/领型/袖长/衣长，各有默认值）。agent 先读需求模型，再对照用户给的信息，缺什么问什么。

**追问的规矩：**
- 先问量体（胸围、身高），再问选项（版型、领型、袖长）；一次问一个主题，不一次甩十个问题。
- 每个问题都带底版参照和默认值（“165-96 是人体 96、成衣 102 的常规版，你要多大？”），用户只说“就按常规”就能过。
- 头脑风暴式：agent 提方案、用户拍板，不是填表。用户改主意随时可以改，改完重算。
- 必填项（胸围、身高）没齐不能出图；选填项没给就用默认值，出图时写清楚用了哪个默认。

**制版引擎**（`draft_pattern` 工具，CLI：`pattern draft --base <底版.apattern> --measurements '{...}' --options '{...}' --out <新码.apattern>`）：
- 成衣量度 = 量体 + 松量（版型定松量：修身胸围 +4、常规 +6、宽松 +10）；前/后片按底版比例分（165-96 前 49、后 53）。
- **用户的制版规则（2026-11-07，一码 = 成衣胸围 4 cm，全部按胸围放量 chest_delta 走）：**
  - 肩宽：一码 +1 cm（chest_delta/4）。肩线（领肩点→肩端点）加长这个数，**斜度不变**：肩端点从新领肩点沿底版肩线方向放。
  - 后背宽 / 前胸宽：各 +胸围放量 × 15%（back_w / chest_w 点左右各移一半）。
  - 袖笼深：+胸围放量 × 20%（腋点往下移，袖笼加深）。
  - 后领宽 / 前领宽：各 +胸围放量 × 10%（领肩点左右各移一半）。
  - 后领深：**固定**（底版值不变，后领围中点跟着领肩点走）。
  - 前领深：+胸围放量 × 10%（前领围中点往下移）。
  - 袖肥：+胸围放量 / 2（袖片 cap_l / cap_r 左右各移一半）。
  - 袖山高：动态调整以对合袖笼线长（袖山 = 前袖笼 + 后袖笼 + 0.05，针织无容量），一般往上抬 0.2–0.35。
  - 袖口：跟袖肥一样放（+胸围放量 / 2）。
- 袖笼、领围是结果不是输入：宽度/长度动完重测；袖山按新袖笼反推，领长按新领围反推（领长 =（前领围 + 后领围）× 0.82，罗纹负松量）。
- 轮廓按有名点插值重建（曲线保形）；全部线段重测、配对校验重跑，不过就报错停下，不悄悄改数字。
- 规则全文写在 `server/src/pattern_making/draft.py` 的文件头里，等用户纠正。
- 出图后把关键量度（成衣胸围、腰围、摆围、衣长、袖笼、袖山、领围）和编号图一起给用户确认；用户点头才算完。

## 出 DXF（可选）

`write_dxf_aama` 工具（CLI：`pattern write-dxf`，`--miter` 把缝份角改尖角）把 JSON 点列写成 DXF-AAMA（R12、标准层号、每片一个块、刀口双份写、# 编号）。写完按 `references/aama-dxf.md` 的回读验收清单复核。规范见 `references/aama-dxf.md`。目前只支持三片式 T 恤布局（FRONT/BACK/SLEEVE，单码 M）。

## 校验

调 `check_job` 工具（CLI：`pattern check --job ~/workspace/jobs/<款号>`；放行检查加 `--release`）。

`--release` 要求同时满足：`verification.json` 状态为 pass、`approval.md` 里有用户明确的放行记录、本版输出目录存在且未被后续覆盖。缺任何一项，脚本退出非 0，agent 必须停下来找用户，不能自己放行。细则见 `references/validation-gate.md`。

有 SVG/DXF 产物时，另跑 Seamlint（`slnt check`）做缝长、拐点、断口、松量比检查，报告贴进 `verification.json`。Seamlint 只量不改，量不出来要写"无法量测"，不能编一个通过。

## 交付

只说三件事：本版是什么（款、码段、版型）、校验过了什么（附 verification.json）、还缺什么（OPEN 项 + 下一步要用户给的东西）。没实机验证的扩展名不伪造：没在 CLO/Style3D 里打开保存过，就不写"已入 CLO/Style3D"。
