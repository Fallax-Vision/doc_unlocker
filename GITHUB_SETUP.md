# GitHub: renaming the repo and automatic releases

This repository was first pushed to GitHub as **`Fallax-Vision/word_unlocker`**.
The project has been renamed to **Doc Unlocker** (`doc_unlocker`). This guide
shows how to (1) rename the existing GitHub repo in place - no new repository -
and (2) get a Release published automatically on every version bump.

---

## Why the first release did not appear

The previous workflow only ran on a **pushed tag** (`v*`). GitHub Desktop pushed
your branch but **not the tag**, so the workflow never triggered (0 runs).

This has been fixed: the workflow now also runs on **every push to `main`**,
reads `__version__` from `doc_unlocker.py`, and **publishes a Release only if one
does not already exist for that version**. So simply pushing a commit that bumps
the version creates the release automatically - no manual tag required.

---

## Part 1 - Rename the GitHub repo (in place, no new repo)

1. Go to **https://github.com/Fallax-Vision/word_unlocker/settings**
2. Under **General -> Repository name**, change `word_unlocker` to
   **`doc_unlocker`** and click **Rename**.
   - GitHub keeps all history, stars, issues, and **redirects the old URL**, so
     nothing breaks. This is a rename, not a new repository.
3. While in **Settings**, open **Actions -> General**, set **Workflow
   permissions** to **Read and write permissions**, and **Save**. This lets the
   workflow create Releases (without it the release step fails with a 403).

> Do Part 1 **before** pushing: the local remote now points at the new
> `doc_unlocker` URL, which only resolves after the rename.

---

## Part 2 - Point your local copy at the new name

The local folder has been renamed to
`C:\wamp64\www\fallax_projects\doc_unlocker`.

### In GitHub Desktop
1. If Desktop shows the old repo as "missing", click **Remove** it from the list.
2. **File -> Add local repository...** and choose
   `C:\wamp64\www\fallax_projects\doc_unlocker`.
3. Desktop will detect the existing remote. (If it still points at the old URL,
   that's fine - GitHub redirects - but you can update it to be tidy: see below.)

### Update the remote URL (optional but tidy)
In a terminal in the repo folder:
```powershell
git remote set-url origin https://github.com/Fallax-Vision/doc_unlocker.git
```

---

## Part 3 - Push and get the automatic release

1. In **GitHub Desktop**, you should see a new commit
   ("Rename to Doc Unlocker ..."). Click **Push origin**.
2. Open **https://github.com/Fallax-Vision/doc_unlocker/actions** - the
   **Build and Release** workflow will start automatically.
3. When it finishes (a few minutes), a **Release `v1.0.0`** appears with
   **`DocUnlocker.exe`** attached, under
   **https://github.com/Fallax-Vision/doc_unlocker/releases**.

That's it - no manual tagging or uploading.

---

## How future releases work (automatic)

Whenever you want to ship a new version:

1. Edit `doc_unlocker.py` and bump `__version__` (e.g. `1.0.0` -> `1.1.0`).
2. Add a matching section to `CHANGELOG.md`.
3. Commit and **Push origin** (GitHub Desktop or `git push`).

The workflow sees the new version, builds the `.exe`, creates the tag
`v1.1.0`, and publishes the Release with the binary attached. If the version is
unchanged, ordinary pushes do **not** create duplicate releases.

> You can also trigger a build manually from the **Actions** tab
> ("Build and Release" -> **Run workflow**).

---

## Manual fallback (if you ever need it)

Build locally and attach the binary by hand:
```powershell
py -m pip install --user pyinstaller
py build_exe.py                      # -> dist/DocUnlocker.exe
```
Then on **Releases -> Draft a new release**, pick the tag, and drag in
`dist/DocUnlocker.exe`.

Requirements: you must be a member/owner of the **Fallax-Vision** organisation
with permission to manage its repositories.
