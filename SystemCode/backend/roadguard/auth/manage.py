"""Local account provisioning. No public registration or client-selected role."""

import argparse
import getpass
import secrets

from roadguard.config import load_settings
from roadguard.database import Database
from .service import AuthService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "password", "disable"])
    parser.add_argument("username")
    parser.add_argument("--name")
    parser.add_argument("--role", choices=["inspector", "crew", "dispatcher"])
    parser.add_argument("--crew")
    parser.add_argument("--generate-password", action="store_true")
    args = parser.parse_args()
    settings = load_settings()
    database = Database(settings.database_path)
    database.initialize()
    service = AuthService(database, list(settings.project["planning"]["crew_ids"]))
    if args.action == "disable":
        with database.transaction() as connection:
            row = connection.execute("SELECT user_id FROM auth_users WHERE username=?", (args.username.lower(),)).fetchone()
            if row is None: parser.error("Account not found.")
            connection.execute("UPDATE auth_users SET enabled=0 WHERE user_id=?", (row[0],))
            connection.execute("DELETE FROM auth_sessions WHERE user_id=?", (row[0],))
        print("Account disabled; all sessions revoked.")
        return
    password = secrets.token_urlsafe(18) if args.generate_password else getpass.getpass("Password (12–256 characters): ")
    try:
        if args.action == "create":
            if not args.role: parser.error("--role is required for create.")
            service.create_user(args.username, args.name or args.username, args.role, args.crew, password)
        else:
            service.set_password(args.username, password)
    except ValueError as exc:
        parser.error(str(exc))
    print("Account saved.")
    if args.generate_password:
        print("Generated password (store privately):", password)


if __name__ == "__main__":
    main()
