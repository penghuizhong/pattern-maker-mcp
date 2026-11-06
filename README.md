# Pattern Making

制版 skill：把用户需求变成版本化的纸样 job。先写结构单，围度一律用户给（不猜数），几何由确定性脚本算，校验门 + 审批门通过后才能放行。

## 目录架构

```
pattern-maker-mcp/
├── SKILL.md                  # skill 本体：触发条件、铁律、工作流
├── CHANGELOG.md              # 按日期记的改动记录（版本号只在 SKILL.md 里）
├── README.md                 # 本文件
├── references/               # skill 的规范文档（只讲规矩，不含代码）
│   ├── aama-dxf.md           # DXF-AAMA 写入规范（层号、刀口、# 编号、回读验收）
│   ├── job-contract.md       # job 文件夹结构与 approval.md 模板
│   └── validation-gate.md    # 校验门 + 审批门的细则
└── server/                   # 可运行的包：CLI + MCP 服务器（pattern 命令）
    ├── README.md             # server 的安装、工具表、验证记录
    ├── pyproject.toml        # Python 包（pattern-making）：依赖与 CLI 入口
    ├── src/pattern_making/   # Python 工具（MCP 工具与 CLI 的实现）
    │   ├── server.py         # MCP 服务器（pattern serve，4 个工具）
    │   ├── cli.py            # CLI（pattern quantify/plot/write-dxf/check/serve）
    │   ├── quantify.py       # DXF → 量化 JSON（只量、不画、不改）
    │   ├── plot.py           # DXF → 编号图 PNG（ezdxf + matplotlib）
    │   ├── write_dxf.py      # JSON 点列 → DXF-AAMA（--miter 尖角）
    │   └── check.py          # 校验门 + 审批门
    └── tests/
        └── test_mcp_client.py  # MCP 端到端测试（起 pattern serve，4 个工具全调）
```

### 分层与边界

- **仓根是 skill，`server/` 是工具。** SKILL.md 只讲工作流和铁律，不含代码；几何和校验都在 `server/` 的工具里做（MCP 优先，CLI 备用）。
- **工具只做 DXF。** `quantify` / `plot` / `write_dxf` / `check` 全是 Python + ezdxf，不生成版型、不读别的格式。版型几何来自用户的 DXF（复刻链）或以后自家参数化打版的 JSON 点列。
- **不在仓里的东西。** `server/.venv/` 是装出来的依赖（`.gitignore` 已排除）；job 文件夹（`jobs/<款号>/`）按 `references/job-contract.md` 在使用时建，不进仓。

### 加东西往哪放

| 想加的东西 | 放哪里 |
|---|---|
| 一个新工具 | `server/src/pattern_making/` 加模块，`cli.py` 与 `server.py` 各加一行 |
| 一条新规范 | `references/` 加 `.md`，SKILL.md 里内联引用 |
| 一次改动记录 | `CHANGELOG.md` 先写条目再发版 |

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
- 没有“照片自动出西装纸样”：照片只能出结构单，几何走工具 + 校验门。
