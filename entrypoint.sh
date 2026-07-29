#!/bin/sh
set -e

# The app writes to these at runtime (SQLite db, uploaded/generated
# workbooks). They're expected to be volume-mounted by docker-compose so
# data survives container recreation - create them if a fresh, empty
# volume was just mounted, so the app never has to guess.
mkdir -p /app/data /app/uploads /app/outputs

exec "$@"
