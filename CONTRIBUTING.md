# 贡献指南 / Contributing

谢谢你有兴趣改进 self-trust。本仓是**确定性规则引擎**（Python 标准库），LLM 只做路由与润色。

## 开发环境

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"   # 仅装 pytest
```

要求 Python >= 3.9。

## 跑测试

```bash
python -m pytest scripts/tests/ -q
```

测试纪律（项目铁律）：
- 全部用临时目录 + `--data-dir` 覆盖，**绝不碰真实账本数据**；
- 确定性、可重放（无网络、无密钥、无随机）；
- 失败即红灯，**不 skip**；
- 改了公式 / 判定 / schema / 权限，必须同步 `CHANGELOG.md`、`STATUS.md`、`SKILL.md` 与 `docs/DESIGN.md`（设计规格真相源）。

## 提交 / PR

- 本仓历史以**匿名**方式提交（`anonymous <noreply@localhost>`），不要求真实姓名；你也可以用自己的 GitHub 隐私邮箱。
- 一个逻辑一个提交，信息用中文或英文均可，说清**动机**与**影响范围**。
- PR 描述请包含：改了什么、为什么、测试如何验证。
- 涉及公式（F0~F8）、判定（§4.4）、权限模型（§10.3）的改动，请对照 `docs/DESIGN.md` 说明是否偏离规范。

## 文档结构

- `docs/DESIGN.md` — 设计规格真相源（公式 / schema / 判定 / 权限）。
- `references/` — 按需加载的子文档（审批 / 异常 / 初始化 / 报表 / 数据模式 / schema）。
- `templates/` — 意见书 / 演示模板。
- `scripts/core/` — formulas / contract（三区权限）/ models / audit。
- `scripts/modules/` — judge / calibrate / report / initialize / customize / governance / import_asset / reward / streaks。
