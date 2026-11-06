# Changelog

按日期记。每次改动先写条目再发版；版本号只写在 SKILL.md 里（frontmatter 的 `version` 字段），发版时按它打 git tag。

## 2026-11-06 — 根 README 补目录架构说明

- 根 `README.md` 的“仓里有什么”改成完整的“目录架构”一节：整棵树 + 分层与边界（仓根 skill / server 工具、引擎与库、框架依赖与库源码、两个运行时一条 JSON 接口、数据文件是生成的、不在仓里的东西）+ 加东西往哪放的对照表。只改文档，不动代码。

## 2026-11-06 — 通用生成纸样引擎 + 基础纸样库（server/engine/ + server/library/）

- 按用户要求去 Codeberg 把 FreeSewing 的底拿进来，做成本项目的通用生成纸样引擎和基础纸样库，目录架构规范化。先 clone 整个 monorepo（shallow + sparse）核对结构：framework 是 `packages/core`（7.3k 行：Design/Pattern/Point/Path/Store/Stack/SVG 渲染、插件系统）+ `plugins/`；数据结构是 `packages/config` 的 42 个标准量体（只有 shoulderSlope 是角度，其余毫米）+ core 的 pattern settings 默认值；计算公式是各款 `src/*.mjs` 的 draft 函数；款式数据是各款 `about.json` + `i18n/` + `packages/models` 的标准量体套（neckstimate 从颈围推算）。
- 分工定死：框架（core + 插件）是 pinned 依赖（server/package.json，exact 4.10.2，lockfile 为凭），不 fork；纸样库是源码进仓（`server/library/`），以后自家款也按同样形状放进来。runner（`server/engine/runner/draft.mjs`）先从库里找款（扫 `library/<分类>/<款名>/src/index.mjs`，分类只是组织、不定死），没有才去 npm 找；`source: library/npm` 写进 summary，库优先。
- 库里三款（FreeSewing 4.10.2，MIT，见 `server/library/NOTICE.md`，只改了库内互相引用的 import、改成相对路径）：`blocks/brian/`（男装身原型，11 个量体）、`designs/teagan/`（收腰针织 T，13 个量体）、`parts/library/`（可复用部件：袖子、矩形、两片袖、三片帽）。依赖链 teagan → brian → library → core。款测试没收（依赖 monorepo 的共享测试架子），本项目用 draft 对比 + MCP 测试验。
- 数据结构落地为文件（`server/engine/data/generate.mjs` 生成，改框架版本或加款后重跑）：`measurements.json`（42 量体）、`settings.json`（core 默认值 + sa 默认 10mm）、`paths-format.md`（点列 JSON 格式说明）；`library/data/models.json`（40 套标准量体）、`schemas/<款>.json`（各款要什么量体、选项的默认值与上下限，与 `freesewing_design_info` 同源）。
- 验证：库里 Teagan 点列与存档 `teagan-paths-v2.json` 逐项相等（SVG 36795 字节与 npm 版一致），Brian 库里出图正常；MCP 全套测试通过（含 source: library 断言、draft→write_dxf 链 102 号/4 刀口）；测试自己重建 /tmp/job-test（/tmp 会被清掉）。旧 `server/freesewing/` 目录已删（从未进 git），Node 根现在是 `server/`（package.json + node_modules）。
- SKILL.md 工具一节与生成链第 3 步同步改成“款从项目自己的库出”。SKILL.md 版本不变（仍 0.1.2），不打新 tag。

## 2026-11-06 — FreeSewing 生图服务：draft_freesewing（server 0.2.0）

