"""Small JSON-over-stdio helper. No editor provider or third-party modules."""

import difflib
import errno
import fnmatch
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from datetime import datetime
from uuid import uuid4
import importlib.util

_spec = importlib.util.spec_from_file_location("mbb_storage", Path(__file__).with_name("storage.py"))
storage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(storage)


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def platform_paths(system=None, home=None, environ=None):
    system = sys.platform if system is None else system
    home = Path.home() if home is None else Path(home)
    env = os.environ if environ is None else environ
    if system == "darwin":
        base = home / "Library" / "Application Support" / "my-big-brother"
        return base / "configs", base / "data"
    if system == "win32":
        base = Path(env.get("LOCALAPPDATA") or home / "AppData" / "Local")
        base /= "my-big-brother"
        return base / "configs", base / "data"

    def xdg(name, fallback):
        value = Path(env.get(name, ""))
        return value if value.is_absolute() else fallback

    return (xdg("XDG_CONFIG_HOME", home / ".config") / "my-big-brother",
            xdg("XDG_DATA_HOME", home / ".local" / "share") / "my-big-brother")


def absolute(value):
    if (not isinstance(value, str) or not value or "\n" in value
            or "\r" in value or not Path(value).is_absolute()):
        raise ValueError("Expected an absolute path without ~ or variable expansion")
    return Path(value)


def configure(config):
    config_dir, data_dir = platform_paths()
    locator = config_dir / "raw-logs-path.txt"
    override = config.get("record_dir", "")
    layout = storage.Layout.load(config_dir, required=False) if not override else None
    if override:
        root = absolute(override)
        origin = "record_dir override (standalone, outside shared discovery)"
    elif layout is not None:
        root = layout.daily
        origin = str(config_dir / "storage.json")
    elif locator.exists():
        value = locator.read_bytes().decode("utf-8")
        if value.endswith("\r\n"):
            value = value[:-2]
        elif value.endswith("\n"):
            value = value[:-1]
        root = absolute(value)
        origin = str(locator)
    else:
        root = data_dir / "raw-logs"
        origin = "platform default"
    size = config.get("max_file_size", 1048576)
    if type(size) is not int or size <= 0:
        raise ValueError("max_file_size must be a positive integer")
    patterns = config.get("exclude_patterns", ["*.tmp", "*.log", ".git/*"])
    if not isinstance(patterns, list) or any(not isinstance(p, str) for p in patterns):
        raise ValueError("exclude_patterns must be a list of glob strings")
    return {"root": str(root), "locator": str(locator), "path_source": origin,
            "storage_config": str(config_dir), "storage_version": 2 if layout else 1,
            "standalone": bool(override), "max_file_size": size,
            "exclude_patterns": patterns}


def excluded(path, config):
    normalized = str(path).replace("\\", "/")
    parts = normalized.split("/")
    candidates = ["/".join(parts[i:]) for i in range(len(parts))] + parts
    return any(fnmatch.fnmatchcase(value, pattern)
               for pattern in config["exclude_patterns"] for value in candidates)


def file_label(filename):
    """Keep a readable, bounded basename hint that is safe on all three systems."""
    label = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "_", filename).strip(" .")
    return label.encode("utf-8")[:64].decode("utf-8", errors="ignore").rstrip(" .")


def start(config, first_file=""):
    timestamp = now()
    session_id = uuid4().hex
    parent = Path(config["root"])
    layout = storage.Layout.load(config["storage_config"]) if config.get("storage_version") == 2 else None
    if layout is not None:
        parent = layout.ensure_day(layout.day(timestamp)) / "vim"
    elif not config["standalone"]:
        parent = parent / timestamp[:10] / "vim"
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    clock = timestamp[11:19].replace(":", "-")
    label = file_label(Path(first_file).name) if first_file else ""
    compact = clock + "_" + session_id
    directory = parent / (clock + "_" + label + "_" + session_id if label else compact)
    try:
        directory.mkdir(mode=0o700)
    except OSError as exc:
        # A custom root can leave too little room for the optional hint.
        if not label or (exc.errno != errno.ENAMETOOLONG
                         and getattr(exc, "winerror", None) not in (123, 206)):
            raise
        directory = parent / compact
        directory.mkdir(mode=0o700)
    session = {"session_id": session_id, "vim_start": timestamp, "directory": str(directory)}
    if layout is not None:
        day = layout.day(timestamp)
        session.update(logical_day=day, workspace_id=layout.record(day)["workspace_id"],
                       root_session_id=session_id)
    return session


