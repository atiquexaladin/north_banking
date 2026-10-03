# Python Flask Banking System with PostgreSQL

A beginner-friendly **Python and SQL project**: a full-stack bank management system built with Flask and PostgreSQL. Use it to learn Python web development, relational database design, SQL queries, and CRUD operations through a working banking demo.

**Tech stack:** Python 3 · Flask · PostgreSQL · SQL · Psycopg · HTML · CSS

Try the live demo: [north-banking.onrender.com](https://north-banking.onrender.com/login). The free demo may take about a minute to wake after inactivity.

## Features

- Create a Savings or Current account and log in with its generated account number and PIN.
- Store a recovery email and reset a forgotten PIN using a single-use link that expires after 20 minutes.
- Deposit, withdraw, and transfer money between accounts.
- Check the balance and view the transaction history.
- Close an account after its balance reaches zero. Closed accounts cannot log in or receive transfers.
- Keep PostgreSQL as the main database and refresh `data/bank_backup.json` after account or transaction changes. PINs are hashed in PostgreSQL and are never written to the JSON file.

## What this Python and SQL project demonstrates

- Building a Python web application with Flask routes, forms, and server-rendered templates.
- Connecting Python to PostgreSQL and defining relational tables, constraints, and foreign keys with SQL.
- Using parameterized SQL queries for account registration, authentication, balances, transfers, and transaction history.
- Implementing database transactions, row locking, password hashing, and one-time PIN recovery tokens.
- Running a full-stack bank management system locally or deploying a demo from GitHub.

This repository is suitable as a **Python PostgreSQL project**, **Python SQL project**, or **bank management system project** for learning and portfolio demonstration.

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

### Free public demo deployment

This Flask app needs a Python web host and PostgreSQL; GitHub Pages only serves static sites and cannot run its backend. A free demo can use the Render free web-service plan with a Neon free PostgreSQL database:

1. Create a free Neon project and copy its pooled PostgreSQL connection string. Keep it private.
2. In Render, create a new Blueprint and connect this public GitHub repository. Render reads `render.yaml` and creates a free web service.
3. Set the service's `DATABASE_URL` to the Neon connection string in Render's environment settings, then deploy.
4. Open the generated `https://...onrender.com` URL. The app creates its tables during startup. Future GitHub pushes trigger redeploys after the repository is linked.

Free Render services sleep after 15 minutes without traffic and can take about a minute to wake. Neon free usage is subject to its current storage, compute, and transfer quotas. This is a learning/demo deployment, not a real-money banking service. PIN reset email additionally needs SMTP settings as described above.

The app creates its `accounts` and `transactions` tables on startup. If the older version of this project has a `transactions` table, it is renamed to `legacy_transactions` so its records are preserved while the new banking table is created.

This project is for learning and is not intended for handling real money or production banking.
