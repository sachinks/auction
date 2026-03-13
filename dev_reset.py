import os
import django
from pathlib import Path

print("Starting development reset...")

# Delete database
if os.path.exists("db.sqlite3"):
    os.remove("db.sqlite3")
    print("Database deleted")

# Delete old migrations
migrations_dir = Path("auction/migrations")
for file in migrations_dir.glob("00*.py"):
    if file.name != "__init__.py":
        os.remove(file)
for file in migrations_dir.glob("00*.pyc"):
    os.remove(file)
print("Old migrations removed")

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.core.management import call_command
from django.contrib.auth.models import User

print("Creating migrations...")
call_command("makemigrations")
print("Applying migrations...")
call_command("migrate")

# Ensure media/banners and static/backgrounds directories exist
os.makedirs("media/banners", exist_ok=True)
os.makedirs("static/backgrounds", exist_ok=True)
print("Media and static directories ready")

# Create TournamentSettings singleton
from auction.models import TournamentSettings
TournamentSettings.get()
print("TournamentSettings singleton created")

# Create superuser
print("Creating superuser...")
User.objects.create_superuser(username="sk", email="sk@example.com", password="sk")
print("username: sk | password: sk")

print("\nDevelopment reset complete.")
print("Run: python manage.py runserver")