- 新增第 5、6 个工具 `draft_freesewing` / `freesewing_design_info`（MCP + `pattern draft` CLI），server 升 0.2.0；SKILL.md 工具表与生成链第 3 步同步改成调工具。SKILL.md 版本不变（仍 0.1.2），不打新 tag。
- 生图不再定死款：款名、量体、选项全由调用方传；款要什么量体、有什么选项（默认值、上下限）由工具运行时从款本身查（`pattern.getConfig()`，FreeSewing 官方口径：量体与选项由款定义，不由 core 定义）；已装哪些款由工具运行时从 `node_modules/@freesewing/*` 里认（导出了款构造函数的才是款——keywords 与 about.json 不区分，实测 core、插件、library 全带 "design" 关键词）。新款只须 `cd server/freesewing && npm install @freesewing/<款名>`。
- 验证（MCP 全套测试通过）：Teagan 收腰版的点列 JSON 与存档 `teagan-paths-v2.json` 在写盘契约（seam、sa、grainline、刀口、title、topLeft）上逐项相等，SVG 除主题的日期戳外与 `teagan-fitted.svg` 一致；Brian 同一套量体照常出图（3 片，hips/waist 报未用——它只要 11 个量体），证明 runner 不只认 Teagan；缺量体、未装款（aaron）都按预期报错并给出所缺/已装清单；未知选项名、超上下限只报 warning 不静默；draft 出来的新点列走 `write_dxf_aama --miter` 照常出 102 号、4 刀口。
- 实现细节：`server/freesewing/draft.mjs`（Node runner，`--design/--measurements/--options/--sa/--out`，另有 `--info` 与 `--list-designs`）+ `server/src/pattern_making/freesewing.py`（Python 封装）；一次调用跑两次 draft（一次不带主题出点列 JSON、一次带主题出 SVG，几何相同）；pct 选项传的是小数（0.08 = 8%），spec 的上下限是百分数，runner 换算后再比上下限；丝缕线按名含 grainline 认（macro 路径名如 `__macro_grainline_grainline_line`），同时按 `grainline` 键暴露给写盘器。

## 2026-11-06 — SKILL.md 瘦身：工具改走 server/

- SKILL.md 瘦身：几何和校验改调 `server/` 的工具（MCP 优先，`pattern` CLI 备用），新增工具对照表；`scripts/` 4 个脚本（check_job.py、dxf_quantify.py、to-dxf-v3.py、dxf_plot.py）已删（trash 可恢复至 2026-12-06，git 历史里也有）。
- references/validation-gate.md 与 aama-dxf.md 的工具引用同步改成 MCP 工具名 + `pattern` 命令；README（仓里有什么、使用、快速验证）同步改。
- 版本不变（SKILL.md 仍 0.1.2），不打新 tag。

## 2026-11-06 — SKILL.md 重构：只讲通用流程

- 标题去掉版本号；版本号只剩 frontmatter 的 `version` 字段（README 版本管理一节同步改了）。
- 删掉所有硬编码的款形字眼（西装、T 恤、男女装）：流程只讲通用步骤，款式只出现在 job 数据和 `measurements/` 表里，不出现在 skill 正文里。
- `协议红线` 整节删除；`参考文件` 一节删除，两个只在那里出现的引用改到步骤里内联（出图 → curves.md，校验门 → validation-gate.md）。
- scripts/ 只留 check_job.py、dxf_quantify.py、to-dxf-v3.py：tshirt.py、grading.py 已删；第 2 步放码改按 grading.md 恒量自检，不再跑脚本。
- job-contract.md 补 approval.md 模板格式（日期、版本、放行范围、已知风险；对齐 check_job.py --release 的四点检查）。
- references/ 只留 aama-dxf.md、job-contract.md、validation-gate.md：curves.md、engines.md、grading.md、measurements.md 已删；SKILL.md 第 2、3 步的引用同步改成直接表述（按表验算恒量、曲线纪律一行）。
- 再重构：SKILL.md 改写成两条通用流程（FreeSewing 生成、DXF 复刻）；Python/GarmentCode 生成路线删掉（没跑通过的链路）；pattern.py 悬空引用随之消除。
- dxf_plot.py：user-dxf-1 的 plot_numbered_full.py 通用化进仓（`--in/--out/--title`，ezdxf + matplotlib，按层着色、# 编号、闭合封口）；跑裤子 1.dxf 与编号图 v2 逐像素一致（10 片、191 个 #，4680×3240）。
- 清西装旧数据：examples/womens-suit-M/ 与 measurements/（男女西装表）已删；围度改一律用户给（measurements.json 必须标 source，check_job.py 改查 source 不再查锁表）；job-contract.md（garment 品类名、engine 两链）、validation-gate.md（门第 2、5 项）、README（仓里有什么、快速验证改临时 job）同步改。
- job-contract.md 的 OPEN 项规则一节按用户要求删除（OPEN 概念仍在 SKILL.md 第 1 步与 validation-gate.md 人门里）。
- SKILL.md 去下游表述：删“样衣不能先裁”（第 1 步）、“DXF 不能发工厂、样衣不能裁、文件不能对外发布”（铁律 3）、frontmatter 的 "factory release or sample cut"——只出纸样阶段，不写没发生的事；再删两句范围声明（“轮廓核验通过不等于合体、不等于生产可用”“量化只证明几何，不证明合体”）。

