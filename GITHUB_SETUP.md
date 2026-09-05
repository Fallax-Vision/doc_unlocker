# Build and release setup

The repository is `Fallax-Vision/doc_unlocker`. There is no production server or database.
Distribution uses GitHub Releases with a Windows executable and signed Android APK.

## Release steps

1. Keep `doc_unlocker.py` version and Android `versionName`/`versionCode` aligned.
2. Update `CHANGELOG.md`, run `python -m pytest -q`, JVM engine tests and Android lint.
3. Build locally with `python build_exe.py` and `android/gradlew assembleRelease`.
4. Commit and push to origin when authorized. The workflow tests both platforms,
   builds a new version and publishes both assets together with `SHA256SUMS.txt`.
   An unchanged version runs checks without creating a duplicate release.

## Android signing

Release builds require `DOC_UNLOCKER_KEYSTORE`, `DOC_UNLOCKER_STORE_PASSWORD` and
`DOC_UNLOCKER_KEY_PASSWORD` environment variables. The key alias is `docunlocker`.
A stable release key is held outside this repository; never commit signing material.

GitHub Actions uses repository secrets `ANDROID_KEYSTORE_BASE64`,
`ANDROID_STORE_PASSWORD` and `ANDROID_KEY_PASSWORD`. These are decoded only into
an ephemeral runner file, which is removed even if a build fails. Missing signing
credentials fail the release build instead of publishing a debug APK.

Version 1.0.5 starts stable release signing. Earlier APKs were signed with temporary
CI debug keys and may require uninstalling the old application before installation.
Downloaded documents are outside the app on Android 10+, but preserve them first.

## Retention

`python maintenance.py` previews local cleanup; `--apply` removes only listed,
project-owned intermediates and binaries older than the newest three per platform.
`python github_retention.py` previews GitHub cleanup; `--apply` removes old release
binaries, keeping the newest three versions, and keeps five recent completed CI runs
plus two recent failures. Running jobs, tags and release notes are preserved.
The latest release must contain both platform binaries before old binaries are removed.
Temporary CI artifacts expire after seven days. Shared Git history is not rewritten.
