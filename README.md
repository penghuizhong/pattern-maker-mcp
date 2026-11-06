# Pattern Making

制版 skill：把用户需求变成版本化的纸样 job。先写结构单，围度只认锁定的表，几何由确定性脚本或引擎算，校验门 + 审批门通过后才能放行。

## 仓里有什么

- `SKILL.md` — 触发条件、铁律、工作流
- `references/` — DXF-AAMA 规范、job 契约、校验门
- `measurements/` — 男女西装成衣尺寸表的机器版（JSON）
- `scripts/` — 校验、DXF 量化（Python 标准库为主）
- `examples/womens-suit-M/` — 能跑通的示例 job：证明围度 + 放码 + 校验门，**不是纸样**

## 使用

把本文件夹放进你的 agent 的 skills 目录即可。skill 文件本身不依赖任何专属能力：只有 Markdown + Python 标准库脚本。

## 快速验证

```bash
python3 scripts/check_job.py --job examples/womens-suit-M
# 下面这条必须失败（没有 approval.md、还有 OPEN 项），失败就是门在工作：
python3 scripts/check_job.py --job examples/womens-suit-M --release
```

## 版本管理

- 版本号只写在 `SKILL.md` 的 frontmatter `version` 字段里，其他文件不写版本号，防不同步。
- 每次改动先在 `CHANGELOG.md` 里写条目（按日期记）再发版。
- 发版时在 git 里按 `SKILL.md` 的 version 打 tag，tag 随分支一起推。

## 现阶段不承诺的事

- 没有工业西装纸样原型（驳头、袖窿、挂面、半毛衬）：下一阶段单独写。
- 没有排料、面料缩率模型、工艺单自动生成。
- 没有“照片自动出西装纸样”：照片只能出结构单，几何走脚本/引擎 + 校验门。
