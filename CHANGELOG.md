# Changelog

按日期记。每次改动先写条目再发版；版本号只写在 SKILL.md 里（frontmatter 的 `version` 字段），发版时按它打 git tag。

## 2026-11-06 — .apattern：agent 时代的纸样文件（v0.1）

- 用户决定：定 agent 时代的纸样文件标准。DXF-AAMA 还是生产交换格式（给工厂/CAD），`.apattern`（JSON，一个款、一个码、一个文件）是 agent 的工作源头，两边各司其职。简单第一：单码走，放码另算；曲线先存实测多段线，不搞贝塞尔。
- 新文件：`references/apattern-schema.json`（JSON Schema，格式标准，通用就靠它）、`references/apattern.md`（一页说明）、`server/src/pattern_making/apattern.py`（DXF → `.apattern` 转换器：读 DXF 块内坐标、读线段锚点、起名点、抽边弧线、缝份参数、配对校验、Schema 校验；重测每条线段、核对每条边弧长，差 0.05 cm 以上报错）。
- 新工具：第 6 个 MCP 工具 `dxf_to_apattern` + CLI `pattern apattern`（`--in/--anchors/--quantified/--names/--meta/--out`）。MCP 测试加一项（165-96 v0.2 全套），全套通过。
- 首个 `.apattern`：`jobs/tshirt-165-96/outputs/v0.2/tshirt-165-96-M.apattern`（4 片、36 个有名点、20 条线段、12 条边、2 条校验全过；边弧长与线段长逐条核对无误）。转换中修了两个 bug：GBK 块名要重解码（前/后/袖/领），多段线段（领围、袖山）要按分段串弧线、不能取首尾最短弧（袖山 50.80 会被错取成底边 46.55）。
- SKILL.md 升 0.1.3：工具表加 `reanchor_segments` + `dxf_to_apattern`，流程加第 6 步（出 `.apattern`），job 结构图改成每版一个 `.apattern`。job-contract.md 同步改。老版的 quantified.json + segments.md + segments-anchors.json 留着不动，不重写历史。
- 未推（等用户说“推”）。

## 2026-11-06 — 清掉 Teagan 残留，write_dxf 夹具换成用户自己的 163 T 恤

- 用户决定：项目里不留 FreeSewing 相关内容。`server/tests/fixtures/teagan-paths-v2.json`（FreeSewing Teagan 款点列）删掉；`write_dxf.py`、`cli.py`、`server.py`、`test_mcp_client.py`、`server/README.md`、SKILL.md、`references/aama-dxf.md` 里所有 "Teagan" 改名——夹具与款名改成用户的 163 T 恤（`tee163-paths.json`，STYLE=Tee163）。
- 新夹具由用户自己的 163 T 恤模板量化数据生成：`jobs/tshirt-template/outputs/v0.1/quantified.json` 的前/后/袖三片，净线（层 14）作 seam、裁剪线（层 1）作 sa、丝缕线（层 7）作 grainline，坐标归一化为 Y-down 局部坐标，Douglas-Peucker 1.0 mm 简化（552→26 点/片）。回读验证：净线前片 271.0×684.8、周长 177.3 cm，与量化原值 270.9×684.8、177.4 cm 一致；裁剪线周长 +1.2 cm 是 --miter 尖角的正常增量。
- MCP 测试断言同步改：write_dxf 171 个 #、0 个刀口（163 模板无刀口）。MCP 全套测试重跑通过。只改夹具与命名，不升版本。

## 2026-11-06 — 测试去掉硬编码路径（jobs 根目录可配置）

- `server/tests/test_mcp_client.py` 的 4 个绝对路径全去掉：`SERVER` 与 `teagan-paths-v2.json` 夹具改从测试文件自身位置推导（`Path(__file__)`，跟仓走）；裤子 DXF 与 quantified.json 改从 jobs 根目录推导，根目录可配（环境变量 `PATTERN_JOBS_ROOT`），默认 `~/workspace/jobs/`（只是本地默认值，不是写死的 HOME）。默认与显式设 `PATTERN_JOBS_ROOT=~/workspace/jobs` 两种跑法 MCP 全套测试都通过。只改测试，不升版本。

## 2026-11-06 — job 文件夹统一到 ~/workspace/jobs/ + 删 freesewing-teagan-test

