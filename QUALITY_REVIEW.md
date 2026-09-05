# Version 1.0.6 quality review

## Overall UX score

8/10 (heuristic review, not a user-study measurement). Desktop visual checks and
Android source/layout review used the UX psychology checklist.

## Main UX problems and fixes

| Problem | Psychology-based change |
| --- | --- |
| Several actions competed with Start | One primary blue action; secondary GPU controls are quieter |
| Tiny password popup and dense settings | Larger themed password dialog, scrollable settings, fixed Done action |
| Small Android setting targets | Full-row radio/switch targets, minimum 48dp touch size, aligned labels |
| Long status messages crowded metrics | Full-width desktop status above aligned counters |
| Dark status text was difficult to read | Existing readable accent colours provide over 8:1 dark text contrast |
| Slow work froze actions or left stale state | Background work, input snapshots, single-job guard, explicit failure/finally paths |

## Priority changes and implementation

- Desktop library parsing/key derivation runs in a cancellable process, supervised
  by a background thread; widgets are updated through the main-thread queue.
- Android uses background import/save, bounded reads and a prepared Office container
  reused during recovery. Key derivation checks cancellation every 1,024 iterations.
- Known passwords are masked; operational logs omit secrets; GPU transient password
  files are removed. Existing unlocked copies are never overwritten.
- Settings persist atomically in the background; pending saves finish before closing.
- Resume history reads at most 4 MiB, retains 50,000 hashed attempts and migrates old
  plaintext attempts when saved. Logs retain at most two rotated 1 MiB files.

## Standard security scan

One standard scan (no deep scan) identified five medium-severity findings:
unbounded compound-file chains, unbounded crypto metadata/iterations, unbounded
Android imports, debug APK publication and plaintext password logging. The patch
adds bounds/cancellation, secret-free logging and signed non-debuggable releases.
An independent fix review also caught a legacy Office API compatibility issue,
pending-settings-save race and leftover GPU password files; these were corrected.

The scan covers tracked text source/configuration; bundled dependencies and image
binaries were not reverse engineered. TAC access could not be verified because
the access connector was disconnected. The workbench records 4,749,297 aggregate
tokens, including 4,489,856 cached input tokens, across four task contexts; this
measurement includes the owning task context rather than isolated audit effort.

## Verification

- `python -m pytest -q`: 12 passing tests, including real encrypted PDF recovery,
  preservation of existing output, background execution, termination of a stalled
  worker, legacy Office API compatibility, history migration and retention.
- JVM `SecurityTests`: correct/wrong Office password, invalid crypto sizes,
  invalid/cyclic OLE chains, KDF cancellation and bounded input stream tests pass.
- `gradlew lintRelease testReleaseUnitTest assembleRelease`: successful. Lint has
  zero errors and nine advisory warnings. Gradle unit-test task has no additional
  test sources; the executable JVM suite above supplies engine regression coverage.
- APK signature and manifest checked: version 1.0.6 / code 10006, stable RSA release
  certificate, no debuggable flag. Private key and passwords remain outside Git.
- Windows executable built with PyInstaller; packaged GUI startup and PDF recovery
  passed after correcting frozen worker initialization. The decrypted PDF was read
  independently to verify that it is unencrypted.
- Android emulator smoke test could not complete because the existing emulator
  became unresponsive. Real-device Android layout and hardware GPU execution remain
  unverified. No production server or database exists, so no SQL migrations apply.

## Final QA checklist

- [x] Fewer competing choices and one clear main action
- [x] Larger, aligned targets and familiar control behavior
- [x] Strong grouping and chunked, scrollable settings
- [x] Light/dark theme styling and keyboard dialog actions
- [x] Background execution, bounded state and regression checks
- [ ] Android device visual/accessibility check (emulator unavailable)

Release storage keeps the current and two previous binaries per platform. CI artifacts
expire in seven days; five completed runs plus two recent failures remain available.
Shared Git history is preserved because it was only about 159 KiB; CI checkouts are
shallow. Agent instructions and plans remain local-only.
Local cleanup reclaimed approximately 348 MiB of reproducible build intermediates
and duplicate downloaded archives while preserving all three platform versions.
