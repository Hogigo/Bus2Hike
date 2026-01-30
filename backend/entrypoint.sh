#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

echo "--- Starting Entrypoint Script ---"

# 1. Run the Database Initialization/Wipe logic
# This uses the script we built with psycopg2
echo "Running database initialization..."
python -m scripts.init_db

# 2. Start the main application
# 'exec' ensures that signals (like CTRL+C) are passed directly to your python app
echo "Starting Application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload