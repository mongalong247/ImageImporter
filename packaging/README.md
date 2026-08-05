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

The Windows ExifTool zip is **vendored directly in the repo**, at
`vendor/exiftool-<VERSION>_64.zip` — it is committed, not gitignored. The
release workflow's Windows job just unzips it locally into `resources/`
before running PyInstaller; it does not fetch anything over the network.

This is deliberate, not a shortcut: SourceForge (where ExifTool's Windows
build is hosted) returns a flat `403 Forbidden` to GitHub Actions' runner
IP ranges as anti-abuse policy against cloud/datacenter IPs. This was
confirmed directly — the workflow hit it with both `Invoke-WebRequest` and
`curl.exe`, with retries, different user agents, etc. None of that reliably
works around a deliberate IP-range block, so the network fetch was removed
from CI entirely.

`resources/exiftool.exe` and `resources/exiftool_files/` themselves stay
gitignored (see `.gitignore`) — they're the *unzipped, build-time-generated*
copy, not the source. Only the zip in `vendor/` is committed.

**To update the vendored ExifTool version** (e.g. when ExifTool ships a new
release and you bump `PINNED_BUNDLED_VERSION` in `exiftool_manager.py` to
match):

1. On a normal (non-cloud/CI) internet connection, download
   `exiftool-<version>_64.zip` from https://exiftool.org (links to
   SourceForge; a home/office connection isn't blocked, only CI/cloud IP
   ranges are).
2. Delete the old file in `vendor/` and add the new one, keeping the exact
   `exiftool-<version>_64.zip` naming.
3. Update `EXIFTOOL_VERSION` in `.github/workflows/release.yml` to match.
4. Update `PINNED_BUNDLED_VERSION` in `exiftool_manager.py` to match, if you
   haven't already.
5. Commit all three changes together.

**The version in `vendor/`, `EXIFTOOL_VERSION` in the workflow, and
`PINNED_BUNDLED_VERSION` in `exiftool_manager.py` must always agree** — the
app's own status text/UI reports the constant as "what's bundled", so a
mismatch means the app is lying about its own contents.

## Building locally (one platform at a time)

PyInstaller does not cross-compile — build on the OS you're targeting.

```bash
pip install -r requirements.txt -r requirements-build.txt

# Windows only, first: unzip vendor/exiftool-<version>_64.zip into resources/
# the same way the workflow does (exiftool(-k).exe -> resources/exiftool.exe,
# exiftool_files/ -> resources/exiftool_files/)

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
workflow converts it to `.icns` on the macOS runner via
`packaging/make_macos_icon.py` (Pillow for the image resizing, `iconutil`
for the final `.icns` build) before the PyInstaller build. An earlier
version of this step used macOS's `sips` directly, but `sips` has
inconsistent support for reading multi-resolution `.ico` files across
macOS versions and failed outright on this project's first real CI run
("Unable to write image ... Error 13") — Pillow (already a project
dependency) is more predictable.

The spec file just looks for `assets/app_icon.icns` — the generation step
in the workflow always (re)creates it, so if you want a purpose-made macOS
icon instead of an auto-converted one, remove the "Generate macOS app
icon" step from `.github/workflows/release.yml` and commit
`assets/app_icon.icns` directly instead (otherwise CI will overwrite it).

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
