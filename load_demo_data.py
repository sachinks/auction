
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
django.setup()

from auction.models import Team

teams = ["RCB","MI","CSK","KKR"]

for t in teams:
    Team.objects.create(
        name=t,
        owners="Owner",
        remaining_points=10000
    )

print("Demo teams created")
