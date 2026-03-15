#!/usr/bin/env bash
set -e

echo "── Installing dependencies ──────────────────────"
pip install -r requirements.txt

echo "── Collecting static files ──────────────────────"
python manage.py collectstatic --no-input

echo "── Running migrations ───────────────────────────"
python manage.py migrate

echo "── Creating superuser ───────────────────────────"
python manage.py shell -c "
import os
from django.contrib.auth.models import User
username = os.environ.get('ADMIN_USERNAME', 'sk')
password = os.environ.get('ADMIN_PASSWORD', 'kpl2025')
user, created = User.objects.get_or_create(username=username)
user.set_password(password)
user.is_staff = True
user.is_superuser = True
user.save()
print(f'Superuser {username} ready')
"

echo "── Ensuring logs directory ──────────────────────"
mkdir -p logs && touch logs/.gitkeep

echo "✅ Build complete"
