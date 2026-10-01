# PRD — Adaptive Kwik (one gate, prior-calibrated)

**Date:** 2026-10-01  
**Owner:** Hermes Labs (Rolando Bosch)  
**Status:** spike / testable thin slice  
**Product name:** Kwik-e-gate (front door). Engine package may remain `hermes-gate`.

## Problem
Hermes shipped an aisle of gates (Hermes Gate, Quick Gate JS, PyGate / quick-gate-python, overlapping CLIs). Users must know which tool to bash. LintLang already reads repo priors; Kwik does not yet use that to calibrate itself. Unacceptable at ~500★ scale.

## Goal (2028 one-liner)
One free final code gate: pull up → it reads priors → calibrates a profile → runs checks + fail-closed receipt (+ optional material review). No second front door for “bash Python tools.”

## Non-goals (this spike)
- Full PyPI 0.4.0 cutover / Marketplace migration  
- Rewriting PyGate into Kwik  
- Replacing Hermeneutic Gate as a language product  
- LinkedIn / public marketing send  

## User
Operator or coding agent on a Python (or mixed) repo who wants one command/Action, not a product aisle.

## Thin-slice MVP (cook + test now)
1. **Prior scan:** given a repo path, collect cheap priors (language markers: `pyproject.toml` / `package-lock.json` / `pnpm-lock.yaml`; presence of `.hermes/gate.toml`; optional LintLang if installed).  
2. **Calibrate proposal:** emit a proposed `.hermes/gate.toml` fragment (or full file if missing) that includes Python checks when Python priors exist (ruff/pytest commands as named checks — PyGate behavior as *checks*, not a second CLI).  
3. **Dry-run / apply:** `--dry-run` prints proposal; `--write` writes only when no conflicting gate.toml (or `--force`).  
4. **Handoff:** print next command: `kwik-gate plan` / `hermes-gate fast` if available, else “install kwik candidate.”

Success for tonight’s test = run on `/workspace/kwik-e-gate` and one fixture repo; show priors detected + proposed profile; no crash; no silent overwrite.

## Later (path, not tonight)
- Wire LintLang scan output into calibrate (instruction-surface priors).  
- Default Action = Python core Action; JS Quick Gate legacy.  
- Publish `kwik-e-gate` meta → `hermes-gate==0.4.0`; deprecate other front doors.  
- Merge hermes `--fresh` review into kwik tip.  
- Material review as optional fail-closed stage.

## Evidence / acceptance
- Repo file: this PRD  
- Spike CLI or script under `/workspace/kwik-adaptive-prd/`  
- Test log: priors + proposal for live kwik-e-gate checkout  
- Explicit gaps: what was stubbed vs real LintLang

## Risks
- Dual front doors remain until publish cutover  
- Overwriting `.hermes/gate.toml` without force  
- Calibrate inventing checks the repo doesn’t have tools for — prefer detect-then-propose with “requires: ruff” notes
