#!/bin/sh
set -e

DB_PATH="${SQLITE_PATH:-/app/data/schools.db}"

# Check if database exists and has data
if [ -f "$DB_PATH" ]; then
    SCHOOL_COUNT=$(uv run python -c "import sqlite3; conn = sqlite3.connect('$DB_PATH'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM schools'); print(cursor.fetchone()[0]); conn.close()" 2>/dev/null || echo "0")
    echo "Database found with $SCHOOL_COUNT schools"
else
    echo "Warning: No database found at $DB_PATH"
    echo "Tables will be created by the application on startup."
fi

exec uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
