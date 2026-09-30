# Migration and release

## Current status

This checkout is an **unreleased 0.4.0 candidate**. Public PyPI/GitHub latest is
0.1.7 as verified 2026-09-29. The JS checkout is an **unreleased 0.4.0 candidate**;
public npm/GitHub latest is 0.3.2. Nothing has been published by this consolidation.
The product repository is now `hermes-labs-ai/kwik-e-gate`. Its new PyPI install name
`kwik-e-gate` is prepared in source but is not yet registered or published.

## Existing users

| Surface | Migration |
| --- | --- |
| New PyPI `kwik-e-gate`, CLI `kwik-e-gate` | Product install and command after 0.4.0 publication; the small install package depends on the same-version `hermes-gate` engine |
| PyPI `hermes-gate`, import `hermes_gate` | Preserved; upgrade the same distribution |
| `hermes-gate` and `kwik-gate` CLIs | Preserved as entry points to the same engine |
| `fast/full/review/boundary` status API | Preserved, with stronger evidence validation |
| `.hermes/gate.toml` | Preserved; no automatic rewrite/installation |
| Old receipts | Rerun checks; receipts without complete binding cannot be reused |
| Existing review-required profiles | Remain review-required when the new key is omitted |
| New profiles | `review_required=false`; optionally enable review/full policy explicitly |
| PyPI `pygate-ci`, `pygate` and its API | Preserved as optional Python diagnostics adapter; no PyGate runtime rewrite |
| npm `quick-gate`, `evaluateGates`, `runCommand` | Preserved as standalone JS surfaces and optional adapter |
| `gate-result/v1` | Canonical bytes unchanged; still an adapter result rather than boundary receipt |
| JS `quick/full/canary`, artifact paths and Action inputs | Preserved (`canary` remains the quick alias) |
| JS Action `node-version` default | Changes from 20 to 24; explicitly set a supported version to retain a project's runtime |
| New source-pinned core Action | Executes `run` with auto routing; select `mode: fast` or `mode: full` explicitly |
| Existing public Hermes Gate Action | Retains its separate `command` contract at the old repository; it is not the new mode-based Action |
| JS repair default | 0.4.0 makes it deterministic; `--model-assisted` or API `deterministicOnly:false` opts into Ollama |

Full now executes file-driven stages over all included inputs. A mutating check
that previously passed now returns ERROR through the legacy API and FAIL through
`run`. All-skipped JS evaluation is ERROR. JS shell permission now enters config
identity. Review failures/config changes cannot silently reuse previous evidence.
Unclassified CodeRabbit findings at a selected material severity now block acceptance
instead of being silently suppressed. Explicit recognized nonmaterial categories and
the typed JSONL contract keep their existing policy. Rerun receipts after upgrading:
the normalizer's bytes are part of the executing-core binding, even for checks that
never invoke review.
Forced `init` and `uninstall-repo` now park if an integration file or backup would
resolve outside the checkout or its Git metadata. Existing in-checkout symlinks to
regular files remain supported. If an old integration intentionally points outside,
move it inside or resolve it manually before retrying; the tool will not rewrite its
external target. Linked worktrees still keep install state in their Git directory.
Uninstall also parks when a recorded owner backup is missing or changed, or a backup
appears without a matching manifest entry. Restore those exact owner bytes or resolve
the integration manually before retrying; generated files remain in place on a park.
A truncated v1 manifest cannot remove only some generated files and then erase its
enrollment witness.

Do not run `init --force` merely to upgrade: it parks when a current or legacy install
manifest marks the repository as enrolled, preserving the original owner backup.
Uninstall first only while installed files still match; otherwise resolve owner edits
manually. A successful uninstall now removes its recorded backup copies. Leftover
backup copies from an older version or interrupted rollback are reused only when
the corresponding owner file has identical bytes; mismatches and orphaned backups
park until resolved. Existing profiles/CI remain valid; adopt new generated CI,
portable JS command detection and policy keys through a reviewed diff. Commit only intended integration updates. Rollback: retain the previous package
pin and profile/CI files; old receipts must still be regenerated, never relabeled.

`run` now defaults to explainable auto selection. Use `--mode fast` for the former
explicit fast behavior. `verify` selects the latest issued run receipt; use `--kind`
for a particular contract. `plan` is a read-only preview and reports PLANNED. Custom
routing globs only extend defaults; optional review advice cannot replace checks.

