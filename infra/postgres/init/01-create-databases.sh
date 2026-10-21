#!/bin/sh
# Creates one logical database per transactional service on first boot.
# Runs only when the pg_data volume is empty.

create_database() {
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
        -c "CREATE DATABASE \"$1\";"
}

create_database "${AUTH_DB_NAME:?AUTH_DB_NAME is required}"
create_database "${USERS_DB_NAME:?USERS_DB_NAME is required}"
create_database "${ROLES_DB_NAME:?ROLES_DB_NAME is required}"
