# self-trust — 个人自律记账 / 资金池自我治理 skill

> English version: [README_EN.md](README_EN.md)

![tests](https://github.com/shellcdev/self-trust/actions/workflows/tests.yml/badge.svg)
![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.9%2B-blue)

> 设计规格（spec 真相源）：[`docs/DESIGN.md`](docs/DESIGN.md)（**本仓内**）——所有公式（F0~F8）、判定逻辑（§4.4）、schema（§2）、权限模型（§10.3）以该文档为准。
> 工程规范：本仓遵循宿主工作区的《工程统一规范》；OSS 贡献无需该文档，按本仓 [`CONTRIBUTING.md`](CONTRIBUTING.md) 即可。

把「现在的我」和「未来的你」拆成两个视角，用**确定性规则引擎**（Python 代码，非 AI 心算）按既定数学规则约束冲动支出。**这是个人自律记账/预算辅助工具，不具备任何法律效力**（详见设计文档 §0 性质声明）。

## 架构

「Python 引擎 + SKILL.md 薄路由」：公式、判定、状态机全在 `scripts/`；LLM 只做三件事——解析自然语言意图 → 调引擎 → 把引擎 JSON 润色成意见书。**LLM 禁止心算公式，数字必须原样引用引擎输出。**

## 数据目录解析优先级（规范 #6）

代码不写死数据路径，解析顺序（高 → 低）：

1. 命令行参数 `--data-dir <path>`
2. 环境变量 `SELFTRUST_DATA_DIR`
3. 默认 `<home>/.claw/self-trust/`（规范 §3 平台基址，`Path.home()` 解析；零 cwd 依赖、零硬编码机器绝对路径；数据在 skill 目录外，删 skill 不毁账本，且在 `.claw` 备份树内）

数据布局：`<data-dir>/contract.json`（契约）+ `<data-dir>/audit/*.jsonl`（审计，仅追加，物理分离）。

## 快速开始

```bash
# 初始化（懒人模板：3 项输入，其余固化 balanced 默认值）
python scripts/cli.py --data-dir <dir> init \
    --corpus 200000 --monthly 8000 \
    --objective "FIRE:3000000:2036-01-01"

# 审批判定（§4.4 三场景，输出结构化 JSON 含全部中间变量）
python scripts/cli.py --data-dir <dir> judge --amount 6000 --category 合理享受

# 审计留痕只读查询
python scripts/cli.py --data-dir <dir> log --name approval_log
```

## 测试

```bash
python -m pytest scripts/tests/ -q
```

测试纪律（规范 #8）：temp dir + `--data-dir` 覆盖，不碰真实数据；确定性可重放（无网络/无密钥）；失败即红灯不 skip。

## 目录

- `SKILL.md` — LLM 薄路由（触发词/命令表/铁律/references 索引）
- `references/` — 按需加载子文档（approval / exceptions / init / report / data-modes / contract-schema）
- `templates/` — 意见书三段式 / 三场景演示模板
- `scripts/core/` — formulas（F0~F8）/ contract（三区权限）/ models（schema+状态机）/ audit（仅追加）
- `scripts/modules/` — judge / calibrate / report / initialize
- `STATUS.md` — 当前实现状态（真相源，被问进度先读它）

## 安装 / Install

本仓既是**确定性 Python 引擎**，也是 **WorkBuddy skill**（LLM 薄路由）。两种用法：

- **当 Python 引擎独立使用**（无需 WorkBuddy）：克隆后直接跑 `scripts/cli.py`。

  ```bash
  git clone https://github.com/shellcdev/self-trust.git
  cd self-trust
  python -m pytest scripts/tests/ -q   # 验证
  python scripts/cli.py --data-dir /tmp/st-demo init --corpus 200000 --monthly 8000 --objective "FIRE:3000000:2036-01-01"
  ```

- **当 WorkBuddy skill 安装**：把本仓放进 skills 目录（符号链接亦可），LLM 按 `SKILL.md` 路由调用 `scripts/cli.py`。

  ```bash
  # 例：链接到用户级 skills 目录
  ln -s "$(pwd)" ~/.workbuddy/skills/assist-Z-self-trust
  ```

## 许可证 / License

[MIT](LICENSE)。作者以匿名方式提交，欢迎 fork / 修改 / 提 PR。
