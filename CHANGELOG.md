# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.3] - 2026-06-02

### Added

- **Android app (APK).** A barebone Android build with a matching look
  (rounded Material 3 cards, blue/purple accents, light/dark following the
  system, the same key icon, no splash screen, laid out vertically for
  phones). It recovers passwords for **Office 2013+** files
  (`.docx`/`.xlsx`/`.pptx`) via a pure-Java agile-encryption engine
  (AES + SHA-512), with a known-password field, a built-in wordlist, and a
  numeric-PIN sweep; the unlocked copy is saved to Downloads. PDF and the GPU
  path remain desktop-only for now.
- Release assets now include `DocUnlocker-vX.Y.Z.apk` alongside the `.exe`,
  built automatically by CI.
- **"Not encrypted" pre-check** (desktop and Android): before a run, the app
  checks the file is a supported type and actually encrypted. If not, it shows
  a concise warning suggesting apps to open the file in first, with **OK, Cancel**
  and **Continue** buttons.
- Expanded Android **Settings**: theme (System/Light/Dark), keep screen on
  while scanning, vibrate when a run finishes, and an About section. Settings
  persist between launches.

### Changed

- All release artefacts carry the version in their filename
  (`DocUnlocker-vX.Y.Z.exe` / `.apk`).

## [1.0.2] - 2026-06-02

### Changed

- **Redesigned interface** (built on CustomTkinter): rounded cards and
  buttons, a cleaner two-pane layout, and a header that matches the body
  background in dark mode.
- The window now opens **centred** on the screen.

### Added

- **Settings panel** (gear button in the header): theme (Light / Dark /
  System), UI corners (Rounded / Sharp), launch maximised, notify when a run
  is done, play a sound when done, confirm-before-closing during a run,
  auto-download Hashcat, a "Check for updates" button, and an About section
  (license, author, version).
- **Explicit Excel and PowerPoint support.** Encrypted `.xlsx`/`.xlsm` and
  `.pptx`/`.pptm` files are now first-class: dedicated entries in the file
  picker and documented support. They use the same proven Office engine as
  Word (CPU smart-guessing, GPU hash extraction, and *Unlock with known
  password*), verified end-to-end on a real encrypted workbook.

### Fixed

- The portable `.exe` now shows the app's key icon in the Windows taskbar
  (explicit AppUserModelID + `iconbitmap(default=...)`), instead of the
  generic Tk icon.

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