## Product name, repository URLs and existing users

Use **Kwik-e-gate** as the product title and `kwik-e-gate` as the repository slug,
PyPI install name, and primary CLI. The new
[`hermes-labs-ai/kwik-e-gate`](https://github.com/hermes-labs-ai/kwik-e-gate)
repository is the active source. The original
[`quick-gate-js`](https://github.com/hermes-labs-ai/quick-gate-js) and
[`hermes-gate`](https://github.com/hermes-labs-ai/hermes-gate) URLs remain in place
for their historical Actions, plugins, tags, releases, and users. No repository was
renamed and no stars were transferred.

The new `kwik-e-gate` PyPI distribution contains no second engine. It depends exactly
on the same-version `hermes-gate` distribution, which owns the `hermes_gate` import,
receipt engine, and all three CLI entry points. This direction preserves upgrades from
published `hermes-gate` 0.1.7 without two wheels writing the same module files.
Publish both distributions in lockstep. A `kwik-e-gate` release must never point to
an older engine version. npm `quick-gate` remains a standalone JS CLI/API and optional
diagnostics adapter; `pygate-ci` remains a separate optional Python adapter.

GitHub does not redirect hosted Action calls after a repository rename, so preserving
the original repository URLs protects existing Action pins. The new source-pinned core
Action lives at `.github/actions/kwik-e-gate/` in the product repository. See
[GitHub rename documentation](https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository).

## Local candidate verification

```bash
python -m pip install -e '.[test]'
ruff check .
pytest
python -m build
python scripts/verify_release.py --tag v0.4.0 --dist dist
```

Run the real JS roundtrip with `KWIK_QUICK_GATE_CLI=/path/to/quick-gate-js/src/cli.js`
and installed JS checkout dependencies. Set `KWIK_PYGATE_CLI` to installed
`pygate` for the real Python-adapter roundtrip (including Unicode/newline paths). For the JS candidate: `npm ci`, `npm run lint`,
`npm test`, `npm pack --dry-run`. Test the built wheel and tarball in fresh environments.
Adopted repositories also require their own Gate fast/review/full receipts at boundaries.

## Publication sequence

1. Review and merge the combined candidate using repository checks and exact receipts.
   Before creating a tag, verify the npm publisher and **both** PyPI trusted-publisher
   bindings against the new repository, `publish-core.yml`, and the protected `pypi`
   environment. The new `kwik-e-gate` project needs a pending publisher; its current
   404 response does not reserve the name. Tag creation is a publishing boundary.
2. Set the actual release date in citation metadata in the reviewed source, then create
   the new immutable `v0.4.0` tag at that accepted commit. **Pushing this tag immediately
   triggers `publish.yml` for npm**; a draft GitHub release does not prevent that trigger.
   Do not push it while intending only to prepare a PyPI release.
3. Observe npm's build/publish workflow and read back `quick-gate` **0.4.0** in the registry.
   Verify package/lock/plugin parity, runtime exports/bin paths, and a fresh install's
   passing/failing gate and deterministic-default repair. Preserve the historical tags.
4. Publish the GitHub `v0.4.0` release only after source and artifact acceptance.
   **The `release: published` event triggers `publish-core.yml` for PyPI.** It builds
   and verifies both distributions before upload, publishes `hermes-gate` first, then
   publishes `kwik-e-gate` only after the engine job succeeds. Each publication job
   rechecks its downloaded artifact and current PyPI version after environment approval.
5. Read back PyPI `hermes-gate` **0.4.0** and `kwik-e-gate` **0.4.0**, all publish jobs,
   and the GitHub release. In a fresh environment, install `kwik-e-gate==0.4.0`, run
   `kwik-e-gate run`, export and verify a receipt on a disposable repository. Repeat
   from an environment with published `hermes-gate==0.1.7` to prove its import and CLI
   survive upgrade. Test the source-pinned Action's `mode: full` outputs before
   recommending a release pin. The root Action retains its historical JS interface.
6. Update README/skill released-state wording only after each corresponding publication
   is observed. The combined adapter CI uses this checkout's JS source; historical Action
   references remain supported. A failed publication is a partial release to investigate,
   never a reason to move a tag or claim all packages succeeded. Keep historical releases
   accessible; do not delete, unpublish, or move tags to repair a partial release.
