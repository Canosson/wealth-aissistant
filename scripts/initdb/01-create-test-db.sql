-- Runs once on first Postgres boot (docker-entrypoint-initdb.d).
-- Creates the isolated database the pytest suite drops/recreates schema in,
-- so tests never touch the app's `wealth` database.
SELECT 'CREATE DATABASE wealth_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'wealth_test')\gexec
