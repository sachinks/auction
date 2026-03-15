"""
dev_reset.py
────────────
Local development reset script.
Wipes the SQLite database, re-runs all migrations, creates superuser sk/kpl2025.

Usage:
    python dev_reset.py
"""
import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Remove old DB
db_path = os.path.join(os.path.dirname(__file__), "db.sqlite3")
if os.path.exists(db_path):
    os.remove(db_path)
    print("✓ Removed db.sqlite3")

# Set up Django
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

# Run migrations
from django.core.management import call_command
call_command("migrate", verbosity=1)

# Create superuser
from django.contrib.auth.models import User
if not User.objects.filter(username="sk").exists():
    User.objects.create_superuser("sk", "sk@kpl.local", "kpl2025")
    print("✓ Superuser created: sk / kpl2025")
else:
    print("✓ Superuser 'sk' already exists")

# Create logs directory
logs_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(logs_dir, exist_ok=True)
gitkeep = os.path.join(logs_dir, ".gitkeep")
if not os.path.exists(gitkeep):
    open(gitkeep, "w").close()
print("✓ logs/ directory ready")

print("\n✅ Dev reset complete. Run: python manage.py runserver")
