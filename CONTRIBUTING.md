# Contributing to Doc Unlocker

Thanks for your interest in improving Doc Unlocker. This is a friendly,
community-run project and contributions of all sizes are welcome - code, docs,
translations, bug reports, and ideas.

## Ground rules

- Be kind and respectful.
- Doc Unlocker is strictly a **password-recovery tool for files you own or are
  authorised to access**. Please do not file issues or PRs that facilitate
  unauthorised access to other people's data.

## Help especially wanted: macOS and Linux

The core logic is cross-platform Python, but these need work and real-device
testing:

1. **GUI polish** on macOS/Linux (Tkinter theming differs per platform).
2. **Hashcat integration**: the download/unpack step and `hashcat` discovery
   are currently Windows-oriented.
3. **Packaging**: a macOS `.app`, and Linux AppImage / `.deb`.

If you can help, please open an issue describing your plan first.

## Development setup

```bash
git clone https://github.com/Fallax-Vision/doc_unlocker.git
cd doc_unlocker
py -m pip install -r requirements.txt
py doc_unlocker.py
```

The desktop app is in **`doc_unlocker.py`**; the native Android app is in **`android/`**.

### Project layout

- `doc_unlocker.py` - the app (logic + GUI)
- `build_exe.py` - PyInstaller build script
- `assets/` - icon and `make_icon.py`
- `.github/workflows/` - CI that validates and publishes both platforms after a version bump

### Building the `.exe`

```bash
py -m pip install --user pyinstaller
py build_exe.py        # -> dist/DocUnlocker-v1.0.5.exe
```

## Pull request workflow

1. Fork the repo and create a branch: `git checkout -b feature/my-thing`.
2. Make your change. Keep the app a single self-contained file where practical.
3. Run `python -m pytest -q`, the JVM engine regressions, Android lint and a UI smoke test.
4. Update `CHANGELOG.md` under an *Unreleased* heading.
5. Commit with a clear message and open a PR against `main`.

## Versioning and releases

We use [Semantic Versioning](https://semver.org/). Update both platform versions and
`CHANGELOG.md`; follow [release setup](GITHUB_SETUP.md) for testing, signing and the
version-triggered workflow. Keep generated files, keys and user documents out of Git.

## Good first issues

- App screenshots for the README (light and dark).
- More / better wordlists.
- UI translations.
- A device picker for multi-GPU machines.

Happy hacking.
