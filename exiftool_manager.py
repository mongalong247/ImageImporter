import os
import platform
import shutil
import subprocess
import json
import base64
import threading
import queue
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QSettings

import paths

# --- PATHS & CONFIGURATION ---

RESOURCES_DIR = paths.RESOURCES_DIR
EXIFTOOL_EXE_NAME = "exiftool.exe" if platform.system() == "Windows" else "exiftool"
BUNDLED_EXIFTOOL_PATH = os.path.join(RESOURCES_DIR, EXIFTOOL_EXE_NAME)

# Kept for backwards compatibility with any code that still references the
# old constant name directly (e.g. error messages).
EXIFTOOL_PATH = BUNDLED_EXIFTOOL_PATH

# The version of ExifTool bundled in resources/ for this release. This is
# informational only (shown in status messages) -- there is no runtime
# download or update check. To ship a newer version: download the official
# release zip from https://exiftool.org (mirrored via SourceForge), extract
# it, and replace resources/exiftool.exe + resources/exiftool_files/ in the
# project, then bump this constant to match.
PINNED_BUNDLED_VERSION = "13.59"

SETTINGS_ORG = "PhotoTagger"
SETTINGS_APP = "ImageImporter"
CUSTOM_PATH_KEY = "exiftoolCustomPath"

# --- Platform-specific configuration for subprocess to hide console window ---
SUBPROCESS_ARGS = {}
if platform.system() == "Windows":
    SUBPROCESS_ARGS['creationflags'] = subprocess.CREATE_NO_WINDOW

SUBPROCESS_TIMEOUT = 15  # seconds, for one-off calls to the exiftool binary
STAY_OPEN_TIMEOUT = 30   # seconds, for a single command sent to a persistent session/pool

# How many persistent, already-running ExifTool processes to keep around
# for reads (shot-date lookups, RAW preview extraction) and metadata
# writes. On this app's bundled Windows build, every "cold" invocation of
# exiftool.exe re-loads the Perl interpreter plus every .pm module under
# resources/exiftool_files/ from scratch -- by far the biggest single cost
# per call, dwarfing the actual work done. A small pool of persistent
# ("-stay_open") processes pays that startup cost once (per process) at
# the start of a run instead of once per file (or, previously, up to
# several times per file -- see extract_preview_image_bytes), and lets a
# handful of files' extraction/lookup calls genuinely run concurrently
# instead of queueing behind a single process. Kept modest: each process
# costs some memory and its own one-time startup, and beyond a handful
# there's no more benefit once local disk/CPU is saturated anyway.
POOL_SIZE = max(1, min(4, (os.cpu_count() or 2)))

# --- State ---
_resolved_exiftool_path = None  # cached once a working path is found this session
_exiftool_checked = False       # guards against repeating the resolution flow

_pool = None
_pool_lock = threading.Lock()

# Preview/thumbnail tags to try, in descending order of expected size/
# quality -- see extract_preview_image_bytes() below for why each exists.
_PREVIEW_TAGS_PRIORITY = ("JpgFromRaw2", "JpgFromRaw", "PreviewImage", "OtherImage", "ThumbnailImage")


# --- SETTINGS: CUSTOM PATH ---

def get_custom_path() -> str:
    """Returns the user-configured custom ExifTool path, or '' if unset."""
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    return settings.value(CUSTOM_PATH_KEY, "", type=str)


def set_custom_path(path: str):
    """
    Saves a user-configured custom ExifTool path and forces re-resolution
    on the next call to resolve_exiftool_path() / ensure_exiftool_available().
    Pass an empty string to clear the override.
    """
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    settings.setValue(CUSTOM_PATH_KEY, path)
    global _exiftool_checked
    invalidate_resolved_path()
    _exiftool_checked = False
    # A path change means any already-running persistent processes are
    # pointed at the wrong (or no-longer-desired) executable -- shut them
    # down so the next call starts fresh ones against the new path.
    close_session()


