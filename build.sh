#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='sk').exists():
    User.objects.create_superuser('sk', 'sk@kpl.com', 'kpl2025')
    print('Superuser created')
else:
    print('Superuser already exists')
"