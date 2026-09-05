"""Bound project-owned build storage; preview by default, never touch documents."""
import argparse
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent
VERSION_FILE = re.compile(r"DocUnlocker-v(\d+)\.(\d+)\.(\d+)\.(exe|apk)$")


def cleanup_candidates(root=ROOT):
    root = Path(root).resolve()
    dist = root / "dist"
    # PyInstaller regenerates these; do not accumulate one per release.
    for path in root.glob("*.spec"):
        if re.fullmatch(r"(?:Doc|Word)Unlocker(?:-v\d+\.\d+\.\d+)?\.spec", path.name):
            yield path
    for suffix in ("exe", "apk"):
        versions = []
        for path in dist.glob(f"DocUnlocker-v*.{suffix}"):
            match = VERSION_FILE.fullmatch(path.name)
            if match and not path.is_symlink():
                versions.append((tuple(map(int, match.groups()[:3])), path))
        # Current version plus at most two previous versions, per platform.
        yield from (path for _, path in sorted(versions, reverse=True)[3:])
    # Reproducible intermediates only. SDKs and installed tools are reusable.
    for relative in ("build", "android/app/build", "android/.kotlin",
                     "android/_jvmtest/out", "__pycache__", ".pytest_cache"):
        path = root / relative
        if path.exists():
            yield path
    for relative, unpacked in (("tools/gradle-8.9-bin.zip", "tools/gradle-8.9"),
                              ("tools/upx.zip", "tools/upx-4.2.4-win64")):
        path = root / relative
        if path.is_file() and (root / unpacked).is_dir():
            yield path


def clean(root=ROOT, apply=False):
    root = Path(root).resolve()
    for path in cleanup_candidates(root):
        resolved = path.resolve()
        if path.is_symlink() or not resolved.is_relative_to(root) or resolved == root:
            raise ValueError(f"Refusing cleanup outside workspace: {path}")
        print(f"{'Remove' if apply else 'Would remove'}: {path}")
        if apply:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    clean(apply=parser.parse_args().apply)
