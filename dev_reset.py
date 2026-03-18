"""
dev_reset.py
────────────
Local development reset script.
Wipes the SQLite database, re-runs all migrations, creates superuser.

Reads credentials from .env:
    ADMIN_USERNAME  (default: sk)
    ADMIN_PASSWORD  (default: kpl2025)

Usage:
    python dev_reset.py
"""
import os
import sys
import django
from dotenv import load_dotenv

# Load .env BEFORE django.setup()
load_dotenv()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Remove old DB
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.conf import settings
db_path = settings.BASE_DIR / "db.sqlite3"
if db_path.exists():
    db_path.unlink()
    print("✓ Removed db.sqlite3")

# Wipe and regenerate migrations
from pathlib import Path
from django.core.management import call_command

migrations_dir = settings.BASE_DIR / "auction" / "migrations"
deleted = [f.unlink() or f.name for f in migrations_dir.glob("*.py") if f.name != "__init__.py"]
if deleted:
    print(f"✓ Cleared migrations: {', '.join(deleted)}")

call_command("makemigrations", "auction", verbosity=1)
call_command("migrate", verbosity=1)

# Create superuser — always force the password from .env
from django.contrib.auth.models import User
username = os.environ.get("ADMIN_USERNAME", "sk")
password = os.environ.get("ADMIN_PASSWORD", "kpl2025")

user, created = User.objects.get_or_create(username=username)
user.set_password(password)
user.is_staff     = True
user.is_superuser = True
user.save()
print(f"✓ Superuser '{username}' {'created' if created else 'updated'} with password from .env")

# Ensure logs directory exists
logs_dir = settings.BASE_DIR / "logs"
logs_dir.mkdir(exist_ok=True)
gitkeep = logs_dir / ".gitkeep"
if not gitkeep.exists():
    gitkeep.touch()
print("✓ logs/ directory ready")

print(f"\n✅ Dev reset complete.")
print(f"   Login: {username} / {password}")
print(f"   Run:   python manage.py runserver")
