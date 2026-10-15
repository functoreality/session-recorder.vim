"""Small JSON-over-stdio helper. No editor provider or third-party modules."""

import difflib
import errno
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from uuid import uuid4


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def platform_paths(system=None, home=None, environ=None):
    system = sys.platform if system is None else system
    home = Path.home() if home is None else Path(home)
    env = os.environ if environ is None else environ
    if system == "darwin":
        base = home / "Library" / "Application Support" / "my-big-brother"
        return base / "configs", base / "data"
    if system == "win32":
        base = Path(env.get("LOCALAPPDATA") or home / "AppData" / "Local") / "my-big-brother"
        return base / "configs", base / "data"

    def xdg(name, fallback):
        value = Path(env.get(name, ""))
        return value if value.is_absolute() else fallback

    return (xdg("XDG_CONFIG_HOME", home / ".config") / "my-big-brother",
            xdg("XDG_DATA_HOME", home / ".local/share") / "my-big-brother")


def absolute(value):
    if (not isinstance(value, str) or not value or "\n" in value
            or "\r" in value or not Path(value).is_absolute()):
        raise ValueError("Expected an absolute path without ~ or variable expansion")
    return Path(value)


def configure(config):
    config_dir, data_dir = platform_paths()
    locator = config_dir / "raw-logs-path.txt"
    override = config.get("record_dir", "")
    if override:
        root, origin = absolute(override), "record_dir"
    elif locator.exists():
        value = locator.read_bytes().decode("utf-8")
        if value.endswith("\r\n"):
            value = value[:-2]
        elif value.endswith("\n"):
            value = value[:-1]
        root, origin = absolute(value), str(locator)
    else:
        root, origin = data_dir / "raw-logs", "platform default"
    size = config.get("max_file_size", 1048576)
    if type(size) is not int or size <= 0:
        raise ValueError("max_file_size must be a positive integer")
    patterns = config.get("exclude_patterns", ["*.tmp", "*.log", ".git/*"])
    if not isinstance(patterns, list) or any(not isinstance(p, str) for p in patterns):
        raise ValueError("exclude_patterns must be a list of Vim regular expressions")
    return {"root": str(root), "path_source": origin,
            "max_file_size": size, "exclude_patterns": patterns}


def file_label(filename):
    """Keep a readable, bounded basename hint that is safe on all three systems."""
    label = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "_", filename).strip(" .")
    stem, extension = os.path.splitext(label)
    if len(stem) > 20:
        label = stem[:18] + ".." + (extension or stem[-8:])
    encoded = label.encode("utf-8")
    if len(encoded) > 64:
        label = (encoded[:30].decode("utf-8", errors="ignore") + ".."
                 + encoded[-32:].decode("utf-8", errors="ignore"))
    return label.rstrip(" .")


def start(config, first_file=""):
    timestamp = now()
    day = timestamp[:10]
    session_id = uuid4().hex
    parent = Path(config["root"]) / day / "vim"
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    clock = timestamp[11:19].replace(":", "-")
    label = file_label(Path(first_file).name) if first_file else ""
    while True:
        short_id = session_id[:8]
        name = clock + "_" + (label + "_" if label else "") + short_id
        directory = parent / name
        try:
            directory.mkdir(mode=0o700)
            break
        except FileExistsError:
            session_id = uuid4().hex
        except OSError as exc:
            # A custom root can leave too little room for the optional hint.
            if not label or (exc.errno != errno.ENAMETOOLONG
                             and getattr(exc, "winerror", None) not in (123, 206)):
                raise
            label = ""
    return {"session_id": session_id, "vim_start": timestamp, "directory": str(directory)}


def lf_lines(data):
    """Split exactly as diff does: CR is content, only LF terminates a line."""
    lines = data.split(b"\n")
    return [line + b"\n" for line in lines[:-1]] + ([lines[-1]] if lines[-1] else [])


def diff_counts(content):
    lines = content.split(b"\n")
    return (sum(line.startswith(b"+") for line in lines[2:]),
            sum(line.startswith(b"-") for line in lines[2:]))


