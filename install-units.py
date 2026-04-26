#!/usr/bin/env python3
"""Install systemd user units generated from config.json."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import importlib.util
import argparse
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parent
CONFIG_PATH = REPO_DIR / "config.json"
SCRIPT_PATH = REPO_DIR / "icloud-bisync.py"
APP_NAME = "icloud-sync"


def load_bisync_module():
    spec = importlib.util.spec_from_file_location("icloud_bisync", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Unable to load {SCRIPT_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def unit_path_value(path: str) -> str:
    return path.replace("\\", "\\\\")


def write_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install icloud-sync as a systemd user application."
    )
    parser.add_argument(
        "--force-config",
        action="store_true",
        help="Overwrite ~/.config/icloud-sync/config.json from the source config.json.",
    )
    args = parser.parse_args()

    icloud_bisync = load_bisync_module()
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))

    app_dir = data_home / APP_NAME
    app_config_dir = config_home / APP_NAME
    work_dir = state_home / APP_NAME
    unit_dir = config_home / "systemd" / "user"

    app_dir.mkdir(parents=True, exist_ok=True)
    app_config_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    unit_dir.mkdir(parents=True, exist_ok=True)

    installed_script = app_dir / "icloud-bisync.py"
    installed_config = app_config_dir / "config.json"
    shutil.copy2(SCRIPT_PATH, installed_script)
    if args.force_config or not installed_config.exists():
        shutil.copy2(CONFIG_PATH, installed_config)

    config = icloud_bisync.load_config(installed_config)
    local_path = icloud_bisync.expand_local_path(config["local_path"])
    Path(local_path).mkdir(parents=True, exist_ok=True)

    service = f"""[Unit]
Description=Sync local folder with iCloud Drive using rclone bisync
Documentation=https://rclone.org/bisync/
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory={unit_path_value(str(work_dir))}
ExecStart=/usr/bin/env python3 {unit_path_value(str(installed_script))} sync --config {unit_path_value(str(installed_config))}
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7
TimeoutStartSec=1h
"""

    path_unit = f"""[Unit]
Description=Watch local iCloud sync folder
Documentation=man:systemd.path(5)

[Path]
PathChanged={unit_path_value(local_path)}
PathModified={unit_path_value(local_path)}
Unit=icloud-sync.service
MakeDirectory=true
DirectoryMode=0755

[Install]
WantedBy=default.target
"""

    timer = """[Unit]
Description=Periodically reconcile local folder with iCloud Drive
Documentation=https://rclone.org/bisync/

[Timer]
OnBootSec=2min
OnUnitActiveSec=10min
Unit=icloud-sync.service
Persistent=true

[Install]
WantedBy=timers.target
"""

    write_file(unit_dir / "icloud-sync.service", service)
    write_file(unit_dir / "icloud-sync.path", path_unit)
    write_file(unit_dir / "icloud-sync.timer", timer)

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)

    print(f"Installed app files to {app_dir}")
    print(f"Installed config to {installed_config}")
    print(f"Installed user units to {unit_dir}")
    print(f"Watching local_path from config.json: {local_path}")
    print("Next: systemctl --user enable --now icloud-sync.path icloud-sync.timer")
    return 0


if __name__ == "__main__":
    sys.exit(main())
