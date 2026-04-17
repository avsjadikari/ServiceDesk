#!/usr/bin/env python
"""
Automated backup script for ServiceDesk
Can be run manually or scheduled via cron/Task Scheduler

Usage:
    python scripts/backup.py          # Create backup
    python scripts/backup.py --list   # List backups
    python scripts/backup.py --clean # Clean old backups
"""

import os
import sys
import shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def get_backup_settings():
    db_type = os.environ.get("DB_TYPE", "sqlite")
    db_host = os.environ.get("DB_HOST", "localhost")
    db_port = os.environ.get("DB_PORT", "5432")
    db_name = os.environ.get("DB_NAME", "servicedesk")
    db_user = os.environ.get("DB_USER", "servicedesk")
    db_password = os.environ.get("DB_PASSWORD", "")
    backup_dir = os.environ.get("BACKUP_DIR", "backups")

    return {
        "db_type": db_type,
        "db_host": db_host,
        "db_port": db_port,
        "db_name": db_name,
        "db_user": db_user,
        "db_password": db_password,
        "backup_dir": backup_dir,
    }


def create_backup():
    settings = get_backup_settings()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if not os.path.exists(settings["backup_dir"]):
        os.makedirs(settings["backup_dir"])

    if settings["db_type"] == "sqlite":
        db_path = "instance/servicedesk.db"
        if os.path.exists(db_path):
            backup_file = os.path.join(
                settings["backup_dir"], f"servicedesk_{timestamp}.db"
            )
            shutil.copy2(db_path, backup_file)
            size = os.path.getsize(backup_file)
            print(f"✓ Backup created: {backup_file} ({size:,} bytes)")
            return True
        else:
            print("✗ Database file not found")
            return False

    elif settings["db_type"] == "postgresql":
        import subprocess

        backup_file = os.path.join(
            settings["backup_dir"], f"servicedesk_{timestamp}.dump"
        )

        env = os.environ.copy()
        env["PGPASSWORD"] = settings["db_password"]

        cmd = [
            "pg_dump",
            "-h",
            settings["db_host"],
            "-p",
            str(settings["db_port"]),
            "-U",
            settings["db_user"],
            "-F",
            "c",
            "-b",
            "-v",
            "-f",
            backup_file,
            settings["db_name"],
        ]

        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if result.returncode == 0:
                size = os.path.getsize(backup_file)
                print(f"✓ Backup created: {backup_file} ({size:,} bytes)")
                return True
            else:
                print(f"✗ Backup failed: {result.stderr}")
                return False
        except FileNotFoundError:
            print("✗ pg_dump not found. Install PostgreSQL client tools.")
            return False
        except Exception as e:
            print(f"✗ Backup error: {e}")
            return False

    return False


def list_backups():
    settings = get_backup_settings()
    backup_dir = settings["backup_dir"]

    if not os.path.exists(backup_dir):
        print("No backups found")
        return

    backups = []
    for f in os.listdir(backup_dir):
        if f.startswith("servicedesk_"):
            path = os.path.join(backup_dir, f)
            backups.append(
                {
                    "name": f,
                    "path": path,
                    "size": os.path.getsize(path),
                    "created": datetime.fromtimestamp(os.path.getctime(path)),
                }
            )

    if not backups:
        print("No backups found")
        return

    print(f"\nBackups in {backup_dir}:")
    print("-" * 60)
    for b in sorted(backups, key=lambda x: x["created"], reverse=True):
        print(f"{b['name']:<35} {b['size']:>10,} bytes  {b['created']}")
    print("-" * 60)


def cleanup_backups(max_backups=10):
    settings = get_backup_settings()
    backup_dir = settings["backup_dir"]

    if not os.path.exists(backup_dir):
        return

    backups = []
    for f in os.listdir(backup_dir):
        if f.startswith("servicedesk_"):
            path = os.path.join(backup_dir, f)
            backups.append(
                {
                    "name": f,
                    "path": path,
                    "created": datetime.fromtimestamp(os.path.getctime(path)),
                }
            )

    backups.sort(key=lambda x: x["created"], reverse=True)

    if len(backups) > max_backups:
        for backup in backups[max_backups:]:
            try:
                os.remove(backup["path"])
                print(f"✓ Deleted: {backup['name']}")
            except Exception as e:
                print(f"✗ Failed to delete {backup['name']}: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--list":
            list_backups()
        elif sys.argv[1] == "--clean":
            cleanup_backups()
        else:
            print("Usage: python scripts/backup.py [--list|--clean]")
    else:
        success = create_backup()
        if success:
            cleanup_backups()
