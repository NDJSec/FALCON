#!/bin/bash
set -e

READY_FLAG="/var/lib/postgresql/data/kb_ready.flag"

echo "🚀 Initializing PostgreSQL database..."

# Ensure the ready flag is cleared on startup
if [ -f "$READY_FLAG" ]; then
  echo "🧹 Removing old KB ready flag..."
  rm -f "$READY_FLAG"
fi

# Wait for Postgres to become ready
until pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do
  echo "⏳ Waiting for PostgreSQL to start..."
  sleep 2
done

# If dump file exists, restore KB tables
if [ -f /docker-entrypoint-initdb.d/knowledge_base.dump ]; then
  echo "📦 Found knowledge_base.dump — restoring KB tables..."
  pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    --clean --if-exists -v \
    --jobs="$(nproc)" \
    --disable-triggers \
    --no-owner --no-acl \
    --table=langchain_pg_collection \
    --table=langchain_pg_embedding \
    /docker-entrypoint-initdb.d/knowledge_base.dump
  echo "✅ KB restore complete."
else
  echo "ℹ️ No dump file found — skipping KB restore."
fi

# Create flag file to signal success
touch "$READY_FLAG"
echo "🟢 Knowledge Base ready — flag created at $READY_FLAG"
