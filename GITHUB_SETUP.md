# Publishing this repo to GitHub (Fallax-Vision)

The local repository is fully prepared: git is initialised, the first commit is
made, the `.exe` is built in `dist/`, and the tag **`v1.0.0`** is created.

Pick **one** of the three paths below: GitHub Desktop (easiest, you already
have it), the GitHub CLI, or the website. Releases are produced **automatically**
by the CI workflow when you push a version tag - so you usually never upload the
`.exe` by hand.

---

## Path 1 - GitHub Desktop (recommended for you)

GitHub Desktop manages the local-to-origin connection and pushing. The release
is then built and published **automatically by CI** when the `v1.0.0` tag
arrives.

### A. Publish the repo to the Fallax-Vision org

1. Open **GitHub Desktop**.
2. **File -> Add local repository...** and choose
   `C:\wamp64\www\fallax_projects\word_unlocker`
   (it is already a git repo, so it is added directly).
3. Click **Publish repository** (top bar):
   - **Organization / Owner:** select **Fallax-Vision**
   - **Name:** `word_unlocker`
   - **Uncheck** "Keep this code private" (so it is public / open-source)
   - **Publish repository** - this creates the org repo and pushes `main`.

### B. Push the version tag (this triggers the release build)

GitHub Desktop pushes your commits and the **`v1.0.0`** tag. If the tag does not
appear on GitHub, click **Push origin** again (Repository -> Push).
When the tag lands, the **Actions** workflow builds the `.exe` and publishes the
Release automatically - watch the repo's **Actions** tab. No manual upload.

### C. Day-to-day

- Edit files, review changes in GitHub Desktop, write a summary,
  **Commit to main**, then **Push origin**.
- New version: bump `__version__` in `word_unlocker.py`, add a `CHANGELOG.md`
  entry, **Commit**, then **History -> right-click the commit -> Create Tag...**,
  name it `vX.Y.Z`, then **Push origin**. CI publishes the new release with the
  fresh `.exe`.

> GitHub Desktop has no "create release" button - that is handled by CI
> (automatic), or manually on the website (Releases -> Draft a new release, where
> you can drag `dist/WordUnlocker.exe`).

---

## Path 2 - GitHub CLI (`gh`)

The GitHub CLI (`gh`) has been installed on this machine. Open a **new**
terminal (so `gh` is on PATH), `cd` into
`C:\wamp64\www\fallax_projects\word_unlocker`, then:

```powershell
# 1. Log in to GitHub (opens your browser once)
gh auth login

# 2. Create the repo UNDER the Fallax-Vision org and push code in one step
gh repo create Fallax-Vision/word_unlocker --public --source=. --remote=origin --push ^
   --description "Recover the password of your own Microsoft Office documents - GUI + GPU (Hashcat)."

# 3. Push the version tag
git push origin v1.0.0

# 4. (If the .exe isn't built yet)
py -m pip install --user pyinstaller
py build_exe.py

# 5. Create the v1.0.0 Release and attach the .exe
gh release create v1.0.0 "dist/WordUnlocker.exe" ^
   --repo Fallax-Vision/word_unlocker ^
   --title "Word Unlocker v1.0.0" ^
   --notes-file CHANGELOG.md
```

Done - your repo is live at
`https://github.com/Fallax-Vision/word_unlocker` with a downloadable
`WordUnlocker.exe` on the Releases page.

> You must be a member/owner of the **Fallax-Vision** organisation with rights
> to create repositories. If `gh auth login` does not list the org, ask an org
> owner to grant access (or accept the org's SSO when prompted).

---

## Path 3 - GitHub website (manual)

### 1. Create the empty repo

1. Go to **https://github.com/organizations/Fallax-Vision/repositories/new**
2. **Name:** `word_unlocker`  -  **Visibility:** Public
3. **Do NOT** add a README, .gitignore, or license (we already have them).
4. **Create repository.**

### 2. Push the local repo

```powershell
git remote add origin https://github.com/Fallax-Vision/word_unlocker.git
git push -u origin main
git push origin v1.0.0
```

### 3. Build the .exe (if needed)

```powershell
py -m pip install --user pyinstaller
py build_exe.py        # -> dist/WordUnlocker.exe
```

### 4. Create the Release and attach the .exe

1. Open **https://github.com/Fallax-Vision/word_unlocker/releases/new**
2. **Choose a tag:** `v1.0.0`
3. **Title:** `Word Unlocker v1.0.0`
4. **Description:** paste the `## [1.0.0]` section from `CHANGELOG.md`.
5. Drag **`dist/WordUnlocker.exe`** into the "Attach binaries" box.
6. **Publish release.**

---

## Future releases

```powershell
# bump __version__ in word_unlocker.py + add a CHANGELOG entry, then:
git add -A && git commit -m "Release vX.Y.Z"
git tag vX.Y.Z
git push && git push --tags
py build_exe.py
gh release create vX.Y.Z "dist/WordUnlocker.exe" --title "Word Unlocker vX.Y.Z" --notes-file CHANGELOG.md
```
