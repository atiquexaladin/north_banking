# Simple Banking System

A beginner-friendly Flask app using Python and PostgreSQL. It demonstrates classes, objects, functions, dictionaries, JSON file handling, and exception handling.

## Features

- Create a Savings or Current account and log in with its generated account number and PIN.
- Store a recovery email and reset a forgotten PIN using a single-use link that expires after 20 minutes.
- Deposit, withdraw, and transfer money between accounts.
- Check the balance and view the transaction history.
- Close an account after its balance reaches zero. Closed accounts cannot log in or receive transfers.
- Keep PostgreSQL as the main database and refresh `data/bank_backup.json` after account or transaction changes. PINs are hashed in PostgreSQL and are never written to the JSON file.

## Run locally

1. Install Python and PostgreSQL, and make sure the PostgreSQL service is running.
2. From this folder, install the dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Set up the database and connection securely. The setup command prompts for the PostgreSQL password without displaying it, creates `bank_db` if needed, writes the local `.env`, and initializes the tables:

   ```powershell
   python setup_database.py
   ```

   The PostgreSQL user must be allowed to connect to the `postgres` database and create databases. To use an existing database instead, enter its name at the prompt; the user must be allowed to create tables in it.

4. Start the app:

   ```powershell
   python app.py
   ```

5. Open `http://127.0.0.1:5000` in your browser and create an account.

### Configure PIN reset email

PIN recovery needs an SMTP account. Add `PUBLIC_BASE_URL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USE_SSL`, `SMTP_USER`, `SMTP_PASSWORD`, and `SMTP_FROM` to `.env`. `PUBLIC_BASE_URL` must be the URL customers use to open the app; for local development use `http://127.0.0.1:5000`. Use an SMTP app password where the email provider supports it. For port 587, keep `SMTP_USE_SSL=false` (STARTTLS); for port 465, set it to `true` (implicit TLS). Restart the app after changing `.env`.

The recovery email is collected during registration. Accounts created before recovery email was added do not yet have one on file and cannot use PIN reset until their recovery email is added to PostgreSQL.

The app currently has a customer dashboard only; it does not include an admin profile or admin dashboard.

The app creates its `accounts` and `transactions` tables on startup. If the older version of this project has a `transactions` table, it is renamed to `legacy_transactions` so its records are preserved while the new banking table is created.

This project is for learning and is not intended for handling real money or production banking.
