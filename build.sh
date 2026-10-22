#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "Installing production dependencies..."
pip install -r requirements.txt

echo "Collecting static assets..."
python manage.py collectstatic --no-input

echo "Applying database migrations..."
python manage.py migrate

echo "Build completed successfully!"
