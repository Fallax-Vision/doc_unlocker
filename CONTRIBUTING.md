# Contributing to Word Unlocker

Thanks for your interest in improving Word Unlocker. This is a friendly,
community-run project and contributions of all sizes are welcome - code, docs,
translations, bug reports, and ideas.

## Ground rules

- Be kind and respectful.
- Word Unlocker is strictly a **password-recovery tool for files you own or are
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
git clone https://github.com/Fallax-Vision/word_unlocker.git
cd word_unlocker
py -m pip install -r requirements.txt
py word_unlocker.py
```

The whole app lives in a single file: **`word_unlocker.py`**.

### Project layout

- `word_unlocker.py` - the app (logic + GUI)
- `build_exe.py` - PyInstaller build script
- `assets/` - icon and `make_icon.py`
- `.github/workflows/` - CI that builds and publishes the `.exe` on a version tag

### Building the `.exe`

```bash
py -m pip install --user pyinstaller
py build_exe.py        # -> dist/WordUnlocker.exe
```

## Pull request workflow

1. Fork the repo and create a branch: `git checkout -b feature/my-thing`.
2. Make your change. Keep the app a single self-contained file where practical.
3. Run a quick smoke test: launch the app, switch themes, try a small attack.
4. Update `CHANGELOG.md` under an *Unreleased* heading.
5. Commit with a clear message and open a PR against `main`.

## Versioning and releases

We use [Semantic Versioning](https://semver.org/). To cut a release:

1. Bump `__version__` in `word_unlocker.py` and add a `CHANGELOG.md` entry.
2. Tag it: `git tag vX.Y.Z && git push --tags`.
3. CI (`.github/workflows/release.yml`) builds the Windows `.exe` and attaches
   it to the GitHub Release automatically.

## Good first issues

- App screenshots for the README (light and dark).
- More / better wordlists.
- UI translations.
- A device picker for multi-GPU machines.

Happy hacking.
