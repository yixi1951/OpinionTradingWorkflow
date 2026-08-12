-- PostgreSQL auth schema (mirrored from AuthDatabase._postgres_schema).
-- Applied automatically on AuthDatabase connect when AUTH_DATABASE_URL is postgres*.
-- Manual apply: psql "$AUTH_DATABASE_URL" -f deploy/sql/auth_schema.postgres.sql

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL DEFAULT '',
    password_salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    email_verified INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique
    ON users (email) WHERE email <> '';
CREATE UNIQUE INDEX IF NOT EXISTS users_username_lower_unique
    ON users (lower(username));
CREATE TABLE IF NOT EXISTS roles (name TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS user_roles (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL REFERENCES roles(name),
    PRIMARY KEY(user_id, role)
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    csrf_token TEXT NOT NULL,
    expires_at BIGINT NOT NULL,
    created_at BIGINT NOT NULL,
    last_seen_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions(user_id);
CREATE TABLE IF NOT EXISTS email_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose TEXT NOT NULL,
    expires_at BIGINT NOT NULL,
    used_at BIGINT,
    created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS watchlists (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    created_at BIGINT NOT NULL,
    PRIMARY KEY(user_id, symbol)
);
CREATE TABLE IF NOT EXISTS alert_rules (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    score_high DOUBLE PRECISION NOT NULL DEFAULT 0.35,
    score_low DOUBLE PRECISION NOT NULL DEFAULT -0.35,
    heat_spike_ratio DOUBLE PRECISION NOT NULL DEFAULT 2.0,
    enabled INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY(user_id, symbol)
);
CREATE TABLE IF NOT EXISTS broker_accounts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    account_label TEXT NOT NULL,
    encrypted_config TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    verified_at BIGINT,
    created_at BIGINT NOT NULL,
    UNIQUE(user_id, provider, account_label)
);
CREATE TABLE IF NOT EXISTS orders (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    request_id TEXT NOT NULL UNIQUE,
    broker_account_id BIGINT REFERENCES broker_accounts(id),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    order_type TEXT NOT NULL,
    limit_price DOUBLE PRECISION,
    status TEXT NOT NULL,
    broker_order_id TEXT,
    raw_response TEXT,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
);

INSERT INTO roles(name) VALUES ('viewer'), ('analyst'), ('admin')
ON CONFLICT DO NOTHING;
