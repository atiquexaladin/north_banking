import json
import os
import tempfile
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from models import BankAccount

load_dotenv(Path(__file__).with_name(".env"))

DATABASE_URL = os.getenv("DATABASE_URL")
SCHEMA_PATH = Path(__file__).with_name("bank.sql")
BACKUP_PATH = Path(__file__).with_name("data") / "bank_backup.json"


def get_db():
    if not DATABASE_URL:
        raise RuntimeError(
            "PostgreSQL is not configured: .env is missing DATABASE_URL. "
            "Run '.\\.venv\\Scripts\\python.exe setup_database.py' first, "
            "then enter your PostgreSQL password at the hidden prompt."
        )
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db():
    with get_db() as connection:
        connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


def save_file_backup():
    with get_db() as connection:
        accounts = connection.execute(
            "SELECT account_id, customer_name, account_type, balance, is_active "
            "FROM accounts ORDER BY account_id"
        ).fetchall()
        transactions = connection.execute(
            "SELECT transaction_id, account_id, transaction_type, amount, "
            "transaction_date, related_account_id "
            "FROM transactions ORDER BY transaction_id"
        ).fetchall()

    backup = {
        "accounts": [
            BankAccount(
                account["account_id"],
                account["customer_name"],
                account["account_type"],
                account["balance"],
                account["is_active"],
            ).to_dict()
            for account in accounts
        ],
        "transactions": [
            {
                "transaction_id": transaction["transaction_id"],
                "account_id": transaction["account_id"],
                "transaction_type": transaction["transaction_type"],
                "amount": str(transaction["amount"]),
                "transaction_date": transaction["transaction_date"].isoformat(),
                "related_account_id": transaction["related_account_id"],
            }
            for transaction in transactions
        ],
    }

    BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=BACKUP_PATH.parent,
            suffix=".tmp",
            delete=False,
        ) as backup_file:
            temporary_path = Path(backup_file.name)
            json.dump(backup, backup_file, indent=2)
        temporary_path.replace(BACKUP_PATH)
    except OSError:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
        raise
