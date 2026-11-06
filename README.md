# Pattern Making

制版 skill：把用户需求变成版本化的纸样 job。先写结构单，围度一律用户给（不猜数），几何由确定性脚本或引擎算，校验门 + 审批门通过后才能放行。

## 目录架构

```
pattern-maker-mcp/
├── SKILL.md                  # skill 本体：触发条件、铁律、两条工作流
├── CHANGELOG.md              # 按日期记的改动记录（版本号只在 SKILL.md 里）
├── README.md                 # 本文件
├── references/               # skill 的规范文档（只讲规矩，不含代码）
│   ├── aama-dxf.md           # DXF-AAMA 写入规范（层号、刀口、# 编号、回读验收）
│   ├── job-contract.md       # job 文件夹结构与 approval.md 模板
│   └── validation-gate.md    # 校验门 + 审批门的细则
└── server/                   # 可运行的包：CLI + MCP 服务器（pattern 命令）
    ├── README.md             # server 的安装、工具表、验证记录
    ├── pyproject.toml        # Python 包（pattern-making）：依赖与 CLI 入口
    ├── package.json / package-lock.json
    │                         # Node 依赖清单：FreeSewing 框架（exact 4.10.2）
    ├── engine/               # 通用生成纸样引擎（给数据，出纸样）
    │   ├── README.md         # 引擎地图：框架、数据结构、runner、加款办法
    │   ├── runner/draft.mjs  # 通用 runner：库优先、npm 兜底，什么款都不定死
    │   └── data/             # 数据结构（generate.mjs 生成，勿手改）
    │       ├── measurements.json   # 42 个标准量体（只有 shoulderSlope 是角度）
    │       ├── settings.json       # core 默认值 + sa 默认 10mm
    │       ├── paths-format.md     # 点列 JSON 格式说明
    │       └── generate.mjs        # 数据生成器（升版、加款后重跑）
    ├── library/              # 基础纸样库（公式源码在仓里，可扩展）
    │   ├── README.md / NOTICE.md   # 库地图 / MIT 归属（FreeSewing 4.10.2）
    │   ├── blocks/brian/     # 男装身原型：前后身 + 袖子，11 个量体
    │   ├── designs/teagan/   # 收腰针织 T（站在 Brian 肩膀上），13 个量体
    │   ├── parts/library/    # 可复用部件：袖子、矩形、两片袖、三片帽
    │   └── data/             # 款式数据（generate.mjs 生成，勿手改）
    │       ├── models.json         # 40 套标准量体（neckstimate 从颈围推算）
    │       └── schemas/<款>.json   # 各款要什么量体、选项的默认值与上下限
    ├── src/pattern_making/   # Python 工具（MCP 工具与 CLI 的实现）
    │   ├── server.py         # MCP 服务器（pattern serve，6 个工具）
    │   ├── cli.py            # CLI（pattern quantify/plot/write-dxf/check/draft/serve）
    │   ├── quantify.py       # DXF → 量化 JSON（只量、不画、不改）
    │   ├── plot.py           # DXF → 编号图 PNG（ezdxf + matplotlib）
    │   ├── write_dxf.py      # FreeSewing 点列 → DXF-AAMA（--miter 尖角）
    │   ├── check.py          # 校验门 + 审批门
    │   └── freesewing.py     # 调 Node runner 的封装（draft_freesewing）
    └── tests/
        └── test_mcp_client.py  # MCP 端到端测试（起 pattern serve，6 个工具全调）
```

### 分层与边界

- **仓根是 skill，`server/` 是工具。** SKILL.md 只讲工作流和铁律，不含代码；几何和校验都在 `server/` 的工具里做（MCP 优先，CLI 备用）。
- **引擎与库是两样东西。** `server/engine/` 是生成引擎（框架 + runner + 数据结构），`server/library/` 是基础纸样库（款的公式源码）。引擎不含任何一款，库不含任何引擎代码。
- **框架是依赖，库是源码。** FreeSewing 框架（core + 插件）是 pinned 的 npm 依赖，不 fork；纸样库是源码进仓，公式看得见、改得了。自家款（比如量体裤公式）按 `library/README.md` 的形状放进库里就能打。
- **两个运行时，一条 JSON 接口。** 生成是 Node（FreeSewing），DXF 读写是 Python（ezdxf）；中间用 JSON 点列接（格式见 `server/engine/data/paths-format.md`）。FreeSewing 不读 DXF，Python 不画版型。
- **数据文件是生成的。** `engine/data/` 与 `library/data/` 下的 `.json` 由 `engine/data/generate.mjs` 从框架和库里生成，改框架版本或加款后重跑，不要手改。
- **不在仓里的东西。** `server/node_modules/` 与 `server/.venv/` 是装出来的依赖（`.gitignore` 已排除）；job 文件夹（`jobs/<款号>/`）按 `references/job-contract.md` 在使用时建，不进仓。

### 加东西往哪放

| 想加的东西 | 放哪里 |
|---|---|
| 一个新款（或自家版型） | `server/library/<分类>/<款名>/`，再跑 `node server/engine/data/generate.mjs` |
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
- 没有“照片自动出西装纸样”：照片只能出结构单，几何走工具/引擎 + 校验门。
