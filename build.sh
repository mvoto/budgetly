#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Run database migrations
python -c "
from app import create_app
from extensions import db

app = create_app()
with app.app_context():
    db.create_all()
    print('Database tables created successfully!')
"
