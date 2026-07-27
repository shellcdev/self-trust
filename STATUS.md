# STATUS — self-trust 实现状态

> 真相源在本文件（仓内 dev doc），不在记忆。状态标记：✅ 已实现 / ⚠️ 部分（骨架可跑，业务未完） / 待实施 / ❌ 已废弃。

更新：2026-07-27（骨架初建）

## 当前阶段：骨架（scaffold）

| 模块 | 状态 | 说明 |
|---|---|---|
| `core/formulas.py` F0~F8 | ✅ | 纯函数 + doctest（文档示例数字），除零/null/超期 clamp 守卫齐 |
| `core/models.py` schema/三区/状态机 | ✅ | dataclass 契约 + FIELD_ZONES + pending_requests 状态机守卫 |
| `core/contract.py` 读写+权限强制 | ✅ | data-dir 三级解析；engine 写配置区必拒；§5.4 闸门（confirm 参数模拟） |
| `core/audit.py` 仅追加 | ✅ | audit/*.jsonl 仅追加，无删除接口，损坏显式报错 |
| `modules/initialize.py` 懒人模板 | ✅ | §7.1 护栏 1/2/3/4 全实现；演示（§7.2）为 stub |
| `modules/judge.py` | ⚠️ | 三场景路由/白名单双上限/冷静期触发已实现；lag 恶化校验、pending 入队、optimization_goal 调度、imported_pending 拦截 → 待实施 |
| `modules/calibrate.py` | 待实施 | stub：缓冲/柔性/收入放松/回滚全未实装（§6.2/§6.4） |
| `modules/report.py` | 待实施 | stub：进度条/趋势图/月度快照未实装（§6.1） |
| `cli.py` | ⚠️ | 7 子命令注册齐 + JSON 输出 + 错误码；reconcile/reward 为 stub |
| 冷静期状态机落盘（§5.1） | 待实施 | models 状态机已备，judge 入队/提醒/迁移未接 |
| 申诉/覆写（§5.2） | 待实施 | appeal_count 字段已备，流程未实装 |
| 记账重置（§7.1.1） | 待实施 | |
| 第三方导入（§7.3） | 待实施 | 首版砍掉（§8.3 取舍 #3），schema 已预留 corpus_status |
| SKILL.md + references + templates | ✅ | 真实占位内容（引用设计文档章节），随实装迭代 |
| 测试 | ✅ | 85 通过：formulas 全量 / contract_guard 全量 / audit 全量 / judge 骨架 / calibrate 冒烟 |

## 下一步（后续 PR 顺序建议）

1. judge 补全：lag 恶化（F4 接 objectives）+ pending_requests 入队落盘 + imported_pending 拦截
2. 冷静期生命周期：撤回激励（§5.1.1）/ 到期终裁 / 双阶段提醒（惰性检查）
3. report 实装（§6.1 双可视化 + monthly_history 快照）
4. calibrate 实装（§6.2 缓冲/柔性/放松/回滚 + §6.4 生命周期）
5. 申诉/覆写/记账重置/奖励支取（§5.2 / §7.1.1 / §6.3）
