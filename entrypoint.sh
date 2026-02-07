#!/bin/sh
set -e

DB_PATH="${SQLITE_PATH:-/app/data/schools.db}"

# Check if database exists and has data
if [ -f "$DB_PATH" ]; then
    SCHOOL_COUNT=$(.venv/bin/python -c "
import sqlite3, sys
try:
    conn = sqlite3.connect(sys.argv[1])
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM schools')
    print(cursor.fetchone()[0])
    conn.close()
except Exception:
    print('0')
" "$DB_PATH" 2>/dev/null || echo "0")
    echo "Database found at $DB_PATH with $SCHOOL_COUNT schools"
else
    echo "Warning: No database found at $DB_PATH"
    echo "Tables will be created by the application on startup."
fi

exec uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
