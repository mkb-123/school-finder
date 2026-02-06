#!/bin/sh
set -e

DB_PATH="${SQLITE_PATH:-/app/data/schools.db}"

# Seed database on first run (empty volume)
if [ ! -f "$DB_PATH" ]; then
    echo "No database found at $DB_PATH — seeding..."
    uv run python -m src.db.seed --council "Milton Keynes"
    echo "Seed complete."
fi

exec uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