def _get_install_hint() -> str:
    """Returns a platform-appropriate install instruction for ExifTool."""
    system = platform.system()
    if system == "Darwin":
        return "install it with Homebrew (brew install exiftool)"
    if system == "Linux":
        return (
            "install it with your distro's package manager "
            "(e.g. 'sudo apt install libimage-exiftool-perl' on Debian/Ubuntu, "
            "'sudo dnf install perl-Image-ExifTool' on Fedora, or "
            "'sudo pacman -S perl-image-exiftool' on Arch)"
        )
    return "install it from https://exiftool.org"


# --- PUBLIC: RESOLUTION ---

def _is_valid_exiftool(path: str) -> bool:
    """Checks that `path` points to a file that actually runs as ExifTool."""
    if not path or not os.path.isfile(path):
        return False
    try:
        subprocess.check_output(
            [path, "-ver"], text=True, timeout=SUBPROCESS_TIMEOUT, **SUBPROCESS_ARGS
        )
        return True
    except Exception:
        return False


def invalidate_resolved_path():
    """
    Forces the next resolve_exiftool_path() call to re-run the fallback
    chain from scratch instead of trusting the cached result. Used when a
    persistent ExifTool session fails to even launch (e.g. the resolved
    binary was deleted, or a removable drive holding it went away mid-run),
    so a bad cached path doesn't stay stuck for the rest of the app's
    lifetime.
    """
    global _resolved_exiftool_path
    _resolved_exiftool_path = None


def resolve_exiftool_path():
    """
    Resolves a working ExifTool executable using a fallback chain:
      1. User-configured custom path (Settings)
      2. A system-wide install found on PATH
      3. The bundled, pinned copy in resources/

    The result is cached for the rest of the app's run once found, and is
    NOT re-validated (i.e. no extra "-ver" subprocess spawn) on every call.
    This matters: previously, every single ExifTool operation in this app
    (a shot-date lookup, a preview extraction, a metadata write) silently
    paid for TWO process launches instead of one -- a "-ver" liveness
    check here, then the real command -- which for a large import batch
    doubled the total number of exiftool.exe launches for no benefit,
    since the resolved path essentially never changes mid-run. Call
    invalidate_resolved_path() to force re-resolution (set_custom_path()
    already does this automatically).

    Returns the resolved path (str), or None if nothing usable was found.
    """
    global _resolved_exiftool_path

    if _resolved_exiftool_path:
        return _resolved_exiftool_path

    custom = get_custom_path()
    if custom and _is_valid_exiftool(custom):
        _resolved_exiftool_path = custom
        return custom

    system_path = shutil.which("exiftool")
    if system_path and _is_valid_exiftool(system_path):
        _resolved_exiftool_path = system_path
        return system_path

    if _is_valid_exiftool(BUNDLED_EXIFTOOL_PATH):
        _resolved_exiftool_path = BUNDLED_EXIFTOOL_PATH
        return BUNDLED_EXIFTOOL_PATH

    _resolved_exiftool_path = None
    return None


def get_active_exiftool_path():
    """Returns the currently cached, resolved exiftool path (may be None)."""
    return _resolved_exiftool_path


def ensure_exiftool_available():
    """
    Checks whether a working ExifTool is available via the fallback chain
    (custom path / system PATH / bundled copy). There is no runtime
    download -- the bundled copy is pinned and shipped with the app (see
    PINNED_BUNDLED_VERSION above), which also removes the network
    dependency and the fragile "download and extract a .zip" logic that
    used to run on first launch.

    This function NEVER raises and never implies the app should quit -- it
    just reports what it found so the caller can degrade gracefully (e.g.
    disable metadata features) instead of treating a missing ExifTool as
    fatal.

    Returns (success: bool, message: str).
    """
    global _exiftool_checked

    path = resolve_exiftool_path()
    _exiftool_checked = True

    if path:
        return True, f"Using ExifTool at: {path}"

    return False, (
        "ExifTool was not found. The bundled copy may be missing from this "
        f"build's resources/ folder, you can {_get_install_hint()}, or you "
        "can set a custom path in Settings > Set ExifTool Path..."
    )


def check_or_install_exiftool() -> bool:
    """
    Deprecated alias kept for backwards compatibility. Prefer
    ensure_exiftool_available(), which also returns a status message and
    never implies the app must exit on failure.
    """
    success, _ = ensure_exiftool_available()
    return success


