import os
import shutil
import subprocess
from datetime import datetime
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
            return backup_file
        return None

    elif settings["db_type"] == "postgresql":
        backup_file = os.path.join(
            settings["backup_dir"], f"servicedesk_{timestamp}.sql"
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
                return backup_file
            else:
                print(f"Backup failed: {result.stderr}")
                return None
        except Exception as e:
            print(f"Backup error: {e}")
            return None

    return None


def restore_backup(backup_file):
    settings = get_backup_settings()

    if settings["db_type"] == "sqlite":
        if os.path.exists(backup_file):
            db_path = "instance/servicedesk.db"
            shutil.copy2(backup_file, db_path)
            return True
        return False

    elif settings["db_type"] == "postgresql":
        env = os.environ.copy()
        env["PGPASSWORD"] = settings["db_password"]

        cmd = [
            "pg_restore",
            "-h",
            settings["db_host"],
            "-p",
            str(settings["db_port"]),
            "-U",
            settings["db_user"],
            "-d",
            settings["db_name"],
            "-c",
            "-v",
            backup_file,
        ]

        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            print(f"Restore error: {e}")
            return False

    return False


def list_backups():
    settings = get_backup_settings()
    backup_dir = settings["backup_dir"]

    if not os.path.exists(backup_dir):
        return []

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

    return sorted(backups, key=lambda x: x["created"], reverse=True)


def cleanup_old_backups(max_backups=10):
    backups = list_backups()

    if len(backups) > max_backups:
        for backup in backups[max_backups:]:
            try:
                os.remove(backup["path"])
                print(f"Deleted old backup: {backup['name']}")
            except Exception as e:
                print(f"Failed to delete {backup['name']}: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "backup":
            result = create_backup()
            if result:
                print(f"Backup created: {result}")
            else:
                print("Backup failed")

        elif command == "list":
            for b in list_backups():
                print(f"{b['name']} - {b['size']} bytes - {b['created']}")

        elif command == "restore" and len(sys.argv) > 2:
            restore_backup(sys.argv[2])

        elif command == "cleanup":
            cleanup_old_backups()
    else:
        print("Usage: python -m app.backup [backup|list|restore <file>|cleanup]")
