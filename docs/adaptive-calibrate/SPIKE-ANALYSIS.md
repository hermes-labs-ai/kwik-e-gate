# Spike analysis — adaptive Kwik calibrate (2026-10-01)

**Inputs:** `PRD-adaptive-kwik-2026-10-01.md`, `calibrate.py`, `test_calibrate.py`, `TEST-LOG.md`  
**Product survivor:** `hermes-labs-ai/kwik-e-gate`  
**Spike location:** `/workspace/kwik-adaptive-prd/` (outside the package)

## What works (v1)

- **Cheap prior scan** at repo root only: Python markers (`pyproject.toml`, `setup.py`, `requirements*.txt`), JS lockfiles (`package-lock.json` → npm, `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn), presence of `.hermes/gate.toml`.
- **Tool PATH probes:** `ruff` / `pytest` via `shutil.which`; LintLang via `lintlang --version` then `python -m lintlang --version` (cwd `/tmp`, timeout, no network, no file content reads).
- **Propose-then-print:** default `--dry-run` emits JSON with priors + `proposed_toml`; never writes unless `--write`.
- **Overwrite safety:** `--write` creates `.hermes/gate.toml` only when missing; refuses with exit 2 without `--force`; atomic write via temp + `os.replace`.
- **Python checks:** when Python priors exist, emits `[[fast]]`/`[[full]]` ruff and `[[full]]` pytest argv matching patterns used in live kwik profiles, with `# requires:` comments.
- **Handoff hint:** PATH lookup for `kwik-gate` / `hermes-gate`.
- **Tests:** 8 pytest cases cover markers, dry-run non-write, write create, refuse, force.
- **Live dry-run on `/workspace/kwik-e-gate`:** exit 0, gate.toml unchanged, proposal loadable by `hermes_gate.config.load_config`.

## Gaps

| Gap | Detail |
| --- | --- |
| **LintLang stub** | Availability probe only. No `lintlang scan`, no instruction-surface priors, no `[lintlang]` table in proposed toml. Engine default `enabled = false` stays. |
| **Not in package** | Spike lives under `/workspace/kwik-adaptive-prd/`, not under `kwik-e-gate` docs or `hermes_gate`. Not reviewable as a PR on the survivor product. |
| **No intent-verify** | Does not detect `INTENT.md` / `SPEC.md` / `AGENTS.md` / `skills/`. Does not propose optional intent-verify argv checks. |
| **No merge with `kwik-gate init`** | `init_repo.py` already emits a richer profile (`[adapter]`, `[lintlang]`, `[review]`, exclusions, JS scripts). Calibrate invents a thinner parallel profile and does not call, diff, or extend init. |
| **Schema incompleteness** | v1 omits `[adapter]`, `[lintlang]`, `[review]`, `exclusions`, `adapter_status`. Loader tolerates missing tables (defaults), but the proposal does not match the shape operators see from init / shipping profiles. |
| **JS checks not proposed** | Lockfiles are recorded; no eslint/npm-test argv (init does that from `package.json` scripts — calibrate deliberately does not read contents). |
| **Tools proposed when absent** | Ruff/pytest checks always proposed for Python priors even when `on_path` is false (by design: detect-then-propose with `# requires:`). |
| **Root-only markers** | No recursive walk; no content reads; no merge into an existing gate.toml (propose-replace only with `--force`). |

## v2 requirements (tonight)

1. **Keep** prior detect: Python/JS locks, `gate.toml` presence, tool PATH (ruff, pytest, lintlang, intent-verify).
2. **Add instruction-surface priors:** detect root `INTENT.md`, `SPEC.md`, `AGENTS.md`, and `skills/` directory → when present, propose:
   - `[lintlang]` table (schema-aligned with init / live profiles), with comments that `lintlang` must be installed; `enabled` true only when binary on PATH (else false + comment).
   - Optional named `[[full]]` check for **intent-verify** when `INTENT.md` or `SPEC.md` exists (`intent-verify check --spec <file>`), commented `# requires: intent-verify`.
3. **Emit JSON + proposed toml** matching kwik `.hermes/gate.toml` schema closely enough to load via `hermes_gate.config.load_config` (include `[gate]` exclusions/adapter_status, `[adapter]`, `[lintlang]`, `[review]` stubs, plus `[[fast]]`/`[[full]]`).
4. **CLI:** `--dry-run` default; `--write` refuse overwrite without `--force`.
5. **Fixtures + pytest** under `v2/fixtures/` for tiny fake repos.
6. **Publishable slice:** land under `docs/adaptive-calibrate/` on branch `feat/adaptive-calibrate-v2` (experimental; do not fold into `hermes_gate` package tonight). Draft PR, do not merge.
7. **Still stubbed:** no LintLang scan wiring into calibrate logic; no merge/diff with `init_repo`; no JS script inference from `package.json` contents; no replacing `kwik-gate init`.

## Decision: experimental docs path

Integrating into `src/hermes_gate/` would touch CLI, packaging, and init semantics — too large for tonight. Prefer `docs/adaptive-calibrate/` with a runnable script + README so Hermes repos can dry-run v2 without changing the shipping engine.
