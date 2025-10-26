#!/bin/bash
# Initialize PostgreSQL database with schema
# This script can be run manually if needed

set -e

echo "Initializing PostgreSQL database..."

# Check if PostgreSQL is accessible
if ! docker-compose exec postgres pg_isready -U ${POSTGRES_USER:-infomerics_user} > /dev/null 2>&1; then
    echo "Error: PostgreSQL is not ready"
    exit 1
fi

# Run migration
echo "Running migration: 001_initial_schema.sql"
docker-compose exec -T postgres psql -U ${POSTGRES_USER:-infomerics_user} -d ${POSTGRES_DB:-infomerics} < migrations/001_initial_schema.sql

echo "PostgreSQL initialization complete!"

