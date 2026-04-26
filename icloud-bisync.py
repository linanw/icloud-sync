#!/usr/bin/env python3
"""Run rclone bisync using this repo's config.json."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = REPO_DIR / "config.json"


def expand_local_path(value: str) -> str:
    return str(Path(os.path.expandvars(os.path.expanduser(value))).resolve())


def load_config(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
    except FileNotFoundError:
        raise SystemExit(f"Config file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}")

    required = ("local_path", "icloud_path")
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise SystemExit(f"Missing required config key(s): {', '.join(missing)}")

    flags = config.get("bisync_flags", [])
    if not isinstance(flags, list) or not all(isinstance(item, str) for item in flags):
        raise SystemExit("config key 'bisync_flags' must be a list of strings")

    return config


def build_command(config: dict, *, resync: bool, dry_run: bool) -> list[str]:
    local_path = expand_local_path(config["local_path"])
    icloud_path = config["icloud_path"]

    Path(local_path).mkdir(parents=True, exist_ok=True)

    command = [
        config.get("rclone_bin", "rclone"),
        "bisync",
        local_path,
        icloud_path,
        *config.get("bisync_flags", []),
    ]

    if resync:
        command.append("--resync")
    if dry_run:
        command.append("--dry-run")

    return command


def notify(config: dict, title: str, message: str, *, urgency: str = "normal") -> None:
    if not config.get("notifications", True):
        return

    notify_send = shutil.which("notify-send")
    if notify_send is None:
        print("Notification skipped: notify-send not found", file=sys.stderr)
        return

    try:
        subprocess.run(
            [
                notify_send,
                "--app-name=iCloud Sync",
                f"--urgency={urgency}",
                title,
                message,
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        print(f"Notification skipped: {exc}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run rclone bisync for a local folder and iCloud Drive remote."
    )
    parser.add_argument(
        "mode",
        choices=("sync", "resync", "dry-run", "dry-run-resync"),
        help=(
            "Use 'dry-run-resync' first, then 'resync' once, then normal 'sync' "
            "for subsequent systemd runs."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(os.environ.get("ICLOUD_SYNC_CONFIG", DEFAULT_CONFIG)),
        help="Path to config.json",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    command = build_command(
        config,
        resync=args.mode in ("resync", "dry-run-resync"),
        dry_run=args.mode in ("dry-run", "dry-run-resync"),
    )
    local_path = expand_local_path(config["local_path"])
    icloud_path = config["icloud_path"]

    print("+ " + " ".join(command), flush=True)
    notify(
        config,
        "iCloud sync started",
        f"{local_path} <-> {icloud_path}",
    )

    return_code = subprocess.call(command)
    if return_code == 0:
        notify(
            config,
            "iCloud sync finished",
            f"{local_path} <-> {icloud_path}",
        )
    else:
        notify(
            config,
            "iCloud sync failed",
            f"Exit code {return_code}: {local_path} <-> {icloud_path}",
            urgency="critical",
        )

    return return_code


if __name__ == "__main__":
    sys.exit(main())
