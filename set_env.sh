#!/bin/bash
# Set environment variables for local PostgreSQL development
export DATABASE_URL="postgresql://mauriciovoto@localhost/budgetly"
export SECRET_KEY="dev-key-change-in-production"
export FLASK_ENV="development"

echo "✅ Environment variables set for PostgreSQL development:"
echo "DATABASE_URL: $DATABASE_URL"
echo "SECRET_KEY: $SECRET_KEY"
echo "FLASK_ENV: $FLASK_ENV"