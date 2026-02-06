#!/bin/sh
set -e

DB_PATH="${SQLITE_PATH:-/app/data/schools.db}"
SEED_DB="/app/seed/schools.db"

# Check if database exists and has data
if [ -f "$DB_PATH" ]; then
    # Check if database has schools (empty databases have no tables or no rows)
    SCHOOL_COUNT=$(uv run python -c "import sqlite3; conn = sqlite3.connect('$DB_PATH'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM schools'); print(cursor.fetchone()[0]); conn.close()" 2>/dev/null || echo "0")

    if [ "$SCHOOL_COUNT" = "0" ]; then
        echo "Database exists but is empty (0 schools). Replacing with seed database..."
        if [ -f "$SEED_DB" ]; then
            cp "$SEED_DB" "$DB_PATH"
            echo "Seed database copied successfully!"
        fi
    else
        echo "Database found with $SCHOOL_COUNT schools"
    fi
else
    # Database doesn't exist - copy seed
    if [ -f "$SEED_DB" ]; then
        echo "No database found. Copying pre-seeded database from $SEED_DB to $DB_PATH"
        cp "$SEED_DB" "$DB_PATH"
        echo "Database copied successfully!"
    else
        echo "No database found and no seed database available"
        echo "Database tables will be created by the application on startup."
    fi
fi

exec uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
