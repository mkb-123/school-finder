#!/bin/sh
set -e

DB_PATH="${SQLITE_PATH:-/app/data/schools.db}"

if [ -f "$DB_PATH" ]; then
    echo "Database found at $DB_PATH"
else
    echo "Warning: No database found at $DB_PATH"
    echo "Tables will be created by the application on startup."
fi

exec .venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000
