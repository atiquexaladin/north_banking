import os
import hashlib
import re
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from email.message import EmailMessage
from functools import wraps
from urllib.parse import urlparse

import psycopg
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db, init_db, save_file_backup

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-secret-key")


@app.context_processor
def inject_account():
    account = None
    if session.get("account_id"):
        with get_db() as connection:
            account = connection.execute(
                "SELECT account_id, customer_name, account_type, balance, recovery_email, created_at "
                "FROM accounts WHERE account_id = %s AND is_active = TRUE",
                (session["account_id"],),
            ).fetchone()
        if account is None:
            session.clear()
    return {"current_account": account}


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("account_id"):
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def parse_amount(value):
    try:
        amount = Decimal(value)
        if not amount.is_finite() or amount <= 0:
            raise ValueError
        if amount != amount.quantize(Decimal("0.01")):
            raise ValueError
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Enter a valid amount with up to two decimal places.")
    return amount


def record_transaction(connection, account_id, transaction_type, amount, related_account_id=None):
    connection.execute(
        "INSERT INTO transactions (account_id, transaction_type, amount, related_account_id) "
        "VALUES (%s, %s, %s, %s)",
        (account_id, transaction_type, amount, related_account_id),
    )


def refresh_file_backup():
    try:
        save_file_backup()
    except OSError as error:
        app.logger.error("Could not update the local bank data backup: %s", error)
        flash(
            "PostgreSQL saved the change, but the local JSON backup could not be updated.",
            "error",
        )


def send_pin_reset_email(recipient, reset_url):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_from = os.getenv("SMTP_FROM") or smtp_user
    if not smtp_host or not smtp_user or not smtp_password or not smtp_from:
        raise RuntimeError("SMTP email settings are not configured.")

    message = EmailMessage()
    message["Subject"] = "Reset your Northstar Bank PIN"
    message["From"] = smtp_from
    message["To"] = recipient
    message.set_content(
        "We received a request to reset your Northstar Bank PIN.\n\n"
        f"Use this one-time link within 20 minutes:\n{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )

    if os.getenv("SMTP_USE_SSL", "").lower() in ("1", "true", "yes"):
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10) as server:
            server.login(smtp_user, smtp_password)
            server.send_message(message)
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(message)


