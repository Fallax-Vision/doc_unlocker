# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.1] - 2026-06-02

### Added

- **PDF support.** Doc Unlocker can now recover the open password of
  encrypted PDF files and save an unlocked copy (powered by `pypdf`):
  - works with the CPU smart-guessing attack and with
    *Unlock with known password*,
  - permission/owner-only protected PDFs are unlocked automatically,
  - the file picker now lists `.pdf` files.

### Notes

- GPU acceleration (Hashcat) still targets Office files only; selecting a PDF
  for a GPU action shows a clear message to use the CPU path instead. PDF GPU
  modes are planned for a future release.

## [1.0.0] - 2026-06-02

First public release.

### Added

- Graphical desktop app (Tkinter) to recover the password of your own
  Microsoft Office documents (`.docx`, `.xlsx`, `.pptx`).
- Light / Dark / System theme switcher.
- Smart CPU dictionary attack with:
  - common-password and common-word lists (multilingual),
  - on-the-fly mutations (capitalisation, numbers, years, symbols, leet),
  - word + date patterns (1960-2026),
  - optional two-word combinations,
  - optional numeric-PIN sweep.
- GPU acceleration via Hashcat (`-m 9600`, MS Office 2013+):
  - one-click *Get Hashcat* download and unpack,
  - *Test GPU* (`hashcat -I`) device check,
  - *Run Hashcat now* dictionary attack with live progress and auto-unlock,
  - *GPU brute-force* mask attack (every combination) with a keyspace/time
    estimate before you start,
  - *Export for GPU* to generate a wordlist, hash and ready-to-run `.bat`.
- Native `$office$` hash extraction (no buggy external scripts).
- *Unlock with known password* helper.
- Resume support: tried passwords are saved per file and skipped next time.
- Live speed and estimated-time-remaining readout.
- Application icon (window and executable).
- One-command `.exe` build (`build_exe.py`) with module exclusion and UPX.
- GitHub Actions workflow that builds and publishes the `.exe` on every
  version tag.
- `CONTRIBUTING.md` and contributor guidance.

### Notes

- Windows-only for now. Help wanted for macOS and Linux builds.
