# Changelog

按日期记。每次改动先写条目再发版；版本号只写在 SKILL.md 里（frontmatter 的 `version` 字段），发版时按它打 git tag。

## 2026-11-06 — SKILL.md 重构：只讲通用流程

- 标题去掉版本号；版本号只剩 frontmatter 的 `version` 字段（README 版本管理一节同步改了）。
- 删掉所有硬编码的款形字眼（西装、T 恤、男女装）：流程只讲通用步骤，款式只出现在 job 数据和 `measurements/` 表里，不出现在 skill 正文里。
- `协议红线` 整节删除；`参考文件` 一节删除，两个只在那里出现的引用改到步骤里内联（出图 → curves.md，校验门 → validation-gate.md）。
- scripts/ 只留 check_job.py、dxf_quantify.py、to-dxf-v3.py：tshirt.py、grading.py 已删；第 2 步放码改按 grading.md 恒量自检，不再跑脚本。
- job-contract.md 补 approval.md 模板格式（日期、版本、放行范围、已知风险；对齐 check_job.py --release 的四点检查）。
- references/ 只留 aama-dxf.md、job-contract.md、validation-gate.md：curves.md、engines.md、grading.md、measurements.md 已删；SKILL.md 第 2、3 步的引用同步改成直接表述（按表验算恒量、曲线纪律一行）。
- 再重构：SKILL.md 改写成两条通用流程（FreeSewing 生成、DXF 复刻）；Python/GarmentCode 生成路线删掉（没跑通过的链路）；pattern.py 悬空引用随之消除。

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