@app.route("/")
def index():
    return redirect(url_for("dashboard" if session.get("account_id") else "login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        recovery_email = request.form.get("recovery_email", "").strip().lower()
        account_type = request.form.get("account_type", "")
        pin = request.form.get("pin", "")

        if (
            not name
            or len(name) > 120
            or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", recovery_email)
            or account_type not in ("Savings", "Current")
            or not pin.isdigit()
            or not 4 <= len(pin) <= 6
        ):
            flash("Enter your name, a valid recovery email, an account type, and a 4 to 6 digit PIN.", "error")
            return render_template("register.html")

        try:
            with get_db() as connection:
                account = connection.execute(
                    "INSERT INTO accounts (customer_name, recovery_email, account_type, pin_hash) "
                    "VALUES (%s, %s, %s, %s) RETURNING account_id",
                    (name, recovery_email, account_type, generate_password_hash(pin)),
                ).fetchone()
        except psycopg.errors.UniqueViolation:
            flash("An account already uses that recovery email. Log in or use another email.", "error")
            return render_template("register.html")
        refresh_file_backup()
        flash(
            f"Account created. Your account number is {account['account_id']}. Please save it.",
            "success",
        )
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/forgot-pin", methods=["GET", "POST"])
def forgot_pin():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        generic_message = "If an active account uses that email, a reset link will be sent shortly."

        public_base_url = (
            os.getenv("PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL", "")
        ).rstrip("/")
        parsed_base_url = urlparse(public_base_url)
        if (
            not all(os.getenv(key) for key in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"))
            or not public_base_url
            or parsed_base_url.scheme not in ("http", "https")
            or not parsed_base_url.netloc
            or parsed_base_url.username
            or parsed_base_url.password
        ):
            flash("PIN reset email is not configured yet. Please contact the site operator.", "error")
            return render_template("forgot_pin.html")

        with get_db() as connection:
            account = connection.execute(
                "SELECT account_id, recovery_email FROM accounts "
                "WHERE LOWER(recovery_email) = %s AND is_active = TRUE",
                (email,),
            ).fetchone()
            if account:
                token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
                connection.execute(
                    "UPDATE accounts SET reset_token_hash = %s, reset_expires_at = %s "
                    "WHERE account_id = %s",
                    (token_hash, datetime.now(timezone.utc) + timedelta(minutes=20), account["account_id"]),
                )
                reset_url = f"{public_base_url}{url_for('reset_pin', token=token)}"
                try:
                    send_pin_reset_email(account["recovery_email"], reset_url)
                except (OSError, smtplib.SMTPException, RuntimeError, ValueError) as error:
                    app.logger.error("Could not send a PIN reset email: %s", error)

        flash(generic_message, "success")
        return redirect(url_for("forgot_pin"))
    return render_template("forgot_pin.html")


@app.route("/reset-pin/<token>", methods=["GET", "POST"])
def reset_pin(token):
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if request.method == "POST":
        pin = request.form.get("pin", "")
        if not pin.isdigit() or not 4 <= len(pin) <= 6:
            flash("Choose a new PIN with 4 to 6 digits.", "error")
            return render_template("reset_pin.html", token=token)

        with get_db() as connection:
            account = connection.execute(
                "UPDATE accounts SET pin_hash = %s, reset_token_hash = NULL, reset_expires_at = NULL "
                "WHERE reset_token_hash = %s AND reset_expires_at > CURRENT_TIMESTAMP "
                "AND is_active = TRUE RETURNING account_id",
                (generate_password_hash(pin), token_hash),
            ).fetchone()
        if account:
            flash("Your PIN has been reset. Log in with your new PIN.", "success")
            return redirect(url_for("login"))
        flash("This reset link is invalid, expired, or already used.", "error")
        return redirect(url_for("forgot_pin"))

    with get_db() as connection:
        valid_token = connection.execute(
            "SELECT 1 FROM accounts WHERE reset_token_hash = %s "
            "AND reset_expires_at > CURRENT_TIMESTAMP AND is_active = TRUE",
            (token_hash,),
        ).fetchone()
    if not valid_token:
        flash("This reset link is invalid, expired, or already used.", "error")
        return redirect(url_for("forgot_pin"))
    return render_template("reset_pin.html", token=token)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        account_number = request.form.get("account_id", "").strip()
        pin = request.form.get("pin", "")
        try:
            account_id = int(account_number)
        except ValueError:
            account_id = 0

        with get_db() as connection:
            account = connection.execute(
                "SELECT account_id, pin_hash FROM accounts "
                "WHERE account_id = %s AND is_active = TRUE",
                (account_id,),
            ).fetchone()
        if account and check_password_hash(account["pin_hash"], pin):
            session.clear()
            session["account_id"] = account["account_id"]
            return redirect(url_for("dashboard"))
        flash("Invalid account number or PIN.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    with get_db() as connection:
        transactions = connection.execute(
            "SELECT transactions.*, related.customer_name AS related_name "
            "FROM transactions LEFT JOIN accounts AS related "
            "ON transactions.related_account_id = related.account_id "
            "WHERE transactions.account_id = %s "
            "ORDER BY transactions.transaction_date DESC, transactions.transaction_id DESC LIMIT 5",
            (session["account_id"],),
        ).fetchall()
        summary = connection.execute(
            "SELECT COUNT(*) AS transaction_count, "
            "COALESCE(SUM(amount) FILTER (WHERE transaction_type IN ('Deposit', 'Received')), 0) AS total_credits, "
            "COALESCE(SUM(amount) FILTER (WHERE transaction_type IN ('Withdrawal', 'Transfer')), 0) AS total_debits "
            "FROM transactions WHERE account_id = %s",
            (session["account_id"],),
        ).fetchone()
    return render_template("dashboard.html", transactions=transactions, summary=summary)


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    if request.method == "POST":
        try:
            amount = parse_amount(request.form.get("amount"))
        except ValueError as error:
            flash(str(error), "error")
            return render_template("deposit.html")

        with get_db() as connection:
            connection.execute(
                "UPDATE accounts SET balance = balance + %s WHERE account_id = %s",
                (amount, session["account_id"]),
            )
            record_transaction(connection, session["account_id"], "Deposit", amount)
        refresh_file_backup()
        flash("Deposit completed successfully.", "success")
        return redirect(url_for("dashboard"))
    return render_template("deposit.html")


@app.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():
    if request.method == "POST":
        try:
            amount = parse_amount(request.form.get("amount"))
        except ValueError as error:
            flash(str(error), "error")
            return render_template("withdraw.html")

        with get_db() as connection:
            account = connection.execute(
                "SELECT balance FROM accounts WHERE account_id = %s AND is_active = TRUE FOR UPDATE",
                (session["account_id"],),
            ).fetchone()
            if amount > account["balance"]:
                flash("Insufficient funds.", "error")
                return render_template("withdraw.html")
            connection.execute(
                "UPDATE accounts SET balance = balance - %s WHERE account_id = %s",
                (amount, session["account_id"]),
            )
            record_transaction(connection, session["account_id"], "Withdrawal", amount)
        refresh_file_backup()
        flash("Withdrawal completed successfully.", "success")
        return redirect(url_for("dashboard"))
    return render_template("withdraw.html")


@app.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():
    if request.method == "POST":
        try:
            recipient_id = int(request.form.get("account_id", ""))
            if recipient_id <= 0 or recipient_id == session["account_id"]:
                raise ValueError
        except (ValueError, TypeError):
            flash("Enter a valid account number different from your own.", "error")
            return render_template("transfer.html")
        try:
            amount = parse_amount(request.form.get("amount"))
        except ValueError as error:
            flash(str(error), "error")
            return render_template("transfer.html")

        with get_db() as connection:
            locked_accounts = connection.execute(
                "SELECT account_id, customer_name, balance, is_active FROM accounts "
                "WHERE account_id IN (%s, %s) ORDER BY account_id FOR UPDATE",
                (session["account_id"], recipient_id),
            ).fetchall()
            accounts = {account["account_id"]: account for account in locked_accounts}
            sender = accounts.get(session["account_id"])
            recipient = accounts.get(recipient_id)

            if not recipient or not recipient["is_active"]:
                flash("That active recipient account could not be found.", "error")
                return render_template("transfer.html")
            if amount > sender["balance"]:
                flash("Insufficient funds.", "error")
                return render_template("transfer.html")

            connection.execute(
                "UPDATE accounts SET balance = balance - %s WHERE account_id = %s",
                (amount, sender["account_id"]),
            )
            connection.execute(
                "UPDATE accounts SET balance = balance + %s WHERE account_id = %s",
                (amount, recipient["account_id"]),
            )
            record_transaction(connection, sender["account_id"], "Transfer", amount, recipient_id)
            record_transaction(connection, recipient_id, "Received", amount, sender["account_id"])
        refresh_file_backup()
        flash("Transfer completed successfully.", "success")
        return redirect(url_for("dashboard"))
    return render_template("transfer.html")


@app.route("/transactions")
@login_required
def transactions():
    with get_db() as connection:
        items = connection.execute(
            "SELECT transactions.*, related.customer_name AS related_name "
            "FROM transactions LEFT JOIN accounts AS related "
            "ON transactions.related_account_id = related.account_id "
            "WHERE transactions.account_id = %s "
            "ORDER BY transactions.transaction_date DESC, transactions.transaction_id DESC",
            (session["account_id"],),
        ).fetchall()
    return render_template("transactions.html", transactions=items)


@app.route("/close-account", methods=["POST"])
@login_required
def close_account():
    with get_db() as connection:
        account = connection.execute(
            "SELECT balance FROM accounts WHERE account_id = %s AND is_active = TRUE FOR UPDATE",
            (session["account_id"],),
        ).fetchone()
        if account["balance"] != 0:
            flash("Withdraw or transfer your remaining balance before closing the account.", "error")
            return redirect(url_for("dashboard"))
        connection.execute(
            "UPDATE accounts SET is_active = FALSE WHERE account_id = %s",
            (session["account_id"],),
        )
    refresh_file_backup()
    session.clear()
    flash("Your account has been closed.", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    init_db()
    save_file_backup()
    app.run(debug=True)
