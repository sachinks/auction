#!/usr/bin/env bash
set -e

echo "── Installing dependencies ──────────────────────"
pip install -r requirements.txt

echo "── Collecting static files ──────────────────────"
python manage.py collectstatic --no-input

echo "── Running migrations ───────────────────────────"
python manage.py migrate

echo "── Creating superuser (sk/kpl2025) ──────────────"
python manage.py shell -c "
from django.contrib.auth.models import User
import os
if not User.objects.filter(username='sk').exists():
    User.objects.create_superuser('sk', 'sk@kpl.local', 'kpl2025')
    print('Superuser sk created')
else:
    print('Superuser sk already exists')
"

echo "── Ensuring logs directory ──────────────────────"
mkdir -p logs && touch logs/.gitkeep

echo "✅ Build complete"
