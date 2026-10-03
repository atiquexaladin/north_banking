import getpass
import os
import secrets
from pathlib import Path
from urllib.parse import quote

import psycopg
from dotenv import dotenv_values
from psycopg import sql


PROJECT_DIR = Path(__file__).resolve().parent
ENV_PATH = PROJECT_DIR / ".env"


def main():
    host = input("PostgreSQL host [localhost]: ").strip() or "localhost"
    port_text = input("PostgreSQL port [5432]: ").strip() or "5432"
    username = input("PostgreSQL username [postgres]: ").strip() or "postgres"
    database_name = input("Database name [bank_db]: ").strip() or "bank_db"
    try:
        port = int(port_text)
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise SystemExit("PostgreSQL port must be a number between 1 and 65535.")
    if not database_name or "\x00" in database_name:
        raise SystemExit("Enter a valid database name.")

    password = getpass.getpass("PostgreSQL password (input is hidden): ")
    try:
        with psycopg.connect(
            host=host,
            port=port,
            dbname="postgres",
            user=username,
            password=password,
            connect_timeout=5,
            autocommit=True,
        ) as connection:
            exists = connection.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (database_name,),
            ).fetchone()
            if not exists:
                connection.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
                )
                print(f"Created PostgreSQL database '{database_name}'.")
            else:
                print(f"PostgreSQL database '{database_name}' already exists.")
    except psycopg.Error as error:
        raise SystemExit(f"Could not connect to PostgreSQL or create the database: {error}")

    old_config = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    host_for_url = f"[{host}]" if ":" in host and not host.startswith("[") else host
    database_url = (
        f"postgresql://{quote(username, safe='')}:{quote(password, safe='')}"
        f"@{host_for_url}:{port}/{quote(database_name, safe='')}"
    )
    secret_key = old_config.get("SECRET_KEY") or secrets.token_urlsafe(32)
    config = {"DATABASE_URL": database_url, "SECRET_KEY": secret_key}
    for key in (
        "PUBLIC_BASE_URL",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USE_SSL",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "SMTP_FROM",
    ):
        if old_config.get(key):
            config[key] = old_config[key]
    ENV_PATH.write_text(
        "".join(f"{key}={value}\n" for key, value in config.items()),
        encoding="utf-8",
    )
    os.environ["DATABASE_URL"] = database_url
    os.environ["SECRET_KEY"] = secret_key

    from database import init_db, save_file_backup

    init_db()
    save_file_backup()
    print("Database connection verified; banking tables are ready.")
    print("Configuration saved to .env. Start the app with: python app.py")


if __name__ == "__main__":
    main()