def unified_fallback(original, current, old_name, new_name):
    """Portable LF-based unified diff without SequenceMatcher's autojunk loss."""
    old, new = lf_lines(original), lf_lines(current)
    begin = 0
    while begin < min(len(old), len(new)) and old[begin] == new[begin]:
        begin += 1
    if begin == len(old) == len(new):
        return b"", 0, 0
    end = 0
    while (end < min(len(old), len(new)) - begin
           and old[len(old) - end - 1] == new[len(new) - end - 1]):
        end += 1
    # Keep context but avoid quadratic matching over an unchanged repetitive file.
    offset = max(0, begin - 3)
    old_end, new_end = min(len(old), len(old) - end + 3), min(len(new), len(new) - end + 3)
    matcher = difflib.SequenceMatcher(None, old[offset:old_end], new[offset:new_end], autojunk=False)
    output = [b"--- " + old_name.encode("utf-8") + b"\n",
              b"+++ " + new_name.encode("utf-8") + b"\n"]
    added = deleted = 0

    def line(prefix, content):
        output.append(prefix + content)
        if not content.endswith(b"\n"):
            output.append(b"\n\\ No newline at end of file\n")

    def region(start, stop):
        size = stop - start
        return str(start if size == 0 else start + 1) + ("," + str(size) if size != 1 else "")

    for group in matcher.get_grouped_opcodes(3):
        first, last = group[0], group[-1]
        header = "@@ -" + region(first[1] + offset, last[2] + offset)
        header += " +" + region(first[3] + offset, last[4] + offset) + " @@\n"
        output.append(header.encode("ascii"))
        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                for value in old[i1 + offset:i2 + offset]:
                    line(b" ", value)
            else:
                if tag in ("replace", "delete"):
                    for value in old[i1 + offset:i2 + offset]:
                        line(b"-", value)
                    deleted += i2 - i1
                if tag in ("replace", "insert"):
                    for value in new[j1 + offset:j2 + offset]:
                        line(b"+", value)
                    added += j2 - j1
    return b"".join(output), added, deleted


def system_diff(original_path, current_path):
    executable = shutil.which("diff")
    if not executable:
        return None
    arguments = [executable, "-u"]
    arguments.extend([str(original_path), str(current_path)])
    try:
        result = subprocess.run(arguments, capture_output=True)
    except OSError:
        return None
    if result.returncode not in (0, 1):
        # An installed diff may not support these paths or options.
        return None
    return (result.stdout,) + diff_counts(result.stdout)


def finalize_file(record, directory):
    if record.get("snapshot_status") != "ok":
        record["diff_generated"] = False
        return
    original_path = directory / record["original_file"]
    path = Path(record["path"])
    # The opening byte limit does not restrict exit comparisons.
    if path.exists():
        result = system_diff(original_path, path)
    else:
        result = None
    if result is None:
        original = original_path.read_bytes()
        current = path.read_bytes() if path.exists() else b""
        new_name = str(path) if path.exists() else "/dev/null"
        content, added, deleted = unified_fallback(original, current,
                                                   record["original_file"], new_name)
        record["modified"] = original != current
    else:
        content, added, deleted = result
        record["modified"] = bool(content)
    record["diff_generated"] = True
    if content:
        filename = f"{record['id']}-modification.diff"
        (directory / filename).write_bytes(content)
        record.update(diff_file=filename, lines_added=added, lines_deleted=deleted)


def finalize(session, files):
    directory = Path(session["directory"])
    for record in files:
        try:
            finalize_file(record, directory)
        except (OSError, ValueError) as exc:
            record["diff_generated"] = False
            record["error"] = str(exc)
    payload = {"schema_version": 1, "source": "vim", "session_id": session["session_id"],
               "vim_start": session["vim_start"], "vim_close": now(), "opened_files": files}
    # A reader sees either the previous complete file or the new complete file.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory,
                                     prefix="record-", suffix=".tmp", delete=False) as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        temporary = stream.name
    os.replace(temporary, directory / "record.json")
    return {"record": str(directory / "record.json"), "files": len(files),
            "errors": sum("error" in record for record in files)}


def dispatch(request):
    action = request["action"]
    if action == "configure":
        return configure(request["config"])
    if action == "start":
        return start(request["config"], request.get("first_file", ""))
    if action == "finalize":
        return finalize(request["session"], request["files"])
    raise ValueError("Unknown recorder action")


if __name__ == "__main__":
    try:
        request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        result = {"ok": True, "result": dispatch(request)}
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    json.dump(result, sys.stdout, ensure_ascii=True)
    sys.stdout.write("\n")
