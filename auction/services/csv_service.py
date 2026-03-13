import csv
import re

from auction.models import Player, Team


class CSVService:

    PLAYER_REQUIRED = ["name", "role", "phone", "place"]
    TEAM_REQUIRED   = ["name"]
    VALID_ROLES     = ["BAT", "BOWL", "AR", "PLY"]

    def valid_phone(self, phone):
        return re.match(r"^\+?[0-9]{10,12}$", phone)

    # ─────────────────────────────────────────────
    # VALIDATE PLAYERS CSV (no DB write) — item 2
    # ─────────────────────────────────────────────

    def validate_players_csv(self, filepath):
        return self._process_players_csv(filepath, dry_run=True)

    # ─────────────────────────────────────────────
    # IMPORT PLAYERS CSV
    # ─────────────────────────────────────────────

    def import_players(self, filepath):
        return self._process_players_csv(filepath, dry_run=False)

    def _process_players_csv(self, filepath, dry_run=False):
        created = 0
        errors  = []

        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            if not reader.fieldnames or not all(c in reader.fieldnames for c in self.PLAYER_REQUIRED):
                raise Exception(f"Invalid CSV header. Required columns: {', '.join(self.PLAYER_REQUIRED)}")

            for i, row in enumerate(reader, start=2):
                name  = row.get("name", "").strip()
                role  = row.get("role", "").strip().upper()
                phone = row.get("phone", "").strip()
                place = row.get("place", "").strip()

                if not name:
                    errors.append(f"Row {i}: name is empty")
                    continue
                if role not in self.VALID_ROLES:
                    errors.append(f"Row {i} ({name}): invalid role '{role}' — must be one of {self.VALID_ROLES}")
                    continue
                if not self.valid_phone(phone):
                    errors.append(f"Row {i} ({name}): invalid phone '{phone}'")
                    continue
                if not dry_run and Player.objects.filter(name=name).exists():
                    errors.append(f"Row {i} ({name}): duplicate player")
                    continue

                if not dry_run:
                    try:
                        Player.objects.create(name=name, role=role, phone=phone,
                                              place=place, base_price=0, status="AVAILABLE")
                        created += 1
                    except Exception as e:
                        errors.append(f"Row {i} ({name}): {e}")
                else:
                    created += 1  # count valid rows in dry-run

        return created, errors

    # ─────────────────────────────────────────────
    # VALIDATE TEAMS CSV (no DB write) — item 14
    # ─────────────────────────────────────────────

    def validate_teams_csv(self, filepath):
        return self._process_teams_csv(filepath, dry_run=True)

    # ─────────────────────────────────────────────
    # IMPORT TEAMS CSV — item 14
    # ─────────────────────────────────────────────

    def import_teams(self, filepath):
        return self._process_teams_csv(filepath, dry_run=False)

    def _process_teams_csv(self, filepath, dry_run=False):
        created = 0
        errors  = []

        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            if not reader.fieldnames or "name" not in reader.fieldnames:
                raise Exception("Invalid CSV header. Required column: name")

            for i, row in enumerate(reader, start=2):
                name       = row.get("name", "").strip()
                short_name = row.get("short_name", "").strip()
                owners     = row.get("owners", "").strip()
                payment    = row.get("payment_info", "0").strip()

                if not name:
                    errors.append(f"Row {i}: team name is empty")
                    continue

                if not dry_run and Team.objects.filter(name=name).exists():
                    errors.append(f"Row {i} ({name}): duplicate team")
                    continue

                if not dry_run:
                    try:
                        Team.objects.create(
                            name=name,
                            short_name=short_name,
                            owners=owners,
                            payment_info=int(payment) if payment.isdigit() else 0,
                        )
                        created += 1
                    except Exception as e:
                        errors.append(f"Row {i} ({name}): {e}")
                else:
                    created += 1

        return created, errors
