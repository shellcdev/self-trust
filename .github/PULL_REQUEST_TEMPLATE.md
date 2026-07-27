## 改动摘要 / Summary

<!-- 改了什么、为什么 -->

## 影响范围 / Scope

- [ ] 公式（F0~F8）
- [ ] 判定逻辑（§4.4）
- [ ] 权限模型（§10.3）
- [ ] `contract.json` schema
- [ ] CLI 子命令 / 参数
- [ ] 仅文档 / 测试

## 验证 / Verification

```bash
python -m pytest scripts/tests/ -q
```

- [ ] 测试全绿
- [ ] 已同步 `CHANGELOG.md` / `STATUS.md` / `SKILL.md`（如涉及逻辑）
- [ ] 未包含真实账本数据
