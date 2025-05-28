#!/bin/bash
# Set environment variables for PRODUCTION testing with Supabase
export $(cat env.production | grep -v '^#' | xargs)

echo "🚀 Environment set for PRODUCTION (Supabase):"
echo "DATABASE_URL: ${DATABASE_URL:0:50}..."
echo "SECRET_KEY: ${SECRET_KEY:0:20}..."
echo "FLASK_ENV: $FLASK_ENV"
echo ""
echo "☁️ Using SUPABASE database"