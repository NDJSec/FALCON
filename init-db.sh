#!/bin/bash
set -e

# This script waits for Postgres to be ready and then creates the
# Timescale vector extensions.
#
# We are now using 'vector', which is the standard pgvector extension
# and is expected by LangChain.

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL
