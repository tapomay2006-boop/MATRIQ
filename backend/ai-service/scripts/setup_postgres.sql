-- Local Postgres setup for ai-service.
-- Run once:  sudo -u postgres psql -f scripts/setup_postgres.sql

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'sih') THEN
        CREATE ROLE sih LOGIN PASSWORD 'sih';
    END IF;
END
$$;

SELECT 'CREATE DATABASE numm_ai OWNER sih'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'numm_ai')\gexec

\connect numm_ai
GRANT ALL ON SCHEMA public TO sih;
ALTER SCHEMA public OWNER TO sih;