def read_text_bytes(path, limit):
    # Bound reads even if the file grows after stat().
    with path.open("rb") as stream:
        data = stream.read(limit)
    if len(data) >= limit:
        return None, "too_large"
    if b"\0" in data:
        return None, "binary"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return None, "non_utf8"
    return data, ""


def capture(path, file_id, directory, config):
    if config.get("storage_version") == 2:
        layout = storage.Layout.load(config["storage_config"])
        day = Path(directory).parent.parent.name
        record = layout.record(day)
        if not record or record["disposition"] == "discarded":
            return None
    path = absolute(path)
    if excluded(path, config) or excluded(path.resolve(), config) or path.is_dir():
        return None
    record = {"id": file_id, "path": str(path), "opened": now()}
    if config.get("storage_version") == 2:
        record["day_checkpoint"] = True
    resolved = path.resolve()
    if resolved != path:
        record["resolved_path"] = str(resolved)
    try:
        if not path.exists():
            record["new_file"] = True
            data, reason = b"", ""
        else:
            info = path.stat()
            record["size"] = info.st_size
            if not stat.S_ISREG(info.st_mode):
                record["snapshot_status"] = "unsupported_file"
                return record
            data, reason = read_text_bytes(path, config["max_file_size"])
        if reason:
            record["snapshot_status"] = reason
            if reason == "binary":
                record["is_binary"] = True
        else:
            suffix = path.suffix
            if not re.fullmatch(r"\.[A-Za-z0-9_-]{1,16}", suffix):
                suffix = ".txt"
            filename = f"{file_id}-original{suffix}"
            (Path(directory) / filename).write_bytes(data)
            record["original_file"] = filename
            record["snapshot_status"] = "ok"
    except OSError as exc:
        record["snapshot_status"] = "error"
        record["error"] = str(exc)
    return record


def unified(original, current, old_name, new_name):
    lines = list(difflib.diff_bytes(difflib.unified_diff,
                 original.splitlines(keepends=True), current.splitlines(keepends=True),
                 fromfile=old_name.encode("utf-8"), tofile=new_name.encode("utf-8")))
    # difflib leaves unterminated input lines unterminated, unlike diff -u.
    output = []
    for line in lines:
        output.append(line)
        if not line.endswith(b"\n"):
            output.append(b"\n\\ No newline at end of file\n")
    added = sum(line.startswith(b"+") for line in lines[2:])
    deleted = sum(line.startswith(b"-") for line in lines[2:])
    return b"".join(output), added, deleted


def finalize_file(record, directory, limit):
    if record.get("snapshot_status") != "ok":
        record["diff_generated"] = False
        return
    record.pop("diff_status", None)
    record.pop("error", None)
    path = Path(record["path"])
    if path.exists():
        current, reason = read_text_bytes(path, limit)
        if reason:
            record["diff_generated"] = False
            record["diff_status"] = reason
            return
        new_name = str(path)
    else:
        current, new_name = b"", "/dev/null"
    original = (directory / record["original_file"]).read_bytes()
    if record.get('day_checkpoint'):
        checkpoint_file = str(record['id']) + '-checkpoint.txt'
        (directory / checkpoint_file).write_bytes(current)
        record['checkpoint_file'] = checkpoint_file
    content, added, deleted = unified(original, current,
                                      record["original_file"], new_name)
    record["modified"] = original != current
    record["diff_generated"] = True
    if content:
        filename = f"{record['id']}-modification.diff"
        (directory / filename).write_bytes(content)
        record.update(diff_file=filename, lines_added=added, lines_deleted=deleted)
    elif "diff_file" in record:
        (directory / record.pop("diff_file")).write_bytes(b"")
        record.pop("lines_added", None)
        record.pop("lines_deleted", None)


