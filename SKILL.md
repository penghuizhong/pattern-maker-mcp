---
name: pattern-making
version: 0.1.2
description: Garment pattern work driven by an agent. Use when the user asks for a sewing pattern, a toile/sample pattern, grading, a DXF for a factory, or a pattern check. Turns a user requirement into a versioned pattern job: requirement sheet first, measurements from the locked size tables, deterministic geometry by script/engine (never coordinates computed in the agent's head), a validation gate, and a human approval gate before any factory release or sample cut.
---

# Pattern Making (skill, v0.1.2)

这是一个制版 skill，不是已经会画西装纸样的程序。它把用户需求变成版本化的纸样 job：先写结构单，围度只认锁定的表，几何由确定性脚本或引擎算，校验门 + 审批门通过后才能放行。

## 铁律

1. **先写结构单，再出图。** 用户给照片、手稿或文字要求时，先按 `references/job-contract.md` 写 `requirements.md`：每条缝、褶、口袋、开衩、领型、扣数都要有出处和置信度，空白项就是没读懂，不能靠猜填。文字与图片不一致时（比如文字说翻盖口袋、图片却是贴袋），必须列为 OPEN 项，样衣不能先裁。
2. **AI 只传参数，不算坐标。** 几何永远由确定性脚本或引擎算：`scripts/`、FreeSewing、GarmentCode、Seamly2D 命令行。Agent 在对话里算出的坐标一律无效，改参数、重跑脚本才是改版。
3. **围度只认锁定的表。** 成衣尺寸只用 `measurements/` 里的男女西装表；量体定制必须用户另外给量体数据，并在 job 里标明来源。缺围度时从标准码起步可以，但必须在交付里写清“哪几个值是标准码、不是实测”。
4. **每版新目录，绝不覆盖。** 输出永远是 `outputs/v0.1/`、`outputs/v0.2/`……改版另建目录。旧版、旧链接不动。
5. **校验门 + 审批门，两道都过才能放行。** 校验门是机器门（`scripts/check_job.py` + 有 SVG/DXF 时跑 Seamlint）；审批门是人门（用户点头）。没过审批门，DXF 不能发工厂、样衣不能裁、文件不能对外发布。草稿就是草稿。
6. **密钥走环境变量。** API key 一律走环境变量，不进 prompt、不进 job 文件、不进 git。

## 工作流

### 第 1 步：立 job

一个款一个 job 文件夹，结构见 `references/job-contract.md`：

```
jobs/<款号>/
  requirements.md      # 用户原话 + 结构单 + OPEN 项
  measurements.json    # 围度来源（引用 measurements/ 的表，或用户量体）
  design.json          # 款式参数：品类、码段、版型、缝份、特殊工艺
  outputs/v0.1/        # 本版产物：SVG / DXF / 校验报告
  verification.json    # 本版校验结果
  approval.md          # 用户审批记录（放行前必须有）
```

### 第 2 步：定围度与放码

- 先读 `references/measurements.md` 和 `references/grading.md`。
- 成衣西装直接用表里的全码值，**不要用“每档 +4”之类的一刀切公式去反推男装表**：男装肩宽、衣长的档差本身就不均匀（见 grading.md），表即是放码结果。
- 跑 `scripts/grading.py` 出放码表并自检（胸腰差、上衣减裤子腰围差等恒量必须全码成立，不成立就停下来问用户，不要悄悄修数）。

```bash
python3 scripts/grading.py --garment womens-suit --sizes S M L XL 2XL 3XL
python3 scripts/grading.py --garment mens-suit --out jobs/<款号>/outputs/v0.1/graded.json
```

### 第 3 步：出图（引擎二选一，别两个都接）

按 `references/engines.md` 选引擎，推荐：

- JS 路线：FreeSewing + `pattern-via-io`（stdin JSON → stdout SVG/JSON）。
- Python 路线：`pattern-making-skill` 的 `pattern.py` 纪律（单文件、标准库、每步缝份校验），或 GarmentCode 的程序合成路线。

**当前边界：** 西装是中高级制版，AI 制版现阶段碰不了，先从简单款做起。本仓目前锁定的是围度、放码、job 契约和校验门，外加一个能真跑的基础 T 恤模块（`scripts/tshirt.py`，净样 + 袖山与袖窿自动对合）。工业西装原型（驳头、袖窿、挂面、半毛衬结构）暂缓，没有现成可复用的开源原型时不许用基础原型冒充西装出图。

### 第 4 步：校验门

```bash
python3 scripts/check_job.py --job jobs/<款号>
# 放行检查（多一道门）：
python3 scripts/check_job.py --job jobs/<款号> --release
```

`--release` 要求同时满足：`verification.json` 状态为 pass、`approval.md` 里有用户明确的放行记录、本版输出目录存在且未被后续覆盖。缺任何一项，脚本退出非 0，agent 必须停下来找用户，不能自己放行。

有 SVG/DXF 产物时，另跑 Seamlint（`slnt check`）做缝长、拐点、断口、松量比检查，报告贴进 `verification.json`。Seamlint 只量不改，量不出来要写“无法量测”，不能编一个通过。

### 第 5 步：交付

交付只说三件事：本版是什么（款、码段、版型）、校验过了什么（附 verification.json）、还缺什么（OPEN 项 + 下一步要用户给的东西）。没实机验证的扩展名不伪造：没在 CLO/Style3D 里打开保存过，就不写“已入 CLO/Style3D”；轮廓核验通过不等于合体、不等于生产可用。

## 协议红线

- MIT 的 FreeSewing、GarmentCode、pattern-making-skill、Seamlint：可引用、可改，保留原版权声明。

## 参考文件

- `references/measurements.md` — 男女西装成衣尺寸表出处与口径
- `references/grading.md` — 放码规则与恒量自检
- `references/job-contract.md` — job 文件夹契约与版本规则
- `references/validation-gate.md` — 校验门与审批门细则
- `references/engines.md` — 引擎与工具对照（可复用 / 本地限定 / 协议）
- `references/curves.md` — 曲线纪律：制版点 + 样条 + 长度拟合 + 法线缝份偏移
