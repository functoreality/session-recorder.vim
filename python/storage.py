"""Storage v2 protocol, also vendored by independent activity collectors.

This module uses only the standard library and has no package imports.
All writers register a logical day before creating it. Missing registered
workspaces are abandoned, even if a review or a collector failed.
"""

import json
import os
import sys
import uuid
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path


class DiscardedDay(ValueError):
    pass


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
            xdg("XDG_DATA_HOME", home / ".local" / "share") / "my-big-brother")


def read_json(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object: " + str(path))
    return value


def write_json(path, value):
    """Atomic metadata replacement. Callers serialize writes to the same path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    pending = path.with_name(path.name + ".pending")
    with pending.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    pending.chmod(0o600)
    os.replace(pending, path)


@contextmanager
def file_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def timestamp(value=None):
    result = datetime.now().astimezone() if value is None else value
    if isinstance(result, str):
        result = datetime.fromisoformat(result.replace("Z", "+00:00"))
    if not isinstance(result, datetime) or result.utcoffset() is None:
        raise ValueError("An explicit timezone offset is required")
    return result.astimezone()


def managed_layout(daily_root):
    root = Path(daily_root)
    marker = root.parent / 'memory/_system/storage.json'
    if root.name != 'daily' or not marker.exists():
        return None
    result = Layout(read_json(marker))
    result.check()
    if result.daily.resolve() != root.resolve():
        raise ValueError('Daily directory does not match its persistent storage contract')
    return result


class Layout:
    def __init__(self, value):
        if (set(value) != {"schema_version", "data_root", "day_start_hour"}
                or type(value["schema_version"]) is not int or value["schema_version"] != 2):
            raise ValueError("storage.json requires the version 2 storage contract")
        root = value["data_root"]
        hour = value["day_start_hour"]
        if (not isinstance(root, str) or not root or "\n" in root or "\r" in root
                or not Path(root).is_absolute()):
            raise ValueError("storage.data_root must be an absolute path")
        if type(hour) is not int or not 0 <= hour <= 23:
            raise ValueError("storage.day_start_hour must be between 0 and 23")
        self.settings = value
        self.root = Path(root)
        self.hour = hour
        self.daily = self.root / "daily"
        self.memory = self.root / "memory"
        self.system = self.memory / "_system"

    @classmethod
    def load(cls, config_dir, *, required=True):
        path = Path(config_dir) / "storage.json"
        if not path.exists():
            if required:
                raise ValueError("Storage v2 is not initialized. Run init or migrate-storage.")
            return None
        result = cls(read_json(path))
        result.check()
        return result

    @classmethod
    def install(cls, config_dir, data_root, hour=0):
        path = Path(config_dir) / "storage.json"
        settings = {"schema_version": 2, "data_root": str(data_root), "day_start_hour": hour}
        if path.exists():
            result = cls.load(config_dir)
            if result.settings != settings:
                raise ValueError("Existing storage preserved. Changing its root or calendar needs migration.")
            return result
        result = cls(settings)
        marker = result.system / "storage.json"
        if marker.exists() and read_json(marker) != settings:
            raise ValueError("Existing data has a different storage calendar")
        for directory in (result.daily, result.system / "days", result.system / "locks"):
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        write_json(marker, settings)
        write_json(path, settings)
        return result

    def check(self):
        if read_json(self.system / "storage.json") != self.settings:
            raise ValueError("Storage calendar changed or persistent metadata is unavailable")
        if not (self.system / "days").is_dir():
            raise ValueError("Persistent day registry is missing. Do not initialize an empty replacement.")

    def day(self, value=None):
        moment = timestamp(value)
        return (moment.date() - timedelta(days=moment.hour < self.hour)).isoformat()

    def launch_directory(self, preferred_day=None):
        # Log ownership only. The executing Agent chooses its review plan.
        preferred = preferred_day or (date.fromisoformat(self.day()) - timedelta(days=1)).isoformat()
        try:
            directory = self.ensure_day(preferred)
        except DiscardedDay:
            directory = self.ensure_day(self.day())
        launch = directory / "_launches" / uuid.uuid4().hex
        launch.mkdir(parents=True, mode=0o700)
        return launch

    def bounds(self, day):
        parsed = date.fromisoformat(day)
        if parsed.isoformat() != day:
            raise ValueError("Dates must use YYYY-MM-DD")
        return (datetime.combine(parsed, time(hour=self.hour)).astimezone(),
                datetime.combine(parsed + timedelta(days=1), time(hour=self.hour)).astimezone())

    def _record(self, day):
        self.check()
        self.bounds(day)
        path = self.system / "days" / (day + ".json")
        value = read_json(path) if path.exists() else None
        if value is not None:
            if (value.get("date") != day or value.get("disposition") not in ("retained", "discarded")
                    or not isinstance(value.get("workspace_id"), str)):
                raise ValueError("Invalid persistent day record: " + str(path))
            marker = self.daily / day / "_workspace.json"
            missing = not marker.exists()
            mismatched = not missing and read_json(marker).get("workspace_id") != value["workspace_id"]
            if value["disposition"] == "retained" and (missing or mismatched):
                value["disposition"] = "discarded"
                write_json(path, value)
        return value

    def record(self, day):
        self.check()
        self.bounds(day)
        with file_lock(self.system / "locks" / "storage" / (day + ".lock")):
            return self._record(day)

    def ensure_day(self, day, *, recreate=False):
        self.check()
        self.bounds(day)
        with file_lock(self.system / "locks" / "storage" / (day + ".lock")):
            record = self._record(day)
            if record and record["disposition"] == "discarded" and not recreate:
                raise DiscardedDay("Day workspace was discarded: " + day)
            directory = self.daily / day
            if record is None or record["disposition"] == "discarded":
                start, end = self.bounds(day)
                record = {"date": day, "workspace_id": uuid.uuid4().hex,
                          "disposition": "retained", "review": (record or {}).get("review", {}),
                          "window": {"start": start.isoformat(), "end": end.isoformat()}}
                write_json(self.system / "days" / (day + ".json"), record)
                directory.mkdir(parents=True, exist_ok=True, mode=0o700)
                write_json(directory / "_workspace.json", {"workspace_id": record["workspace_id"]})
            return directory

    def update_review(self, day, review):
        self.check()
        self.bounds(day)
        with file_lock(self.system / "locks" / "storage" / (day + ".lock")):
            value = self._record(day)
            if value is None or value["disposition"] == "discarded":
                raise DiscardedDay("Day workspace was discarded: " + day)
            value["review"] = review
            write_json(self.system / "days" / (day + ".json"), value)

    def check_run(self, run_dir, workspace_id=None):
        directory = Path(run_dir).resolve()
        parts = directory.relative_to(self.daily.resolve()).parts
        if len(parts) != 3 or parts[1] != "_analysis":
            raise ValueError("Not a storage v2 review run")
        record = self.record(parts[0])
        if (not record or record["disposition"] == "discarded"
                or (workspace_id is not None and workspace_id != record["workspace_id"])):
            raise DiscardedDay("Run belongs to a discarded workspace")
        return record
