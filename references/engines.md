# Engines — 引擎与工具对照（2026-11-03 实查）

## 可复用核心（任意 agent 环境可跑）

| 工具 | 协议 | agent 调用方式 | 备注 |
|---|---|---|---|
| pattern-making-skill | MIT | skill + `pattern.py`（标准库） | 最贴合本 skill 的纪律：AI 只传参数，脚本算几何、每步缝份校验；出 SVG/DXF/CLO JSON；1 star，需审原型 |
| FreeSewing + pattern-via-io | MIT | stdin JSON → stdout SVG/JSON（Node） | GitHub 主仓已归档、已迁 Codeberg；约 65 款，偏居家款，不做放码、不出工业 DXF |
| GarmentCode (PyGarment) | MIT | Python 程序合成 | ETH 研究项目，MetaGarment 组件化；适合“AI 出程序参数”路线，较重，无西装原型 |
| Seamlint | npm 包 | `slnt check`（只读） | 读 SVG/ASTM DXF，报缝长、拐点、断口、松量比；只量不改 |
| Loomit | 见其 LICENSE | `loom diff`（CLI） | Git 风格版片管理，纯文本 `.part.loom`，diff 读作制版决策；出图仍交给外部 CAD |

## 本地限定（需桌面环境）

| 工具 | 限定原因 | 备注 |
|---|---|---|
| clo3d-mcp-extended | 桌面 CLO + MCP 插件 | 170 工具，实测 Windows 11 + CLO 2025.2；macOS 回退未测试；没装 CLO 时标记待实机验证 |
| pattern-to-style3d | 桌面 RP DGS + Style3D | Codex skill；PXF 目前只有轮廓，不承诺内部线、纱向、剪口、缝合；版本敏感（9.2.880 直线控制点结构） |
| OpenMarker 排料 | 本地 FastAPI + 桌面 | 自认未到生产可用，导出流程还在计划中；只能参考，不能当生产排料 |

## 外部导出工具

- **Seamly2D（GPLv3）：** 有无界面导出模式（`-m` 围度、`-b` 输出名、`-d` 目录、`-f` 格式：SVG=0、PDF=1、DXF R10=6，多码 `-x/-gheight`）。agent 可以批量导出，但写 `.val` 原型仍是 GUI 活儿；GPL 代码不嵌进闭源产品，只当外部工具。
- **商业软件（CLO3D、Style3D、Gerber、Lectra、Optitex）：** 只走用户自己的授权和安装，不替用户注册、不绕授权。DXF-AAMA/ASTM 是工厂互通的格式目标，garment.dev 的做法（放码 X/Y 规则 + 校验报告、排料约束、34 个主流 CAD 文件对过）是工业门槛参考，不是可复用的开源代码。
- **DXF-AAMA 写盘（本 skill 自有，2026-11-05）：** 见 `references/aama-dxf.md`；实现 `scripts/to-dxf-v3.py`（R12、标准层、双份刀口、双份片名、显式封口），验收用回读校验。Teagan 单码 M 已出 `teagan-fitted-v3.dxf` 并全项通过；ETCAD 读回实测待用户做。

## 本仓现阶段不承诺的事

- 没有工业西装原型：驳头、袖窿、挂面、半毛衬结构必须下一阶段单独写，不能用基础原型冒充。
- 没有排料、没有面料缩率模型、没有工艺单自动生成：这三项是下一阶段的待办，不是现阶段的交付。
- 没有“照片自动出西装纸样”：照片只能出结构单和分析，几何必须走脚本/引擎 + 校验门。
