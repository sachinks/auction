import os
import django
from pathlib import Path

print("Starting development reset...")

# ---------------------------------
# DELETE DATABASE
# ---------------------------------

if os.path.exists("db.sqlite3"):
    os.remove("db.sqlite3")
    print("Database deleted")


# ---------------------------------
# DELETE MIGRATIONS
# ---------------------------------

migrations_dir = Path("auction/migrations")

for file in migrations_dir.glob("00*.py"):
    if file.name != "__init__.py":
        os.remove(file)

for file in migrations_dir.glob("00*.pyc"):
    os.remove(file)

print("Old migrations removed")


# ---------------------------------
# LOAD DJANGO
# ---------------------------------

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django.setup()

from django.core.management import call_command
from django.contrib.auth.models import User


# ---------------------------------
# RUN MIGRATIONS
# ---------------------------------

print("Creating migrations...")
call_command("makemigrations")

print("Applying migrations...")
call_command("migrate")


# ---------------------------------
# CREATE SUPERUSER
# ---------------------------------

print("Creating superuser...")

User.objects.create_superuser(
    username="sk",
    email="sk@example.com",
    password="sk"
)

print("Superuser created")
print("username: sk")
print("password: sk")

print("Development reset completed")