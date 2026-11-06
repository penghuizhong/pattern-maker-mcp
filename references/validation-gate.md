# Validation gate — 校验门与审批门

## 机器门：check_job.py（每次出版必跑）

```bash
python3 scripts/check_job.py --job jobs/<款号>
python3 scripts/check_job.py --job jobs/<款号> --release
```

普通检查（不带 `--release`）查：

1. `requirements.md`、`measurements.json`、`design.json` 存在且 JSON 合法；
2. `measurements.json` 引用的表在 `measurements/` 里存在，码段在表里齐全；
3. `design.json` 的 `open_items` 和 `requirements.md` 的 OPEN 项一致（不能一边写 OPEN、一边当定稿）；
4. 本版 `outputs/<版本>/` 存在，`verification.json` 存在；
5. 放码恒量自检通过（由 verification.json 里的记录证明）。

## 机器门：几何校验（有产物时必做）

有 SVG/DXF 产物时，跑 Seamlint（`slnt check`，npm 包 `seamlint`，只读）：

- 缝长不匹配、拐点、断口、切线不连续、松量比异常，全部记进 `verification.json`，不能只报“通过”。
- Seamlint 量不出来时写 `unmeasurable` + 原因，不能编一个通过。Seamlint 只量不改，改图要回引擎重跑。

## 人门：approval.md（放行前必须有）

`--release` 在普通检查之外还要求：

1. `verification.json` 的 `status` 为 `pass`；
2. `approval.md` 里有用户明确的放行记录：日期、版本号、放行范围（发工厂 / 裁样衣 / 仅内部看样，三选一写清）；
3. `design.json` 的 `open_items` 为空——有 OPEN 项时 `--release` 必须失败，哪怕用户口头说“先发”，也要先把 OPEN 项清掉或在 approval.md 里逐项写明“已知风险、用户坚持放行”。

**agent 没有放行权。** 脚本退出非 0 时，agent 的唯一正确动作是停下来、把失败项原样报给用户，不能换个说法再报一次、不能自己改数让它通过。

## 交付用语

- 通过：写“本版校验通过：……（附 verification.json）”。
- 没通过：写“本版未通过：……（失败项原文）”，不写“基本通过”“差不多”。
- 没实机验证：写“待实机验证：……”，不写“已验证”。