def finalize(session, files, config, *, checkpoint=False):
    directory = Path(session["directory"])
    if config.get("storage_version") == 2:
        layout = storage.Layout.load(config["storage_config"])
        state = layout.record(session["logical_day"])
        if (not state or state["disposition"] == "discarded"
                or state["workspace_id"] != session["workspace_id"]):
            return {"record": "", "files": 0, "errors": 0, "discarded": True}
    for record in files:
        focus = record.get("last_focus_line", {})
        if "time_epoch" in focus:
            focus["time"] = datetime.fromtimestamp(focus.pop("time_epoch")).astimezone().isoformat()
        try:
            finalize_file(record, directory, config["max_file_size"])
        except (OSError, ValueError) as exc:
            record["diff_generated"] = False
            record["error"] = str(exc)
    payload = {"schema_version": 1, "source": "vim", "session_id": session["session_id"],
               "vim_start": session["vim_start"], "vim_close": now(), "opened_files": files}
    if config.get("storage_version") == 2:
        payload.update(storage_version=2, logical_day=session["logical_day"],
                       root_session_id=session["root_session_id"], segment_open=checkpoint,
                       diff_scope="Independent logical-day segment through the recorded checkpoint")
        if session.get("boundary_gap"):
            payload["boundary_gap"] = session["boundary_gap"]
    # A reader sees either the previous complete file or the new complete file.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory,
                                     prefix="record-", suffix=".tmp", delete=False) as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        temporary = stream.name
    os.replace(temporary, directory / "record.json")
    return {"record": str(directory / "record.json"), "files": len(files),
            "errors": sum("error" in record or record.get("diff_status") is not None
                          for record in files)}


def checkpoint(session, files, config):
    """Persist a day-local checkpoint or begin an independent later-day segment.

    On a delayed rollover, retain the last prior-day checkpoint. Never read
    today's disk bytes and attribute their changes to a closed earlier day.
    """
    if config.get("storage_version") != 2:
        return {"session": session, "files": files}
    layout = storage.Layout.load(config["storage_config"])
    current = now()
    day = layout.day(current)
    if day == session["logical_day"]:
        result = finalize(session, files, config, checkpoint=True)
        return {"session": session, "files": files, "discarded": result.get("discarded", False)}
    old_record = Path(session["directory"]) / "record.json"
    prior = layout.record(session["logical_day"])
    if old_record.exists() and prior and prior["disposition"] != "discarded":
        payload = storage.read_json(old_record)
        payload.update(segment_open=False, rollover_observed_at=current,
                       boundary_gap="Changes after the last checkpoint and before rollover are not attributed")
        storage.write_json(old_record, payload)
    try:
        following = start(config, files[0]["path"] if files else "")
    except storage.DiscardedDay:
        return {"session": session, "files": files, "discarded": True}
    following["root_session_id"] = session["root_session_id"]
    following["boundary_gap"] = "No observation between the last prior-day checkpoint and this segment baseline"
    refreshed = []
    for old in files:
        item = capture(old["path"], len(refreshed) + 1, following["directory"], config)
        if item is not None:
            item.update(continued=True, original_opened=old.get("original_opened", old["opened"]))
            prior_snapshot = Path(session['directory']) / old.get('checkpoint_file', '__missing__')
            if item.get('original_file') and prior_snapshot.is_file():
                previous = prior_snapshot.read_bytes()
                latest = (Path(following['directory']) / item['original_file']).read_bytes()
                bridge, _, _ = unified(previous, latest, 'previous-checkpoint', item['original_file'])
                if bridge:
                    name = str(item['id']) + '-boundary.diff'
                    (Path(following['directory']) / name).write_bytes(bridge)
                    item.update(boundary_diff_file=name,
                                boundary_diff_scope='Cross-boundary observed difference, not attributable to this day alone')
            refreshed.append(item)
    finalize(following, refreshed, config, checkpoint=True)
    return {"session": following, "files": refreshed, "rotated": True}


def dispatch(request):
    action = request["action"]
    if action == "configure":
        return configure(request["config"])
    if action == "start":
        return start(request["config"], request.get("first_file", ""))
    if action == "capture":
        return capture(request["path"], request["file_id"],
                       request["directory"], request["config"])
    if action == "finalize":
        if request["config"].get("storage_version") == 2:
            value = checkpoint(request["session"], request["files"], request["config"])
            return finalize(value["session"], value["files"], request["config"])
        return finalize(request["session"], request["files"], request["config"])
    if action == "checkpoint":
        return checkpoint(request["session"], request["files"], request["config"])
    raise ValueError("Unknown recorder action")


if __name__ == "__main__":
    try:
        request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        result = {"ok": True, "result": dispatch(request)}
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    json.dump(result, sys.stdout, ensure_ascii=True)
    sys.stdout.write("\n")
