#!/bin/sh
# =============================================================================
# 03-app-role.sh — rol de runtime con privilegios mínimos (ASH)
# -----------------------------------------------------------------------------
# Se ejecuta solo al inicializar un volumen NUEVO de Postgres. Para una base
# existente, correr el equivalente manual o recrear el volumen.
#
# El backend usa APP_DATABASE_URL con este rol para DML; las migraciones/DDL
# siguen usando DATABASE_URL (owner) desde app/database.py.
# =============================================================================

set -eu

: "${APP_DB_USER:?APP_DB_USER no definido}"
: "${APP_DB_PASSWORD:?APP_DB_PASSWORD no definido}"

case "$APP_DB_PASSWORD" in
    *"'"*)
        echo "[app-role] APP_DB_PASSWORD no puede contener comillas simples" >&2
        exit 1
        ;;
esac

if [ "$(psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${APP_DB_USER}'" --username "$POSTGRES_USER" --dbname "$POSTGRES_DB")" != "1" ]; then
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
        -c "CREATE ROLE \"${APP_DB_USER}\" LOGIN PASSWORD '${APP_DB_PASSWORD}'"
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
GRANT CONNECT ON DATABASE "${POSTGRES_DB}" TO "${APP_DB_USER}";
GRANT USAGE ON SCHEMA public TO "${APP_DB_USER}";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "${APP_DB_USER}";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "${APP_DB_USER}";
ALTER DEFAULT PRIVILEGES FOR ROLE "${POSTGRES_USER}" IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "${APP_DB_USER}";
ALTER DEFAULT PRIVILEGES FOR ROLE "${POSTGRES_USER}" IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO "${APP_DB_USER}";
SQL

echo "[app-role] rol ${APP_DB_USER} creado/actualizado con privilegios mínimos"
