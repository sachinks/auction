import csv
import re

from auction.models import Player


class CSVService:


    REQUIRED_COLUMNS = ["name", "role", "phone", "place"]

    VALID_ROLES = ["BAT", "BOWL", "AR", "PLY"]


    # -------------------------------------------------
    # VALIDATE PHONE
    # -------------------------------------------------

    def valid_phone(self, phone):

        pattern = r"^\+?[0-9]{10,12}$"

        return re.match(pattern, phone)


    # -------------------------------------------------
    # IMPORT PLAYERS FROM CSV
    # -------------------------------------------------

    def import_players(self, filepath):

        created = 0
        errors = []

        with open(filepath, newline="", encoding="utf-8") as file:

            reader = csv.DictReader(file)

            # Validate header
            if not all(col in reader.fieldnames for col in self.REQUIRED_COLUMNS):

                raise Exception("Invalid CSV header")

            for row in reader:

                name = row["name"].strip()
                role = row["role"].strip()
                phone = row["phone"].strip()
                place = row["place"].strip()

                # Validate role
                if role not in self.VALID_ROLES:

                    errors.append(f"{name}: Invalid role")

                    continue

                # Validate phone
                if not self.valid_phone(phone):

                    errors.append(f"{name}: Invalid phone")

                    continue

                # Prevent duplicates
                if Player.objects.filter(name=name).exists():

                    errors.append(f"{name}: Duplicate player")

                    continue

                try:

                    Player.objects.create(
                        name=name,
                        role=role,
                        phone=phone,
                        place=place,
                        base_price=0,
                        status="AVAILABLE"
                    )

                    created += 1

                except Exception as e:

                    errors.append(str(e))

        return created, errors