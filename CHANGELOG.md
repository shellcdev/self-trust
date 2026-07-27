# CHANGELOG — self-trust

## [0.1.0] - 2026-07-27

### Added
- 骨架初建（独立 git 仓库）：目录结构按设计文档 §8.3 落地。
- `core/formulas.py`：F0~F8 全公式纯函数 + doctest（文档示例数字防漂移）。
- `core/models.py`：契约 schema dataclass + 三区权限映射（FIELD_ZONES）+ pending_requests 状态机。
- `core/contract.py`：契约读写 + data-dir 三级解析（--data-dir > SELFTRUST_DATA_DIR > 默认）+ 三区权限强制（engine 写配置区必拒，§5.4 闸门）。
- `core/audit.py`：审计仅追加（audit/*.jsonl）+ F8 快照落盘，无删除接口。
- `modules/initialize.py`：§7.1 懒人模板（重复初始化拒绝/净口径警告/deadline 校验/对账锚点）。
- `modules/judge.py`：§4.4 三场景路由骨架 + 白名单双上限 + 冷静期触发（lag 校验等留 stub）。
- `cli.py`：judge|init|report|reconcile|calibrate|reward|log 七子命令，全 JSON 输出，错误显式返回。
- 测试 85 例全绿（formulas / contract_guard / audit / judge / calibrate）。
- SKILL.md 薄路由 + references 六篇 + templates 两篇（真实占位内容）。
