# Pattern Making

制版 skill：把用户需求变成版本化的纸样 job。先写结构单，围度一律用户给（不猜数），几何由确定性脚本或引擎算，校验门 + 审批门通过后才能放行。

## 仓里有什么

- `SKILL.md` — 触发条件、铁律、工作流
- `references/` — DXF-AAMA 规范、job 契约、校验门
- `server/` — 工具的 CLI + MCP 服务器（`pattern` 命令，见 `server/README.md`）

## 使用

把本文件夹放进你的 agent 的 skills 目录即可。几何和校验走 `server/` 的工具：按 `server/README.md` 装好 `pattern` 命令（venv + `pip install -e .`），MCP 用 `pattern serve`，或直接用 `pattern` 命令。

## 快速验证

```bash
# 先按 server/README.md 装好 pattern 命令，再跑：
mkdir -p /tmp/pattern-job-smoke/outputs/v0.1
printf '结构单\n' > /tmp/pattern-job-smoke/requirements.md
printf '{"source": "用户量体 2026-11-06", "sizes": ["M"]}' > /tmp/pattern-job-smoke/measurements.json
printf '{"version": "v0.1", "open_items": []}' > /tmp/pattern-job-smoke/design.json
printf '{"status": "pass"}' > /tmp/pattern-job-smoke/verification.json
pattern check --job /tmp/pattern-job-smoke
# 下面这条必须失败（没有 approval.md），失败就是门在工作：
pattern check --job /tmp/pattern-job-smoke --release
```

## 版本管理

- 版本号只写在 `SKILL.md` 的 frontmatter `version` 字段里，其他文件不写版本号，防不同步。
- 每次改动先在 `CHANGELOG.md` 里写条目（按日期记）再发版。
- 发版时在 git 里按 `SKILL.md` 的 version 打 tag，tag 随 main 一起推。

## 现阶段不承诺的事

- 没有工业西装纸样原型（驳头、袖窿、挂面、半毛衬）：下一阶段单独写。
- 没有排料、面料缩率模型、工艺单自动生成。
- 没有“照片自动出西装纸样”：照片只能出结构单，几何走工具/引擎 + 校验门。
