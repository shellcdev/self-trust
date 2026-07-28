# self-trust — Personal Self-Discipline Bookkeeping / Cash-Pool Self-Governance Skill

![tests](https://github.com/shellcdev/self-trust/actions/workflows/tests.yml/badge.svg)
![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.9%2B-blue)

> 中文版： [README.md](README.md)
> Design spec (source of truth): [`docs/DESIGN.md`](docs/DESIGN.md) (**in this repo**) — all formulas (F0~F8), decision logic (§4.4), schema (§2), and the permission model (§10.3) are defined there.
> Engineering conventions: this repo follows the host workspace's *Unified Engineering Spec*; OSS contributors don't need it — just follow [CONTRIBUTING.md](CONTRIBUTING.md).

Separate "the person you are now" from "the person you'll be", and use a **deterministic rule engine** (Python code, not AI guesswork) to constrain impulsive spending by fixed mathematical rules. **This is a personal self-discipline bookkeeping / budgeting aid and carries no legal effect whatsoever** (see design doc §0 nature statement).

## Architecture

"Python engine + thin SKILL.md router": formulas, decisions, and the state machine all live in `scripts/`; the LLM does only three things — parse natural-language intent → call the engine → polish the engine's JSON into a written opinion. **The LLM must never compute formulas itself; numbers must be quoted verbatim from engine output.**

## Data Directory Resolution Priority (Spec #6)

Paths are not hardcoded. Resolution order (high → low):

1. CLI flag `--data-dir <path>`
2. Environment variable `SELFTRUST_DATA_DIR`
3. Default `<home>/.claw/self-trust/` (spec §3 platform base, resolved via `Path.home()`; zero cwd dependency, zero hardcoded absolute machine paths; data lives outside the skill dir so deleting the skill won't destroy the ledger, and it sits inside the `.claw` backup tree)

Data layout: `<data-dir>/contract.json` (contract) + `<data-dir>/audit/*.jsonl` (audit, append-only, physically separated).

## Quick Start

```bash
# Initialize (lazy template: 3 inputs, rest fixed to balanced defaults)
python scripts/cli.py --data-dir <dir> init \
    --corpus 200000 --monthly 8000 \
    --objective "FIRE:3000000:2036-01-01"

# Approval judgment (§4.4 three scenarios, outputs structured JSON with all intermediate variables)
python scripts/cli.py --data-dir <dir> judge --amount 6000 --category reasonable-enjoyment

# Read-only audit query
python scripts/cli.py --data-dir <dir> log --name approval_log
```

## Tests

```bash
python -m pytest scripts/tests/ -q
```

Test discipline (spec #8): temp dir + `--data-dir` override, never touch real data; deterministic and replayable (no network / no keys); failure is a red light, never a skip.

## Directory

- `SKILL.md` — thin LLM router (trigger words / command table / iron rules / references index)
- `references/` — on-demand sub-docs (approval / exceptions / init / report / data-modes / contract-schema)
- `templates/` — three-part opinion template / three-scenario demo templates
- `scripts/core/` — formulas (F0~F8) / contract (three-zone permissions) / models (schema + state machine) / audit (append-only)
- `scripts/modules/` — judge / calibrate / report / initialize
- `STATUS.md` — current implementation status (source of truth; read it first when asked for progress)

## Install

This repo is both a **deterministic Python engine** and a **WorkBuddy skill** (thin LLM router). Two ways to use it:

- **As a standalone Python engine** (no WorkBuddy needed): clone and run `scripts/cli.py` directly.

  ```bash
  git clone https://github.com/shellcdev/self-trust.git
  cd self-trust
  python -m pytest scripts/tests/ -q   # verify
  python scripts/cli.py --data-dir /tmp/st-demo init --corpus 200000 --monthly 8000 --objective "FIRE:3000000:2036-01-01"
  ```

- **As a WorkBuddy skill**: drop this repo into your skills directory (symlink works too); the LLM routes calls to `scripts/cli.py` per `SKILL.md`.

  ```bash
  # e.g. link into the user-level skills directory
  ln -s "$(pwd)" ~/.workbuddy/skills/assist-Z-self-trust
  ```

## License

[MIT](LICENSE). Commits are made anonymously; forks / modifications / PRs are welcome.