# --- PERSISTENT ("-stay_open") EXIFTOOL PROCESS SUPPORT ---

class _ExifToolSession:
    """
    Wraps one persistent ExifTool process started with '-stay_open True',
    so many commands can be sent to it, one after another, without paying
    process-launch (and, for this app's bundled Windows build, Perl
    interpreter + module reload) cost each time.

    Thread-safe: commands are serialized through an internal lock, so
    calling execute() from multiple threads is safe, but only one command
    is ever in flight on THIS particular process at a time -- see
    _ExifToolPool below for running several of these concurrently.
    """

    def __init__(self, exiftool_path: str):
        self._exiftool_path = exiftool_path
        self._proc = None
        self._out_queue = None
        self._lock = threading.Lock()

    def _is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _start(self):
        try:
            self._proc = subprocess.Popen(
                [self._exiftool_path, "-stay_open", "True", "-@", "-"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                **SUBPROCESS_ARGS
            )
        except Exception:
            # The resolved path itself is no good (deleted, unplugged
            # drive, etc.) -- don't keep handing out the same bad path.
            invalidate_resolved_path()
            self._proc = None
            raise

        self._out_queue = queue.Queue()
        threading.Thread(
            target=self._reader_loop, args=(self._proc.stdout, self._out_queue), daemon=True
        ).start()
        threading.Thread(
            target=self._drain_stderr, args=(self._proc.stderr,), daemon=True
        ).start()

    @staticmethod
    def _reader_loop(stream, out_queue):
        try:
            for line in iter(stream.readline, b""):
                out_queue.put(line)
        except Exception:
            pass
        finally:
            out_queue.put(None)  # signals EOF / process gone

    @staticmethod
    def _drain_stderr(stream):
        # Just keeps the stderr pipe from filling up and blocking ExifTool
        # -- per-command/per-file success is already determined from the
        # stdout text (see write_metadata / get_shot_date / etc.), so
        # stderr content here isn't otherwise consumed.
        try:
            for _line in iter(stream.readline, b""):
                pass
        except Exception:
            pass

    def _kill(self):
        try:
            if self._proc:
                self._proc.kill()
        except Exception:
            pass
        self._proc = None

    def close(self):
        """Cleanly shuts down the persistent process, if one is running."""
        with self._lock:
            if not self._is_alive():
                self._proc = None
                return
            try:
                # Per ExifTool's documented -stay_open protocol, the
                # shutdown command still needs an -execute terminator like
                # any other command -- just writing "-stay_open\nFalse\n"
                # without it leaves ExifTool waiting for more input forever.
                self._proc.stdin.write(b"-stay_open\nFalse\n-execute\n")
                self._proc.stdin.flush()
                self._proc.wait(timeout=SUBPROCESS_TIMEOUT)
            except Exception:
                self._kill()
            self._proc = None

    def _collect_until_ready(self, timeout):
        deadline = time.monotonic() + timeout
        lines = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Timed out waiting for ExifTool's response")
            try:
                line = self._out_queue.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError("Timed out waiting for ExifTool's response")
            if line is None:
                raise RuntimeError("ExifTool's -stay_open process ended unexpectedly")
            if line.rstrip(b"\r\n") == b"{ready}":
                return b"".join(lines)
            lines.append(line)

    def execute(self, args, timeout=STAY_OPEN_TIMEOUT):
        """
        Sends one command (a list of ExifTool arguments, e.g.
        ["-j", "-DateTimeOriginal", "file.jpg"]) to the persistent process
        and returns its raw stdout bytes for that command (with the
        trailing '{ready}' marker stripped). Retries once (killing and
        restarting the process) on any failure. Returns None if the
        command still couldn't be completed -- callers should treat that
        as "not available for this call" and fall back accordingly, the
        same as if ExifTool weren't installed at all.
        """
        with self._lock:
            last_error = None
            for _attempt in (1, 2):
                try:
                    if not self._is_alive():
                        self._start()
                    payload = "".join(f"{a}\n" for a in args) + "-execute\n"
                    self._proc.stdin.write(payload.encode("utf-8", errors="replace"))
                    self._proc.stdin.flush()
                    return self._collect_until_ready(timeout)
                except Exception as e:
                    last_error = e
                    self._kill()
            print(f"[ExifTool Session Error] {last_error}")
            return None


class _ExifToolPool:
    """
    A small round-robin pool of _ExifToolSession processes. A single
    persistent process removes launch overhead but still handles one
    command at a time; spreading calls across a few processes lets
    independent files' reads (shot-date lookups, RAW preview extraction)
    actually run concurrently -- the dominant cost in a RAW-heavy ArUco
    scan pass -- instead of queueing behind one process.
    """

    def __init__(self, size: int):
        self._size = max(1, size)
        self._path = None
        self._sessions = []
        self._lock = threading.Lock()
        self._next = 0

    def _ensure_sessions(self, path: str):
        with self._lock:
            if self._path != path or len(self._sessions) != self._size:
                for s in self._sessions:
                    s.close()
                self._path = path
                self._sessions = [_ExifToolSession(path) for _ in range(self._size)]

    def execute(self, args, timeout=STAY_OPEN_TIMEOUT):
        path = resolve_exiftool_path()
        if not path:
            return None
        self._ensure_sessions(path)
        with self._lock:
            session = self._sessions[self._next]
            self._next = (self._next + 1) % self._size
        return session.execute(args, timeout=timeout)

    def close(self):
        with self._lock:
            for s in self._sessions:
                s.close()
            self._sessions = []
            self._path = None


def _get_pool():
    """Returns the shared ExifTool process pool, lazily created, or None
    if no working ExifTool could be resolved at all."""
    global _pool
    if not resolve_exiftool_path():
        return None
    with _pool_lock:
        if _pool is None:
            _pool = _ExifToolPool(size=POOL_SIZE)
        return _pool


def close_session():
    """
    Cleanly shuts down any persistent ExifTool process(es) this app has
    running. Safe to call even if none are running. Call this on app exit
    so no orphaned exiftool process is left behind, and after changing the
    resolved ExifTool path so stale processes aren't reused.
    """
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None


# --- PUBLIC: METADATA OPERATIONS ---

def write_metadata(file_path: str, metadata: dict) -> bool:
    """
    Writes EXIF metadata to a single file, via the persistent ExifTool
    pool when available (falling back to a direct one-off process launch
    if the pool can't complete the call). Returns False (without raising)
    if no ExifTool is available, the file doesn't exist, or the write
    otherwise fails.
    """
    if not os.path.exists(file_path):
        print(f"[Error] File not found for metadata writing: {file_path}")
        return False

    tag_args = [f"-{tag}={value}" for tag, value in metadata.items() if value]
    if not tag_args:
        return True

    pool = _get_pool()
    if pool is not None:
        output = pool.execute(["-overwrite_original"] + tag_args + [file_path])
        if output is not None:
            text = output.decode("utf-8", errors="replace")
            if (
                "1 image files updated" in text
                or "1 image files created" in text
                or "1 image files unchanged" in text
            ):
                return True
            if text.strip():
                print(f"[ExifTool Error] {text.strip()}")
            return False
        # Pool/process failed even after its internal retry -- fall back
        # to a direct one-off invocation for just this file.

    return _write_metadata_subprocess_fallback(file_path, metadata)


def get_shot_date(file_path: str):
    """
    Extracts the 'shot date' from a single file's EXIF metadata. Returns
    None (without raising) if no ExifTool is available, the file doesn't
    exist, or the date can't be parsed. For importing many files at once,
    prefer get_shot_dates_batch() -- it resolves the whole batch in a
    handful of ExifTool commands instead of one per file.
    """
    if not os.path.exists(file_path):
        return None

    pool = _get_pool()
    if pool is not None:
        output = pool.execute(["-j", "-DateTimeOriginal", "-CreateDate", file_path])
        if output is not None:
            try:
                metadata = json.loads(output.decode("utf-8", errors="replace"))[0]
                date_str = metadata.get("DateTimeOriginal") or metadata.get("CreateDate")
                if date_str:
                    return datetime.strptime(date_str[:19], "%Y:%m:%d %H:%M:%S")
                return None
            except Exception as e:
                print(f"[Exif Error] Could not read shot date from {os.path.basename(file_path)}: {e}")
                return None
        # Pool/process failed even after its internal retry -- fall back.

    return _get_shot_date_subprocess_fallback(file_path)


def get_shot_dates_batch(file_paths, chunk_size: int = 200):
    """
    Batched version of get_shot_date(): resolves DateTimeOriginal /
    CreateDate for many files across a handful of ExifTool commands
    (chunked, and those chunks run concurrently across the process pool)
    instead of spawning one process per file. This is what app.py's import
    worker uses to build shot_dates for a whole batch up front, which
    previously meant one exiftool process launch per file just to sort
    the batch and name date-based subfolders.

    Returns {file_path: datetime | None}, with every input path present in
    the result even if its date couldn't be read (missing file, no
    ExifTool available, unparseable date, etc.).
    """
    results = {fp: None for fp in file_paths}
    existing_paths = [fp for fp in file_paths if os.path.exists(fp)]
    if not existing_paths:
        return results

    chunks = [existing_paths[i:i + chunk_size] for i in range(0, len(existing_paths), chunk_size)]

    def _process_chunk(chunk):
        pool = _get_pool()
        output = pool.execute(["-j", "-DateTimeOriginal", "-CreateDate"] + chunk) if pool else None
        if output is None:
            # Whole-chunk command unavailable -- fall back per-file for
            # just this chunk rather than losing dates for the whole batch.
            return {fp: get_shot_date(fp) for fp in chunk}
        try:
            parsed = json.loads(output.decode("utf-8", errors="replace"))
        except Exception as e:
            print(f"[Exif Error] Could not parse batched shot-date response: {e}")
            return {fp: get_shot_date(fp) for fp in chunk}
        if len(parsed) != len(chunk):
            # Shouldn't happen -- ExifTool returns one JSON entry per input
            # file, in order -- but if it ever does, fall back rather than
            # risk silently mismatching dates to the wrong files.
            return {fp: get_shot_date(fp) for fp in chunk}

        chunk_results = {}
        for fp, entry in zip(chunk, parsed):
            date_str = entry.get("DateTimeOriginal") or entry.get("CreateDate")
            if date_str:
                try:
                    chunk_results[fp] = datetime.strptime(date_str[:19], "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    chunk_results[fp] = None
            else:
                chunk_results[fp] = None
        return chunk_results

    if len(chunks) == 1:
        results.update(_process_chunk(chunks[0]))
        return results

    with ThreadPoolExecutor(max_workers=min(len(chunks), POOL_SIZE)) as executor:
        for chunk_result in executor.map(_process_chunk, chunks):
            results.update(chunk_result)
    return results


def extract_preview_image_bytes(file_path: str):
    """
    Extracts an embedded preview/thumbnail image from a file -- what a
    camera's own LCD uses for playback -- without doing a full RAW decode.
    Most RAW formats carry one, but different manufacturers embed their
    largest version under different tag names, so several are considered
    in descending order of expected size/quality:

      JpgFromRaw2 / JpgFromRaw  -- near full-resolution; common on
                                   Panasonic and some Olympus RAW files,
                                   which often don't populate PreviewImage
      PreviewImage              -- medium-to-large; common on Canon/
                                   Nikon/Sony
      OtherImage                -- uncommon, occasional fallback
      ThumbnailImage            -- small (often ~160x120) -- last resort,
                                   likely too low-resolution to scan a
                                   marker from

    All candidate tags are requested in a single ExifTool command (using
    -json -b, which base64-encodes binary tag values inline in the JSON
    response) rather than trying them one at a time in up to five separate
    commands/processes -- previously the single biggest source of
    redundant ExifTool invocations in the ArUco scan pass.

    Returns (image_bytes, tag_name) for the first tag that yields data
    (tag_name without the leading '-', e.g. "PreviewImage"), or
    (None, None) if nothing was found or ExifTool is unavailable.
    """
    if not os.path.exists(file_path):
        return None, None

    pool = _get_pool()
    if pool is not None:
        args = ["-j", "-b"] + [f"-{tag}" for tag in _PREVIEW_TAGS_PRIORITY] + [file_path]
        output = pool.execute(args)
        if output is not None:
            entry = None
            try:
                parsed = json.loads(output.decode("utf-8", errors="replace"))
                entry = parsed[0] if parsed else {}
            except Exception as e:
                print(f"[Exif Error] Could not parse combined preview response for {os.path.basename(file_path)}: {e}")

            if entry is not None:
                for tag in _PREVIEW_TAGS_PRIORITY:
                    raw = entry.get(tag)
                    if raw and isinstance(raw, str) and raw.startswith("base64:"):
                        try:
                            return base64.b64decode(raw[len("base64:"):]), tag
                        except Exception as e:
                            print(f"[Exif Error] Could not decode base64 {tag} from {os.path.basename(file_path)}: {e}")
                return None, None
        # Pool/process failed even after its internal retry -- fall back.

    return _extract_preview_subprocess_fallback(file_path)


# --- SUBPROCESS FALLBACKS (one-off process per call; no -stay_open) ---
#
# These are the original, pre-pool implementations, kept as the safety net
# used when the persistent process pool can't be started or stops
# responding (e.g. an unusual ExifTool build that doesn't support
# -stay_open). Behavior matches exactly what this app shipped with before
# -- slower, but never a regression in correctness.

def _get_shot_date_subprocess_fallback(file_path: str):
    exiftool_path = resolve_exiftool_path()
    if not exiftool_path or not os.path.exists(file_path):
        return None
    try:
        cmd = [exiftool_path, "-j", "-DateTimeOriginal", "-CreateDate", file_path]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            check=True, timeout=SUBPROCESS_TIMEOUT, **SUBPROCESS_ARGS
        )
        metadata = json.loads(result.stdout)[0]
        date_str = metadata.get("DateTimeOriginal") or metadata.get("CreateDate")
        if date_str:
            # Some cameras include a timezone offset or subseconds; only the
            # first 19 characters ("YYYY:MM:DD HH:MM:SS") are guaranteed to
            # match this format, so trim before parsing.
            return datetime.strptime(date_str[:19], "%Y:%m:%d %H:%M:%S")
    except Exception as e:
        print(f"[Exif Error] Could not read shot date from {os.path.basename(file_path)}: {e}")
    return None


def _write_metadata_subprocess_fallback(file_path: str, metadata: dict) -> bool:
    exiftool_path = resolve_exiftool_path()
    if not exiftool_path:
        print("[Error] ExifTool is not available; cannot write metadata.")
        return False

    if not os.path.exists(file_path):
        print(f"[Error] File not found for metadata writing: {file_path}")
        return False

    args = [exiftool_path, "-overwrite_original"]
    for tag, value in metadata.items():
        if value:
            args.append(f"-{tag}={value}")

    if len(args) <= 2:
        return True

    args.append(file_path)

    try:
        result = subprocess.run(
            args, capture_output=True, text=True, check=False,
            timeout=SUBPROCESS_TIMEOUT, **SUBPROCESS_ARGS
        )
        if result.returncode != 0:
            print(f"[ExifTool Error] {result.stderr.strip()}")
            return False
        return True
    except Exception as e:
        print(f"[Exception] Failed to write metadata: {e}")
        return False


def _extract_preview_subprocess_fallback(file_path: str):
    exiftool_path = resolve_exiftool_path()
    if not exiftool_path or not os.path.exists(file_path):
        return None, None

    for tag in ("-JpgFromRaw2", "-JpgFromRaw", "-PreviewImage", "-OtherImage", "-ThumbnailImage"):
        try:
            result = subprocess.run(
                [exiftool_path, "-b", tag, file_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=SUBPROCESS_TIMEOUT, **SUBPROCESS_ARGS
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout, tag.lstrip("-")
        except Exception as e:
            print(f"[Exif Error] Could not extract {tag} from {os.path.basename(file_path)}: {e}")

    return None, None


# --- INTERNAL HELPER FUNCTIONS ---

def _get_installed_version():
    """Checks the version of the currently-resolved ExifTool, if any."""
    path = resolve_exiftool_path()
    if not path:
        return None
    try:
        output = subprocess.check_output(
            [path, "-ver"], text=True, timeout=SUBPROCESS_TIMEOUT, **SUBPROCESS_ARGS
        ).strip()
        return output
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
