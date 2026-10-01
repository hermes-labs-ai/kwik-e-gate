# Adaptive calibrate (experimental)

Thin-slice **prior → proposed `.hermes/gate.toml`** for Kwik / hermes-gate.

This directory is **experimental**. It does **not** replace `kwik-gate init` /
`hermes_gate.init_repo`, and it is **not** wired into the shipping CLI yet.

## Contents

| Path | Role |
| --- | --- |
| [PRD-adaptive-kwik-2026-10-01.md](./PRD-adaptive-kwik-2026-10-01.md) | Product intent for adaptive Kwik |
| [SPIKE-ANALYSIS.md](./SPIKE-ANALYSIS.md) | What v1 proved, gaps, v2 requirements |
| [V2-TEST-LOG.md](./V2-TEST-LOG.md) | Pytest + dry-run evidence on Hermes repos |
| [v2/calibrate.py](./v2/calibrate.py) | Runnable calibrate CLI (stdlib) |
| [v2/fixtures/](./v2/fixtures/) | Tiny fake repos for tests |
| [v2/test_calibrate.py](./v2/test_calibrate.py) | Pytest coverage |

## Run (dry-run default)

```bash
python3 docs/adaptive-calibrate/v2/calibrate.py /path/to/repo
python3 docs/adaptive-calibrate/v2/calibrate.py /path/to/repo --dry-run
```

JSON on stdout includes `priors`, `requires`, and `proposed_toml`. Nothing is
written unless you pass `--write` (refuses overwrite without `--force`).

## Tests

```bash
python3 -m pytest docs/adaptive-calibrate/v2/test_calibrate.py -v
```

Requires pytest. The schema smoke test optionally imports `hermes_gate.config`
when `src/` is on `PYTHONPATH` (as in a kwik-e-gate checkout).

## What it detects

- Python markers: `pyproject.toml`, `setup.py`, `requirements*.txt`
- JS lockfiles: npm / pnpm / yarn (recorded; script checks not inferred)
- `.hermes/gate.toml` presence
- Instruction surface: `INTENT.md`, `SPEC.md`, `AGENTS.md`, `skills/`
- PATH probes: ruff, pytest, lintlang, intent-verify

When instruction-surface files exist it proposes a `[lintlang]` table and an
optional `lintlang-scan` named check. When `INTENT.md` or `SPEC.md` exists it
proposes an optional `intent-verify` named check. Tools are **not** installed;
proposals carry `# requires:` comments.

## Non-goals (still)

- No LintLang scan wiring into calibrate logic
- No merge with `init_repo`
- No replacing the Action / Marketplace front door
