"""
csv_service.py
──────────────
Player and Team CSV import with validate-only (dry-run) mode.
"""
import csv
import re
import logging
import traceback

from auction.models import Player, Team

logger = logging.getLogger("system")


class CSVService:

    REQUIRED_COLUMNS = ["name", "place", "role", "phone"]
    VALID_ROLES      = ["BAT", "BOWL", "AR", "PLY"]

    # Placeholder values that mean "no phone" — normalized to empty string
    PHONE_PLACEHOLDERS = re.compile(r"^[-–—]+$|^0+$|^(n/?a|none|nil|na)$", re.IGNORECASE)

    def normalize_phone(self, phone):
        """Return empty string for placeholder values, otherwise return phone as-is."""
        if not phone or self.PHONE_PLACEHOLDERS.match(phone):
            return ""
        return phone

    def valid_phone(self, phone):
        """phone must already be normalized before calling this."""
        if not phone:
            return True
        return re.match(r"^\+?[0-9]{10,12}$", phone)

    # ─────────────────────────────────────────────
    # Players CSV
    # ─────────────────────────────────────────────

    def validate_players_csv(self, filepath):
        logger.info(f"validate_players_csv: dry-run on {filepath}")
        return self._process_players_csv(filepath, dry_run=True)

    def import_players(self, filepath):
        logger.info(f"import_players: importing from {filepath}")
        return self._process_players_csv(filepath, dry_run=False)

    def _process_players_csv(self, filepath, dry_run=False):
        created = 0
        errors  = []
        mode    = "DRY-RUN" if dry_run else "IMPORT"

        try:
            with open(filepath, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                if not reader.fieldnames or not all(
                    c in reader.fieldnames for c in self.REQUIRED_COLUMNS
                ):
                    msg = "Invalid CSV header. Required: name, place, role, phone"
                    logger.warning(f"_process_players_csv: {msg}")
                    raise ValueError(msg)

                seen = set()
                for i, row in enumerate(reader, start=2):
                    name  = row.get("name", "").strip()
                    role  = row.get("role", "").strip().upper()
                    phone = self.normalize_phone(row.get("phone", "").strip())
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
                    if (name, place) in seen or Player.objects.filter(name=name, place=place).exists():
                        errors.append(f"Row {i}: duplicate player '{name}' from '{place}'")
                        continue
                    seen.add((name, place))

                    if not dry_run:
                        try:
                            Player.objects.create(
                                name=name, role=role, phone=phone,
                                place=place, base_price=0, status="AVAILABLE"
                            )
                            created += 1
                        except Exception as e:
                            errors.append(f"Row {i} ({name}): {e}")
                            logger.error(f"Row {i} ({name}): DB error — {e}")
                    else:
                        created += 1

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"_process_players_csv error: {e}\n{traceback.format_exc()}")
            raise

        logger.info(f"_process_players_csv {mode}: {created} valid, {len(errors)} errors")
        return created, errors

    # ─────────────────────────────────────────────
    # Teams CSV
    # ─────────────────────────────────────────────

    def validate_teams_csv(self, filepath):
        logger.info(f"validate_teams_csv: dry-run on {filepath}")
        return self._process_teams_csv(filepath, dry_run=True)

    def import_teams(self, filepath):
        logger.info(f"import_teams: importing from {filepath}")
        return self._process_teams_csv(filepath, dry_run=False)

    def _process_teams_csv(self, filepath, dry_run=False):
        created = 0
        errors  = []
        mode    = "DRY-RUN" if dry_run else "IMPORT"

        try:
            with open(filepath, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                if not reader.fieldnames or "name" not in reader.fieldnames:
                    msg = "Invalid CSV header. Required column: name"
                    logger.warning(f"_process_teams_csv: {msg}")
                    raise ValueError(msg)

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
                            logger.error(f"Row {i} ({name}): DB error — {e}")
                    else:
                        created += 1

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"_process_teams_csv error: {e}\n{traceback.format_exc()}")
            raise

        logger.info(f"_process_teams_csv {mode}: {created} valid, {len(errors)} errors")
        return created, errors
