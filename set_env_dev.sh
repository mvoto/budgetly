#!/bin/bash
# Set environment variables for LOCAL DEVELOPMENT with PostgreSQL
export $(cat env.development | grep -v '^#' | xargs)

echo "🔧 Environment set for LOCAL DEVELOPMENT:"
echo "DATABASE_URL: $DATABASE_URL"
echo "SECRET_KEY: $SECRET_KEY"
echo "FLASK_ENV: $FLASK_ENV"
echo ""
echo "💾 Using LOCAL PostgreSQL database"