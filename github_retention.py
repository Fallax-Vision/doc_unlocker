"""Preview bounded GitHub release assets and run-log cleanup for this repository."""
import argparse
import json
import re
import subprocess

REPO = "Fallax-Vision/doc_unlocker"


def api(path, method="GET"):
    result = subprocess.run(["gh", "api", "--method", method, f"repos/{REPO}/{path}"],
                            check=True, capture_output=True, text=True, timeout=60)
    return json.loads(result.stdout) if result.stdout.strip() else None


def pages(path, key=None):
    page = 1
    while True:
        data = api(f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}")
        rows = data[key] if key else data
        yield from rows
        if len(rows) < 100:
            return
        page += 1


def main(apply=False):
    releases = [r for r in pages("releases")
                if not r["draft"] and not r["prerelease"]
                and re.fullmatch(r"v\d+\.\d+\.\d+", r["tag_name"])]
    releases.sort(key=lambda r: tuple(map(int, r["tag_name"][1:].split("."))), reverse=True)
    # Keep the newest version plus two old versions. Only trim after both new binaries exist.
    if releases:
        latest = releases[0]
        expected = {f'DocUnlocker-{latest["tag_name"]}.{ext}' for ext in ("exe", "apk")}
        if not expected.issubset({a["name"] for a in latest["assets"]}):
            raise RuntimeError("Latest release is incomplete; refusing asset cleanup.")
    for release in releases[3:]:
        for asset in release["assets"]:
            if re.fullmatch(r"(?:Doc|Word)Unlocker(?:-v\d+\.\d+\.\d+)?\.(exe|apk)", asset["name"]):
                print(f'Old binary: {release["tag_name"]}/{asset["name"]} ({asset["size"]} bytes)')
                if apply:
                    api(f'releases/assets/{asset["id"]}', "DELETE")
    runs = [r for r in pages("actions/runs", "workflow_runs") if r["status"] == "completed"]
    runs.sort(key=lambda r: r["created_at"], reverse=True)
    keep = {r["id"] for r in runs[:5]}
    keep.update(r["id"] for r in [r for r in runs if r["conclusion"] == "failure"][:2])
    for run in runs:
        if run["id"] not in keep:
            print(f'Old completed CI run: {run["id"]} ({run["created_at"]})')
            if apply:
                api(f'actions/runs/{run["id"]}', "DELETE")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    main(parser.parse_args().apply)
