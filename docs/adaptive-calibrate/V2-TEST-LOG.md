# V2-TEST-LOG — adaptive kwik calibrate v2

**Date:** 2026-10-01 (EDT)  
**Scope:** `/workspace/kwik-adaptive-prd/v2/` (`calibrate.py`, fixtures, pytest)  
**Result:** pytest 9 passed. Dry-run exit 0 on `/workspace/kwik-e-gate`, `/workspace/lintlang`, and shallow `/workspace/intent-verify`. No writes. All proposals load via `hermes_gate.config.load_config`.

## How this was run

```
/workspace/kwik-e-gate-venv/bin/python -m pytest v2/test_calibrate.py -v --tb=short
/usr/bin/python3 v2/calibrate.py <repo> --dry-run
```

`python` is not on PATH; CLI dry-runs used `/usr/bin/python3`. LintLang and intent-verify were **not** on PATH for these probes.

## Pytest

```
9 passed in 0.52s
```

Covered: python-only, js-only, intent-surface (INTENT + AGENTS + skills), mixed python+SPEC+locks, dry-run non-write, write create, refuse without force, force overwrite, schema load via shipping `hermes_gate.config.load_config`.

## Dry-run: `/workspace/kwik-e-gate`

- Exit: 0; `wrote`: false; gate.toml SHA-256 unchanged: `99c0ee1ec4d023565516bfde355c926a0015a5e92a5c5a1ae790e11128ef0b8e`
- Priors: python=`pyproject.toml`; package_managers=`npm`; gate_toml_exists=true; instruction_surface via `AGENTS.md` + `skills/`; no INTENT/SPEC → no intent-verify check
- requires: `ruff`, `pytest`, `lintlang`
- Proposed checks: python-ruff (fast+full), python-test, lintlang-scan; `[lintlang].enabled=false` (binary missing)
- `next_command`: `install kwik candidate`
- Schema load: OK (`lintlang.enabled=False`, `review_required=False`)

## Dry-run: `/workspace/lintlang`

- Exit: 0; `wrote`: false (existing `.hermes/gate.toml` untouched)
- Priors: python=`pyproject.toml`; instruction files `INTENT.md`, `AGENTS.md`; `skills/` present; intent_spec=`INTENT.md`
- requires: `ruff`, `pytest`, `lintlang`, `intent-verify`
- Proposed: python checks + `intent-verify check --spec INTENT.md` + `lintlang-scan`; `[lintlang].enabled=false` (not on PATH)
- Schema load: OK; full names include `intent-verify`, `lintlang-scan`

## Dry-run: `/workspace/intent-verify` (shallow clone)

- Cloned: `git clone --depth 1 https://github.com/hermes-labs-ai/intent-verify.git`
- Exit: 0; no `.hermes/` present; nothing written
- Priors: python=`pyproject.toml`; `AGENTS.md` + `skills/` (no root INTENT.md/SPEC.md — samples live under `examples/`); intent_spec=null
- requires: `ruff`, `pytest`, `lintlang` (no intent-verify check without root INTENT/SPEC)
- Schema load: OK

## Still stubbed

- LintLang **scan** not invoked; only PATH/module availability. `[lintlang].enabled` stays false when missing.
- No merge/diff with `hermes_gate.init_repo` / `kwik-gate init`.
- No `package.json` content reads → no npm lint/test argv from scripts.
- Optional named checks proposed even when tools are absent (`# requires:` comments).
- Root-only filename priors; no recursive walk; no content reads of INTENT/SPEC bodies.
- Handoff PATH lookup only (`kwik-gate` / `hermes-gate` absent → `install kwik candidate`).

## Artifacts

- JSON captures: `/workspace/kwik-adaptive-prd/v2-dryruns/{kwik-e-gate,lintlang,intent-verify}.json`
- TOML extracts: same dir `*.toml`