- 所有量化的 job 文件夹统一到 `~/workspace/jobs/`（新顶层目录，通用型，Muse 和本地 OpenClaw 同一套结构）：`user-dxf-1`（裤子）、`tshirt-template`（163 T 恤）、`tshirt-pattern-v1`…`v3`、`brian-block-test` 从 `goals/.../files/` 搬过去；`your_files/` 里留同名软链指向新位置，方便找。job-contract.md 钉死根目录为 `~/workspace/jobs/`，SKILL.md 的路径同步改。
- 每 job 按 job-contract 整理：源 DXF 留根目录（老 job 原名保留，如 `1.dxf`、`tshirt.dxf`，新 job 用 `source.dxf`）；量化 JSON、编号图、ANALYSIS.md、SVG/PNG 收进 `outputs/v0.1/`；缺的 `requirements.md` 按已知事实补上（裤子、T 恤模板、v1–v3 各一份）。brian-block-test 本来就是标准结构，直接搬。
- `freesewing-teagan-test` 删掉（用户决定：项目跟 FreeSewing 已完全无关）。测试用的 `teagan-paths-v2.json` 收进仓里做夹具：`server/tests/fixtures/teagan-paths-v2.json`，测试改指这个路径；裤子测试路径改指 `jobs/user-dxf-1/`（DXF 在根目录，quantified.json 在 `outputs/v0.1/`）。MCP 全套测试重跑通过。

## 2026-11-06 — 删掉 FreeSewing

- 用户决定：DXF 处理流程（收文件、量化、画编号图、量弧线、拟合贝塞尔、写分析）全是 Python + ezdxf，一行 FreeSewing 没用到；FreeSewing 的量体跟用户的不合，生成链不用它。删干净，不留旧新并存。
- 删掉：`server/library/`（Brian、Teagan、零件库、40 套标准体、款 schema）、`server/engine/`（draft runner + measurements/settings/paths-format 数据）、`server/package.json` / `package-lock.json` / `node_modules/`（FreeSewing 框架 npm 依赖）、`server/src/pattern_making/freesewing.py`、MCP 工具 `draft_freesewing` / `freesewing_design_info`、CLI `pattern draft`、draft 相关测试。SKILL.md 的“生成”流程整节删掉，skill 只剩复刻一条链；根 README 目录架构与 server/README 同步改（4 个工具）。`write_dxf.py`、`aama-dxf.md`、`job-contract.md` 里 FreeSewing 的提法改成通用表述（输入点列的格式不变，写盘器照常用）。
- 留下：`quantify`、`plot`、`write_dxf`、`check` 四个 DXF 工具与 MCP/CLI 入口；复刻工作流；T 恤模板分析与贝塞尔参数化方案。从 FreeSewing 学到的东西（贝塞尔控制点取弦长分数、袖山迭代拟合、袖笼构造）已写在 T 恤模板 ANALYSIS.md 里，删代码不丢。`teagan-paths-v2.json`（存档点列）仍在 `your_files/freesewing-teagan-test/`，`write_dxf` 测试继续用它。
- 恢复办法：删掉的代码全在 git 历史里（最后在 `c621b43`），`git checkout c621b43 -- server/library server/engine server/package.json` 可拿回。版本不升（SKILL.md 仍 0.1.2，server 仍 0.2.0），不打新 tag。

## 2026-11-06 — quantify 直接输出 # 号坐标（第 6 步并入第 3 步）

- `quantify.py` 的 by-block（AAMA）模式现在每片输出 `numbered_points`：每个 `# N` 标签对应
  它命名的 POINT 点（`xy_mm`，与 outline_points 同一套模型空间坐标；`layer`；`text_offset_mm` =
  标签到点的距离）。以前 quantify 只记标签文字串和 POINT 个数，不记坐标，量袖笼/袖山还得
  再读一遍 DXF 去定位每个 # 号（第 6 步）；现在一次量化就全有了，第 6 步不再需要。
  匹配规则：标签与它命名的 POINT 在同一层（AAMA：2=拐点、4=刀口），先同层匹配，找不到才
  跨层找——避免把密集的 3 层曲线点误当成 # 号点。只改 `server/src/pattern_making/quantify.py`，
  不升版本。裤子 `user-dxf-1/quantified.json` 已用新版重跑（191 个 # 号），MCP 全套测试通过；
  T 恤 `tshirt-template/quantified.json` 也已重跑，# 号坐标与旧的 `numbered_points.json` 核对一致
  （差一个每片的模型空间平移，0.1mm 舍入内），旧的 `numbered_points.json` 已删，# 号坐标以
  `quantified.json` 为唯一来源。

## 2026-11-06 — draft 时去掉 measurements.json 的 source 键

- `freesewing.py` 的 `draft()` 在传给 runner 之前去掉 measurements 里的 `source` 键。`source` 是 job 格式的元数据（量体来源，check.py 要求有），不是量体；不去掉 runner 会报 `measurement 'source' is not used by ...` 的 warning，还会把它写进 summary 的 measurements 里。修后 Brian 测试版 draft 的 warnings 为空。只改 `server/src/pattern_making/freesewing.py`，不升版本。

## 2026-11-06 — 根 README 补目录架构说明

- 根 `README.md` 的“仓里有什么”改成完整的“目录架构”一节：整棵树 + 分层与边界（仓根 skill / server 工具、引擎与库、框架依赖与库源码、两个运行时一条 JSON 接口、数据文件是生成的、不在仓里的东西）+ 加东西往哪放的对照表。只改文档，不动代码。SKILL.md 工具一节补了一行指向（目录架构见 README.md），不重复贴树。

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
