<div align="center">

<img src="assets/icon.png" width="96" alt="Doc Unlocker icon">

# Doc Unlocker

**Recover the password of a Microsoft Office or PDF document _you own_ - with a friendly GUI, smart guessing, and optional GPU acceleration.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.5-success.svg)](CHANGELOG.md)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Android-informational.svg)](#installation)
[![Python](https://img.shields.io/badge/python-3.10%2B-yellow.svg)](https://www.python.org/)

</div>

<img width="2449" height="1070" alt="GitHub Banner - Doc Unlocker" src="https://github.com/user-attachments/assets/da111e21-c9e1-4dce-af5b-5736f9cf3565" />


## Use it responsibly

Doc Unlocker is a **password-recovery** tool for documents **you own or are
explicitly authorised to access** - for example, a file whose password you
forgot. **Do not** use it on documents you have no right to open. You are
responsible for how you use this software. See the [MIT License](LICENSE).

---

## What it does

You point it at a password-protected document and it tries to find the
password so it can produce an **unlocked copy** (`Unlocked_<yourfile>`).

**Supported files:** Microsoft **Word** (`.docx`/`.docm`/`.doc`), **Excel**
(`.xlsx`/`.xlsm`/`.xls`), **PowerPoint** (`.pptx`/`.pptm`/`.ppt`), and **PDF**
(`.pdf`).

It works on two levels.

### A. Smart CPU guessing

- Built-in **common passwords** and **common words** (multilingual).
- Live **mutations**: capitalisation, numbers, years, symbols, and leetspeak
  (`amani` becomes `Amani2024`, `Am@ni!`, and so on).
- **Word + date** patterns (e.g. `Summer1990`, `Love2025!`).
- Optional **two-word combinations**.
- Optional **numeric-PIN sweep** (1-12 digits).
- Bring your **own wordlist** for a targeted attack.

### B. GPU acceleration (via [Hashcat](https://hashcat.net))

For modern Office encryption (AES-256 / SHA-512 / 100,000 iterations, Hashcat
mode `-m 9600`), the CPU is slow by design. Doc Unlocker can hand the work to
your GPU:

| Button | What it does |
|---|---|
| **Get Hashcat** | Downloads and unpacks Hashcat next to the app (one click). |
| **Test GPU** | Runs `hashcat -I` and tells you if your GPU is detected. |
| **Run Hashcat now** | Builds a smart wordlist + hash, runs the attack, and **auto-creates the unlocked copy** when it succeeds. |
| **GPU brute-force (all combos)** | A mask attack that tries *every* combination of a chosen character set / length - with a keyspace and time estimate first. |
| **Export for GPU** | Generates the wordlist, hash, and a ready-to-run `run_hashcat.bat`. |

> GPU acceleration currently targets **Office files only**. PDFs are handled by
> the CPU path (smart guessing / *Unlock with known password*); PDF GPU modes
> are planned for a future release.

### C. Quality-of-life

- Modern rounded interface with a **Light / Dark / System** theme.
- **Settings panel** (gear icon): theme, rounded/sharp corners, launch
  maximised, finish notifications + sound, and a "Check for updates" button.
- Live **tries counter**, **speed**, and **estimated time remaining**.
- **Resume**: the last 50,000 attempts are remembered as hashes per file and skipped next time.
- **Unlock with known password** if you already have it.

---

## Interface

A clean two-pane layout: your inputs and options on the left, GPU/utility
actions on the right, and a live progress/status bar along the bottom - in
both light and dark themes.

> Tip: drop screenshots into `assets/` and reference them here.

---

## Installation

### Option A - Download the ready-made build (easiest)

1. Go to the [Releases](../../releases) page.
2. Download the latest asset for your platform:
   - **Windows:** `DocUnlocker-vX.Y.Z.exe` (double-click; no Python needed).
   - **Android:** `DocUnlocker-vX.Y.Z.apk` (enable "install unknown apps", then
   open the APK). Android supports Office agile AES-256/SHA-512 files up to 16 MiB.
   Version 1.0.5 introduces stable release signing; older debug-signed installations
   may require uninstalling the old app first. Keep your downloaded documents.

### Option B - Run from source (Windows)

```bash
git clone https://github.com/Fallax-Vision/doc_unlocker.git
cd doc_unlocker
py -m pip install -r requirements.txt
py doc_unlocker.py
```

On first launch the app will offer to install its small dependencies
(`msoffcrypto-tool`, `olefile`, `pypdf`, `customtkinter`) automatically if they
are missing.

> Hashcat is optional. Click **Get Hashcat** inside the app to fetch it, or
> install it yourself from [hashcat.net](https://hashcat.net) and make sure
> `hashcat.exe` is on your `PATH`.

---

## Quick start

1. **Browse** to your locked document.
2. (Optional) pick a **wordlist** and tweak the **Options**.
3. Click **Start Unlocking** for the CPU attack, or
   **Get Hashcat** then **Test GPU** then **Run Hashcat now** for the fast GPU path.
4. When the password is found, an **`Unlocked_<yourfile>`** copy appears in the
   same folder. Existing copies are preserved with numbered names. The password is
   shown in the result; `DocUnlocker_found.log` contains only operational details.

---

## How it works (under the hood)

- For Office files: reads the document's `EncryptionInfo` and builds a
  Hashcat-compatible `$office$*2013*...` hash **natively** in Python (`olefile`).
- Verifies a candidate by decrypting the file and checking its document signature.
  This is a format sanity check, not a complete Office-content validation.
- Uses [`msoffcrypto-tool`](https://github.com/nolze/msoffcrypto-tool) for Office
  decryption, [`pypdf`](https://github.com/py-pdf/pypdf) for PDFs, and
  [Hashcat](https://hashcat.net) for GPU cracking of Office files.

---

## Building the `.exe` yourself

```bash
py -m pip install --user pyinstaller
py build_exe.py
# -> dist/DocUnlocker-v1.0.5.exe
```

The `.exe` is intentionally **git-ignored**; it is distributed as a
[Release](../../releases) asset, not committed to the repo.

---

## Contributing - help wanted

This is a community project and contributions are very welcome.

**We especially need help building macOS and Linux versions.**
The core logic is cross-platform Python, but the GUI styling, the Hashcat
download/unpack step, and packaging (`.app` / AppImage / `.deb`) need work and
testing on those platforms. If you can help:

1. Open an issue describing what you would like to tackle.
2. Fork the repo and create a feature branch.
3. Send a pull request.

Other good first issues: app screenshots, more wordlists, translations, and CI
improvements. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Roadmap

- [ ] macOS build (`.app`) and Linux build (AppImage / `.deb`)
- [ ] In-app screenshots
- [ ] Drag-and-drop a file onto the window
- [ ] Optional CUDA backend hint / device picker
- [x] Update check against the GitHub Releases API

## Limits, testing and storage

Desktop documents are limited to 64 MiB, Android documents to 16 MiB, and custom
wordlists/GPU exports to 32 MiB. Office key derivation is limited to 1,000,000
iterations per attempt. Long-running work stays off the interface thread.

Run `python -m pytest -q` for desktop regressions. Android engine checks are in
`android/_jvmtest/SecurityTests.java`; the release workflow generates a test fixture,
runs these checks, runs Android lint, and builds the signed APK.

Logs rotate at 1 MiB with at most two old logs. Legacy log passwords are removed
when those app-owned logs are next used; legacy resume attempts are hashed on the
next save. No database or server migrations exist in this project.

Preview cleanup with `python maintenance.py`; use `--apply` after copying verified
builds to `dist/`. It retains the current version plus two previous versions per
platform and removes reproducible build intermediates. User documents and unlocked
copies are excluded. `python github_retention.py` previews the equivalent release
binary and CI-run cleanup; the release workflow applies it after successful publication.
Git history is preserved, CI uses shallow checkouts, and temporary CI artifacts expire
after seven days. See [release setup](GITHUB_SETUP.md) for signing configuration.

---

## License

Released under the **[MIT License](LICENSE)** - completely free to use, modify,
redistribute, and even commercialise. Attribution appreciated but not required.

---

<div align="center">
Made by <strong>Fallax Vision</strong> and contributors.
</div>
