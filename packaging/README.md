# Packaging & releasing ImageImporter

This folder holds everything needed to build distributable ImageImporter
archives for Windows, macOS, and Linux. Read this before touching the build.

## The short version

- Push a tag (`v1.4.0`) → GitHub Actions (`.github/workflows/release.yml`)
  builds all three platforms natively and attaches zipped/tarballed archives
  to a **draft** GitHub Release for you to review and publish.
- Or trigger the workflow manually from the Actions tab to test packaging
  changes without cutting a real release.
- Distribution format is a **portable archive** (zip / tar.gz), not an
  installer wizard — unzip it and run the exe/app inside. No admin rights,
  no install/uninstall flow to maintain.

## Why not a single-file .exe, and what "_internal" was about

Earlier attempts used `--onefile` or added `resources/` (the bundled
ExifTool binary) to PyInstaller via `--add-data`. Both are wrong for this
app, for different reasons:

- **`--onefile`** re-extracts the whole app to a fresh temp folder on
  every launch. That's actively broken here because `exiftool_manager.py`
  keeps a small pool of long-running, `-stay_open` ExifTool processes
  pointed at a specific on-disk path for the life of the app run — that
  path needs to be stable, not a temp folder.
- **Adding `resources/` via `datas=`** meant PyInstaller 6+ nested it
  inside its internal libs folder (`_internal/` on Windows/Linux onedir
  builds) instead of leaving it next to the actual `.exe`. But
  `paths.py` deliberately resolves persistent storage (the bundled
  ExifTool, saved lens presets) as `os.path.dirname(sys.executable) /
  "resources"` — the folder containing the *executable*, not
  PyInstaller's internal libs folder. The two disagreed, so the bundled
  ExifTool silently went missing at runtime. That's the "_internal folder
  breaks the resources folder" problem.

**The fix**: build in `onedir` mode (`packaging/ImageImporter.spec`), and
never hand `resources/` to PyInstaller at all. Instead,
`packaging/copy_resources.py` runs as an explicit step *after* the
PyInstaller build and copies `resources/` directly into the same folder as
the built executable. This works regardless of what PyInstaller's internal
layout looks like in any given version, because it isn't relying on
PyInstaller's data-file placement at all — it's just a plain file copy to
a path we compute ourselves.

`assets/` (just the window icon) is unaffected by any of this — it's
read-only, and `app.py`'s `resource_path()` helper already reads it via
`sys._MEIPASS`, which is exactly what that mechanism is for.

## Platform differences

| Platform | Bundled ExifTool? | Why |
|---|---|---|
| Windows | Yes — `resources/exiftool.exe` + `resources/exiftool_files/` | No universal system package manager; bundling avoids a manual install step for most users. |
| macOS | No | `exiftool_manager.py`'s fallback chain checks system PATH first, then bundled. Ships no `resources/exiftool*` at all — if ExifTool isn't found, the app still launches (metadata tagging just disables itself) and shows a Homebrew install hint. |
| Linux | No | Same fallback chain; shows distro-appropriate `apt`/`dnf`/`pacman` install hints. |

This matches how `exiftool_manager.py` already works today — no code
changes were needed to support mac/Linux builds without a bundled binary,
it already degrades gracefully (`ensure_exiftool_available()` never treats
a missing ExifTool as fatal).

## Sourcing ExifTool for Windows builds

`resources/exiftool.exe` and `resources/exiftool_files/` are gitignored —
they're never committed to the repo (see `.gitignore`). The release
workflow's Windows job downloads the official Windows build directly from
exiftool.org (mirrored via SourceForge) and drops it into `resources/`
before running PyInstaller:

```
https://sourceforge.net/projects/exiftool/files/exiftool-<VERSION>_64.zip/download
```

**The version fetched (`EXIFTOOL_VERSION` in the workflow) must match
`PINNED_BUNDLED_VERSION` in `exiftool_manager.py`** — the app's own status
text/UI reports that constant as "what's bundled", so the two need to stay
in sync. When you bump one, bump the other in the same commit.

To build a Windows package locally, you need to do this step yourself
first:

1. Download `exiftool-<version>_64.zip` from https://exiftool.org
2. Extract it
3. Copy `exiftool(-k).exe` → `resources/exiftool.exe`
4. Copy the `exiftool_files/` folder → `resources/exiftool_files/`

## Building locally (one platform at a time)

PyInstaller does not cross-compile — build on the OS you're targeting.

```bash
pip install -r requirements.txt -r requirements-build.txt

# Windows only, first: fetch resources/exiftool.exe + resources/exiftool_files/
# (see above)

pyinstaller packaging/ImageImporter.spec --noconfirm --clean
python packaging/copy_resources.py
```

Output:
- Windows/Linux: `dist/ImageImporter/` (onedir folder — `ImageImporter.exe`
  or `ImageImporter` plus `_internal/` plus `resources/`, all siblings)
- macOS: `dist/ImageImporter.app`

Zip/tar that folder up and it's the same portable archive the release
workflow produces.

## macOS app icon

`assets/app_icon.ico` is the only icon checked into the repo. The release
workflow converts it to `.icns` on the macOS runner using `sips` +
`iconutil` (both preinstalled on macOS, no extra dependency) before the
PyInstaller build. If you want a purpose-made macOS icon instead of an
auto-converted one later, drop `assets/app_icon.icns` into the repo and the
spec file will use it directly (it only auto-generates when the file is
absent... actually: the spec just looks for `assets/app_icon.icns` — the
generation step in the workflow always (re)creates it, so committing your
own would currently get overwritten by CI. If you'd rather hand-author the
`.icns`, remove the "Generate macOS app icon" step from
`.github/workflows/release.yml` and commit `assets/app_icon.icns` instead.)

## A note on where user data lands

`paths.py` stores everything persistent (bundled ExifTool, saved lens
presets, `QSettings`) next to the executable. On Windows/Linux that's the
top-level unzipped folder; on macOS it's inside the `.app` bundle
(`Contents/MacOS/resources/`), which is normal/expected for a self-contained
mac app. One implication worth knowing: if a user unzips the portable
archive into a location their OS locks down (e.g. `C:\Program Files` on
Windows without running as admin), saving a preset or first-run ExifTool
resolution could fail on write. This isn't new behavior introduced by
packaging — it's how `paths.py` already works — but it's worth telling
users in the README/release notes to unzip somewhere in their own user
space (Desktop, Documents, `~/Applications`, etc.) rather than a
system-protected folder. Out of scope for this packaging pass to change,
noted here in case it's worth a follow-up (e.g. switching to a proper
per-OS user-data directory via `platformdirs` for presets/settings while
still keeping the *bundled ExifTool* itself next to the exe).