## 2026-11-05（晚上）—— 缝份角改尖角

- 缝份角改尖角（用户习惯，ETCAD 截图指出）：`to-dxf-v3.py` 新增 `--miter`，把 FreeSewing 缝份偏移的斜切（bevel）段换成两边偏移线切线的交点（尖角，miter），每片 4 处、共 12 处；尖角比斜切中点多伸出腋下 11.4 / 肩尖·领口角 7.1 / 袖山底角 5.7·3.7 / 脚口·袖口角 15.8 mm（>25 mm 拒绝写入）。`teagan-fitted-v3.1.dxf` 已出，回读校验全项通过（编号 #1–#102、拐点 94、曲线点 1828 不变）；净线与 v3 一字不差，裁剪线周长前片 +31.8 / 袖片 +23.2 mm（正是尖角腿长增量）。
- 对折边（层 6）补满整条：v3 只画了封口段（领口缝份点到脚口净线点），脚口短 30 mm；v3.1 从领口缝份点画到脚口缝份点（前片 638.0 mm）。
- `verify-aama-v3.py` 接受 `--file/--turn/--numbers`（可验 v3.1），对折边校验同时接受 v3 式（封口段）与 v3.1 式（整条）。
- 规范 `references/aama-dxf.md` 补 §10 缝份角规则与 §3 对折边整条说明。
- 版本管理规矩改了：版本号只写在 SKILL.md 里；VERSION 文件已删；本文件改按日期记，不再写版本号（防不同步）。

## 2026-11-05（傍晚）—— DXF-AAMA 写入

- 新增 DXF-AAMA 写入规范 `references/aama-dxf.md`：R12、标准层号、闭合与对折、刀口双份写、# 编号、片头/片名文字、ezdxf 写 R12 的坑、回读验收清单。
- 新增 `scripts/to-dxf-v3.py`：FreeSewing JSON 点列 → DXF-AAMA（R12），Teagan 单码 M 已出 `teagan-fitted-v3.dxf`，回读校验全项通过（编号 #1–#90、刀口 4 处双份、净线包围盒与 v2 一致）。
- `references/engines.md` 补 AAMA 写盘条目。

## 2026-11-05（下午）—— 通用标准架构

- 改造成通用标准 skill 架构：去掉与特定运行端绑定的联动说明（原“共用 skill 仓”导语、“两端分工”章节、README 里的两端共用章节），任何 agent 环境均可直接使用。
- `SKILL.md` 协议红线只保留 MIT 部分（FreeSewing、GarmentCode、pattern-making-skill、Seamlint，可引用、可改，保留原版权声明）。
- 密钥规则保留为通用铁律：API key 一律走环境变量，不进 prompt、不进 job 文件、不进 git。
- 新增版本管理：`VERSION` 文件 + 本 changelog + 发版打 tag 的规矩。

## 2026-11-03 — 初版（改造前基线）

- 初版：铁律、工作流、job 契约、男女西装锁表、放码与校验脚本、基础 T 恤模块、示例 job。
