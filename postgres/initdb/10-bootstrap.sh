#!/usr/bin/env bash
# Creates per-service databases and login roles on first start of an empty data directory.
# Application schemas, tables, grants, and policies are created by each service's migrations.
# See docs/adr/0003-service-owned-databases-and-migrations.md.
set -euo pipefail

for var in \
  VERITRACE_CORE_OWNER_PASSWORD VERITRACE_CORE_APP_PASSWORD \
  VERITRACE_TELEMETRY_OWNER_PASSWORD VERITRACE_TELEMETRY_APP_PASSWORD \
  VERITRACE_RELAYER_OWNER_PASSWORD VERITRACE_RELAYER_APP_PASSWORD; do
  if [[ -z "${!var:-}" ]]; then
    echo "bootstrap: ${var} is not set" >&2
    exit 1
  fi
done

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v core_owner_password="$VERITRACE_CORE_OWNER_PASSWORD" \
  -v core_app_password="$VERITRACE_CORE_APP_PASSWORD" \
  -v telemetry_owner_password="$VERITRACE_TELEMETRY_OWNER_PASSWORD" \
  -v telemetry_app_password="$VERITRACE_TELEMETRY_APP_PASSWORD" \
  -v relayer_owner_password="$VERITRACE_RELAYER_OWNER_PASSWORD" \
  -v relayer_app_password="$VERITRACE_RELAYER_APP_PASSWORD" <<'SQL'
-- Owner roles run migrations and own every object in their database.
CREATE ROLE veritrace_core_owner LOGIN PASSWORD :'core_owner_password';
CREATE ROLE veritrace_telemetry_owner LOGIN PASSWORD :'telemetry_owner_password';
CREATE ROLE veritrace_relayer_owner LOGIN PASSWORD :'relayer_owner_password';

-- Runtime roles own nothing and never bypass row-level security.
CREATE ROLE veritrace_core_app LOGIN NOBYPASSRLS PASSWORD :'core_app_password';
CREATE ROLE veritrace_telemetry_app LOGIN NOBYPASSRLS PASSWORD :'telemetry_app_password';
CREATE ROLE veritrace_relayer_app LOGIN NOBYPASSRLS PASSWORD :'relayer_app_password';

CREATE DATABASE veritrace_core OWNER veritrace_core_owner;
CREATE DATABASE veritrace_telemetry OWNER veritrace_telemetry_owner;
CREATE DATABASE veritrace_relayer OWNER veritrace_relayer_owner;

REVOKE ALL ON DATABASE veritrace_core, veritrace_telemetry, veritrace_relayer FROM PUBLIC;
GRANT CONNECT ON DATABASE veritrace_core TO veritrace_core_app;
GRANT CONNECT ON DATABASE veritrace_telemetry TO veritrace_telemetry_app;
GRANT CONNECT ON DATABASE veritrace_relayer TO veritrace_relayer_app;

ALTER ROLE veritrace_core_owner IN DATABASE veritrace_core SET search_path = core, public;
ALTER ROLE veritrace_core_app IN DATABASE veritrace_core SET search_path = core;
ALTER ROLE veritrace_telemetry_owner IN DATABASE veritrace_telemetry SET search_path = telemetry, public;
ALTER ROLE veritrace_telemetry_app IN DATABASE veritrace_telemetry SET search_path = telemetry, public;
ALTER ROLE veritrace_relayer_owner IN DATABASE veritrace_relayer SET search_path = relayer, public;
ALTER ROLE veritrace_relayer_app IN DATABASE veritrace_relayer SET search_path = relayer;

ALTER DATABASE veritrace_core SET timezone = 'UTC';
ALTER DATABASE veritrace_telemetry SET timezone = 'UTC';
ALTER DATABASE veritrace_relayer SET timezone = 'UTC';

-- TimescaleDB requires superuser to install; only the telemetry database uses it.
\connect veritrace_telemetry
CREATE EXTENSION IF NOT EXISTS timescaledb;
SQL

echo "bootstrap: databases and roles created"
