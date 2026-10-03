DO $$
BEGIN
    IF to_regclass('public.transactions') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1
           FROM information_schema.columns
           WHERE table_schema = 'public'
             AND table_name = 'transactions'
             AND column_name = 'transaction_id'
       ) THEN
        ALTER TABLE transactions RENAME TO legacy_transactions;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS accounts (
    account_id BIGSERIAL PRIMARY KEY,
    customer_name TEXT NOT NULL,
    account_type TEXT NOT NULL CHECK (account_type IN ('Savings', 'Current')),
    balance NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (balance >= 0),
    pin_hash TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE accounts
    ADD COLUMN IF NOT EXISTS recovery_email TEXT,
    ADD COLUMN IF NOT EXISTS reset_token_hash TEXT,
    ADD COLUMN IF NOT EXISTS reset_expires_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS accounts_recovery_email_unique
    ON accounts (LOWER(recovery_email))
    WHERE recovery_email IS NOT NULL AND recovery_email <> '';

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts (account_id),
    transaction_type TEXT NOT NULL CHECK (
        transaction_type IN ('Deposit', 'Withdrawal', 'Transfer', 'Received')
    ),
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    transaction_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    related_account_id BIGINT REFERENCES accounts (account_id)
);
