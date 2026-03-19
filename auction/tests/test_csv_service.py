"""
Tests for CSVService — exhaustive coverage of all CSV combinations.

Player CSV  : validate_players_csv, import_players
Team CSV    : validate_teams_csv,   import_teams
Sample files: small / medium / large teams + players
"""
import csv
import os
import tempfile

from django.test import TestCase

from auction.models import Player, Team
from auction.services.csv_service import CSVService


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

PLAYER_FIELDS = ["name", "role", "phone", "place"]
TEAM_FIELDS   = ["name", "short_name", "owners", "payment_info"]

VALID_PLAYER  = {"name": "Rohit", "role": "BAT", "phone": "9876543210", "place": "Mumbai"}
VALID_TEAM    = {"name": "Warriors", "short_name": "WAR", "owners": "Owner A", "payment_info": "5000"}

ALL_ROLES = ["BAT", "BOWL", "AR", "PLY"]


def _csv(rows, fieldnames, directory, filename="test.csv"):
    path = os.path.join(directory, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    return path


def _raw(content, directory, filename="raw.csv"):
    """Write raw string content to a file."""
    path = os.path.join(directory, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _svc():
    return CSVService()


# ─────────────────────────────────────────────────────────────────────────────
# PLAYER  —  VALIDATION  (dry_run=True, no DB writes)
# ─────────────────────────────────────────────────────────────────────────────

class TestPlayerValidation(TestCase):
    """validate_players_csv: dry-run, no DB side effects."""

    # ── basic counts ─────────────────────────────────────────

    def test_single_valid_row_counts_one(self):
        with tempfile.TemporaryDirectory() as d:
            path = _csv([VALID_PLAYER], PLAYER_FIELDS, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 1)
        self.assertEqual(errors, [])

    def test_multiple_valid_rows(self):
        rows = [{**VALID_PLAYER, "name": f"P{i}", "phone": f"98765432{i:02d}"} for i in range(10, 20)]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, PLAYER_FIELDS, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 10)
        self.assertEqual(errors, [])

    def test_validate_does_not_touch_db(self):
        with tempfile.TemporaryDirectory() as d:
            path = _csv([VALID_PLAYER], PLAYER_FIELDS, d)
            _svc().validate_players_csv(path)
        self.assertEqual(Player.objects.count(), 0)

    def test_empty_file_only_header_returns_zero(self):
        with tempfile.TemporaryDirectory() as d:
            path = _csv([], PLAYER_FIELDS, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 0)
        self.assertEqual(errors, [])

    # ── role validation ───────────────────────────────────────

    def test_all_four_roles_valid(self):
        rows = [{**VALID_PLAYER, "name": r, "phone": f"9800000{i:03d}", "role": r}
                for i, r in enumerate(ALL_ROLES)]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, PLAYER_FIELDS, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 4)
        self.assertEqual(errors, [])

    def test_role_lowercase_accepted(self):
        """Service uppercases role before checking."""
        rows = [{**VALID_PLAYER, "name": r.lower(), "phone": f"9800000{i:03d}", "role": r.lower()}
                for i, r in enumerate(ALL_ROLES)]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, PLAYER_FIELDS, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 4)
        self.assertEqual(errors, [])

    def test_role_mixed_case_accepted(self):
        rows = [
            {**VALID_PLAYER, "name": "X1", "phone": "9800000001", "role": "Bat"},
            {**VALID_PLAYER, "name": "X2", "phone": "9800000002", "role": "bowl"},
            {**VALID_PLAYER, "name": "X3", "phone": "9800000003", "role": "Ar"},
            {**VALID_PLAYER, "name": "X4", "phone": "9800000004", "role": "Ply"},
        ]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, PLAYER_FIELDS, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 4)
        self.assertEqual(errors, [])

    def test_invalid_role_gives_error(self):
        for bad_role in ["WICKETKEEPER", "WK", "BATSMAN", "BOWLER", "ALL", "X", "123", ""]:
            with self.subTest(role=bad_role):
                row = {**VALID_PLAYER, "role": bad_role}
                with tempfile.TemporaryDirectory() as d:
                    path = _csv([row], PLAYER_FIELDS, d)
                    valid, errors = _svc().validate_players_csv(path)
                self.assertEqual(valid, 0, f"role={bad_role!r} should be invalid")
                self.assertTrue(len(errors) > 0)

    # ── phone validation ──────────────────────────────────────

    def test_phone_10_digits_valid(self):
        row = {**VALID_PLAYER, "phone": "9876543210"}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], PLAYER_FIELDS, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 1)

    def test_phone_11_digits_valid(self):
        row = {**VALID_PLAYER, "phone": "91987654321"}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], PLAYER_FIELDS, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 1)

    def test_phone_12_digits_valid(self):
        row = {**VALID_PLAYER, "phone": "919876543210"}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], PLAYER_FIELDS, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 1)

    def test_phone_with_plus_prefix_10_digits_valid(self):
        row = {**VALID_PLAYER, "phone": "+9876543210"}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], PLAYER_FIELDS, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 1)

    def test_phone_with_plus_prefix_12_digits_valid(self):
        row = {**VALID_PLAYER, "phone": "+919876543210"}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], PLAYER_FIELDS, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 1)

    def test_invalid_phones(self):
        bad_phones = [
            "123",          # too short (3)
            "123456789",    # 9 digits — too short
            "9876543210123", # 13 digits — too long
            "9876 543210",  # space inside
            "98765-43210",  # hyphen
            "phone",        # letters
            "98765abc210",  # alphanumeric
            "",             # empty
            "++9876543210", # double plus
        ]
        for phone in bad_phones:
            with self.subTest(phone=phone):
                row = {**VALID_PLAYER, "phone": phone}
                with tempfile.TemporaryDirectory() as d:
                    path = _csv([row], PLAYER_FIELDS, d)
                    valid, errors = _svc().validate_players_csv(path)
                self.assertEqual(valid, 0, f"phone={phone!r} should be invalid")
                self.assertTrue(len(errors) > 0)

    # ── name validation ───────────────────────────────────────

    def test_empty_name_gives_error(self):
        row = {**VALID_PLAYER, "name": ""}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], PLAYER_FIELDS, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 0)
        self.assertTrue(len(errors) > 0)

    def test_whitespace_only_name_gives_error(self):
        row = {**VALID_PLAYER, "name": "   "}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], PLAYER_FIELDS, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 0)
        self.assertTrue(len(errors) > 0)

    def test_name_with_spaces_valid(self):
        row = {**VALID_PLAYER, "name": "Virat Kohli"}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], PLAYER_FIELDS, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 1)

    # ── place validation ──────────────────────────────────────

    def test_empty_place_still_valid(self):
        """place is not required — empty should not cause error."""
        row = {**VALID_PLAYER, "place": ""}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], PLAYER_FIELDS, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 1)

    # ── header validation ─────────────────────────────────────

    def test_missing_name_column_raises(self):
        with tempfile.TemporaryDirectory() as d:
            path = _csv([{"role": "BAT", "phone": "9876543210", "place": "X"}],
                        ["role", "phone", "place"], d)
            with self.assertRaises(Exception):
                _svc().validate_players_csv(path)

    def test_missing_role_column_raises(self):
        with tempfile.TemporaryDirectory() as d:
            path = _csv([{"name": "A", "phone": "9876543210", "place": "X"}],
                        ["name", "phone", "place"], d)
            with self.assertRaises(Exception):
                _svc().validate_players_csv(path)

    def test_missing_phone_column_raises(self):
        with tempfile.TemporaryDirectory() as d:
            path = _csv([{"name": "A", "role": "BAT", "place": "X"}],
                        ["name", "role", "place"], d)
            with self.assertRaises(Exception):
                _svc().validate_players_csv(path)

    def test_completely_wrong_headers_raises(self):
        with tempfile.TemporaryDirectory() as d:
            path = _csv([{"a": "1", "b": "2"}], ["a", "b"], d)
            with self.assertRaises(Exception):
                _svc().validate_players_csv(path)

    def test_extra_columns_ignored(self):
        """Extra columns beyond required should not cause errors."""
        row = {**VALID_PLAYER, "extra_col": "ignored", "notes": "whatever"}
        fields = PLAYER_FIELDS + ["extra_col", "notes"]
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], fields, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 1)
        self.assertEqual(errors, [])

    # ── mixed valid/invalid ───────────────────────────────────

    def test_partial_valid_partial_invalid(self):
        rows = [
            VALID_PLAYER,
            {**VALID_PLAYER, "name": "Bad Role", "role": "GOALIE"},
            {**VALID_PLAYER, "name": "Bad Phone", "phone": "123"},
            {**VALID_PLAYER, "name": "Empty Name", "name": ""},
            {**VALID_PLAYER, "name": "Kohli", "phone": "9800000002"},
        ]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, PLAYER_FIELDS, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 2)   # VALID_PLAYER + Kohli
        self.assertEqual(len(errors), 3)

    def test_first_row_invalid_rest_valid(self):
        rows = [
            {**VALID_PLAYER, "role": "INVALID"},
            {**VALID_PLAYER, "name": "P2", "phone": "9800000002"},
            {**VALID_PLAYER, "name": "P3", "phone": "9800000003"},
        ]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, PLAYER_FIELDS, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 2)
        self.assertEqual(len(errors), 1)

    def test_all_rows_invalid(self):
        rows = [
            {**VALID_PLAYER, "role": "BAD"},
            {**VALID_PLAYER, "name": ""},
            {**VALID_PLAYER, "phone": "000"},
        ]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, PLAYER_FIELDS, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 0)
        self.assertEqual(len(errors), 3)


# ─────────────────────────────────────────────────────────────────────────────
# PLAYER  —  IMPORT
# ─────────────────────────────────────────────────────────────────────────────

class TestPlayerImport(TestCase):
    """import_players: actual DB writes."""

    def test_import_creates_player_in_db(self):
        with tempfile.TemporaryDirectory() as d:
            path = _csv([VALID_PLAYER], PLAYER_FIELDS, d)
            created, errors = _svc().import_players(path)
        self.assertEqual(created, 1)
        self.assertEqual(Player.objects.count(), 1)

    def test_imported_player_fields(self):
        with tempfile.TemporaryDirectory() as d:
            path = _csv([VALID_PLAYER], PLAYER_FIELDS, d)
            _svc().import_players(path)
        p = Player.objects.first()
        self.assertEqual(p.name, "Rohit")
        self.assertEqual(p.role, "BAT")
        self.assertEqual(p.phone, "9876543210")
        self.assertEqual(p.place, "Mumbai")
        self.assertEqual(p.base_price, 0)
        self.assertEqual(p.status, Player.STATUS_AVAILABLE)

    def test_import_all_four_roles(self):
        rows = [
            {**VALID_PLAYER, "name": r, "phone": f"9800000{i:03d}", "role": r}
            for i, r in enumerate(ALL_ROLES)
        ]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, PLAYER_FIELDS, d)
            created, errors = _svc().import_players(path)
        self.assertEqual(created, 4)
        for role in ALL_ROLES:
            self.assertTrue(Player.objects.filter(role=role).exists(), f"role {role} not found")

    def test_import_lowercase_role_stored_uppercase(self):
        row = {**VALID_PLAYER, "role": "bat"}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], PLAYER_FIELDS, d)
            _svc().import_players(path)
        self.assertEqual(Player.objects.first().role, "BAT")

    def test_duplicate_name_gives_error(self):
        Player.objects.create(name="Rohit", role="BAT", base_price=0)
        with tempfile.TemporaryDirectory() as d:
            path = _csv([VALID_PLAYER], PLAYER_FIELDS, d)
            created, errors = _svc().import_players(path)
        self.assertEqual(created, 0)
        self.assertEqual(Player.objects.count(), 1)  # existing not doubled
        self.assertTrue(len(errors) > 0)

    def test_duplicate_not_checked_in_validate(self):
        """Validate (dry-run) should NOT check for duplicate names."""
        Player.objects.create(name="Rohit", role="BAT", base_price=0)
        with tempfile.TemporaryDirectory() as d:
            path = _csv([VALID_PLAYER], PLAYER_FIELDS, d)
            valid, errors = _svc().validate_players_csv(path)
        self.assertEqual(valid, 1)  # dry-run: no dup check
        self.assertEqual(errors, [])

    def test_partial_valid_only_valid_imported(self):
        rows = [
            VALID_PLAYER,
            {**VALID_PLAYER, "name": "Bad", "role": "INVALID"},
        ]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, PLAYER_FIELDS, d)
            created, errors = _svc().import_players(path)
        self.assertEqual(created, 1)
        self.assertEqual(len(errors), 1)
        self.assertEqual(Player.objects.count(), 1)

    def test_invalid_row_does_not_block_valid_rows(self):
        rows = [
            {**VALID_PLAYER, "role": "BAD"},
            {**VALID_PLAYER, "name": "P2", "phone": "9800000002"},
            {**VALID_PLAYER, "name": "P3", "phone": "9800000003"},
        ]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, PLAYER_FIELDS, d)
            created, errors = _svc().import_players(path)
        self.assertEqual(created, 2)
        self.assertEqual(len(errors), 1)

    def test_import_50_players(self):
        rows = [
            {"name": f"Player{i}", "role": ALL_ROLES[i % 4],
             "phone": f"9800{i:06d}", "place": "Test"}
            for i in range(50)
        ]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, PLAYER_FIELDS, d)
            created, errors = _svc().import_players(path)
        self.assertEqual(created, 50)
        self.assertEqual(errors, [])
        self.assertEqual(Player.objects.count(), 50)

    def test_import_100_players(self):
        rows = [
            {"name": f"Player{i}", "role": "PLY",
             "phone": f"9800{i:06d}", "place": "Test"}
            for i in range(100)
        ]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, PLAYER_FIELDS, d)
            created, errors = _svc().import_players(path)
        self.assertEqual(created, 100)
        self.assertEqual(Player.objects.count(), 100)

    def test_second_import_with_duplicates(self):
        """Importing same file twice: second import should produce all duplicates."""
        rows = [
            {**VALID_PLAYER, "name": f"P{i}", "phone": f"9800000{i:03d}"}
            for i in range(5)
        ]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, PLAYER_FIELDS, d)
            c1, e1 = _svc().import_players(path)
            c2, e2 = _svc().import_players(path)
        self.assertEqual(c1, 5)
        self.assertEqual(c2, 0)
        self.assertEqual(len(e2), 5)

    def test_whitespace_trimmed_on_import(self):
        row = {"name": "  Rohit  ", "role": " BAT ", "phone": "9876543210", "place": " Mumbai "}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], PLAYER_FIELDS, d)
            created, errors = _svc().import_players(path)
        self.assertEqual(created, 1)
        p = Player.objects.first()
        self.assertEqual(p.name, "Rohit")
        self.assertEqual(p.role, "BAT")
        self.assertEqual(p.place, "Mumbai")

    def test_place_optional_import(self):
        row = {**VALID_PLAYER, "place": ""}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], PLAYER_FIELDS, d)
            created, errors = _svc().import_players(path)
        self.assertEqual(created, 1)
        self.assertEqual(Player.objects.first().place, "")

    def test_import_missing_required_header_raises(self):
        with tempfile.TemporaryDirectory() as d:
            path = _csv([{"name": "A", "role": "BAT", "place": "X"}],
                        ["name", "role", "place"], d)
            with self.assertRaises(Exception):
                _svc().import_players(path)


# ─────────────────────────────────────────────────────────────────────────────
# PLAYER PHONE — exhaustive boundary tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPlayerPhoneValidation(TestCase):
    r"""Boundary and combination tests for the phone regex ^\+?[0-9]{10,12}$"""

    def _valid(self, phone):
        with tempfile.TemporaryDirectory() as d:
            path = _csv([{**VALID_PLAYER, "phone": phone}], PLAYER_FIELDS, d)
            valid, _ = _svc().validate_players_csv(path)
        return valid == 1

    def test_exactly_10_digits(self):
        self.assertTrue(self._valid("9876543210"))

    def test_exactly_11_digits(self):
        self.assertTrue(self._valid("91987654321"))

    def test_exactly_12_digits(self):
        self.assertTrue(self._valid("919876543210"))

    def test_plus_10_digits(self):
        self.assertTrue(self._valid("+9876543210"))

    def test_plus_11_digits(self):
        self.assertTrue(self._valid("+91987654321"))

    def test_plus_12_digits(self):
        self.assertTrue(self._valid("+919876543210"))

    def test_9_digits_invalid(self):
        self.assertFalse(self._valid("987654321"))

    def test_13_digits_invalid(self):
        self.assertFalse(self._valid("9876543210123"))

    def test_space_in_middle_invalid(self):
        self.assertFalse(self._valid("98765 43210"))

    def test_dash_in_middle_invalid(self):
        self.assertFalse(self._valid("98765-43210"))

    def test_plus_in_middle_invalid(self):
        self.assertFalse(self._valid("987+6543210"))

    def test_double_plus_invalid(self):
        self.assertFalse(self._valid("++9876543210"))

    def test_letters_invalid(self):
        self.assertFalse(self._valid("987654321a"))

    def test_all_zeros_10_digits_valid(self):
        self.assertTrue(self._valid("0000000000"))

    def test_empty_string_invalid(self):
        self.assertFalse(self._valid(""))


# ─────────────────────────────────────────────────────────────────────────────
# TEAM  —  VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

class TestTeamValidation(TestCase):

    def test_single_valid_team(self):
        with tempfile.TemporaryDirectory() as d:
            path = _csv([VALID_TEAM], TEAM_FIELDS, d)
            valid, errors = _svc().validate_teams_csv(path)
        self.assertEqual(valid, 1)
        self.assertEqual(errors, [])

    def test_validate_does_not_write_db(self):
        with tempfile.TemporaryDirectory() as d:
            path = _csv([VALID_TEAM], TEAM_FIELDS, d)
            _svc().validate_teams_csv(path)
        self.assertEqual(Team.objects.count(), 0)

    def test_empty_file_only_header(self):
        with tempfile.TemporaryDirectory() as d:
            path = _csv([], TEAM_FIELDS, d)
            valid, errors = _svc().validate_teams_csv(path)
        self.assertEqual(valid, 0)
        self.assertEqual(errors, [])

    def test_empty_team_name_gives_error(self):
        row = {**VALID_TEAM, "name": ""}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], TEAM_FIELDS, d)
            valid, errors = _svc().validate_teams_csv(path)
        self.assertEqual(valid, 0)
        self.assertTrue(len(errors) > 0)

    def test_whitespace_only_name_gives_error(self):
        row = {**VALID_TEAM, "name": "   "}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], TEAM_FIELDS, d)
            valid, errors = _svc().validate_teams_csv(path)
        self.assertEqual(valid, 0)
        self.assertTrue(len(errors) > 0)

    def test_missing_name_column_raises(self):
        with tempfile.TemporaryDirectory() as d:
            path = _csv([{"short_name": "WAR"}], ["short_name"], d)
            with self.assertRaises(Exception):
                _svc().validate_teams_csv(path)

    def test_name_only_column_valid(self):
        """Only 'name' is required; other columns optional."""
        with tempfile.TemporaryDirectory() as d:
            path = _csv([{"name": "Solo Team"}], ["name"], d)
            valid, errors = _svc().validate_teams_csv(path)
        self.assertEqual(valid, 1)
        self.assertEqual(errors, [])

    def test_multiple_valid_teams(self):
        rows = [{"name": f"Team{i}", "short_name": f"T{i}", "owners": "O", "payment_info": "1000"}
                for i in range(8)]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, TEAM_FIELDS, d)
            valid, errors = _svc().validate_teams_csv(path)
        self.assertEqual(valid, 8)
        self.assertEqual(errors, [])

    def test_partial_invalid_teams(self):
        rows = [VALID_TEAM, {"name": "", "short_name": "", "owners": "", "payment_info": ""}]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, TEAM_FIELDS, d)
            valid, errors = _svc().validate_teams_csv(path)
        self.assertEqual(valid, 1)
        self.assertEqual(len(errors), 1)

    def test_extra_columns_ignored(self):
        row = {**VALID_TEAM, "notes": "extra", "irrelevant": "data"}
        fields = TEAM_FIELDS + ["notes", "irrelevant"]
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], fields, d)
            valid, errors = _svc().validate_teams_csv(path)
        self.assertEqual(valid, 1)


# ─────────────────────────────────────────────────────────────────────────────
# TEAM  —  IMPORT
# ─────────────────────────────────────────────────────────────────────────────

class TestTeamImport(TestCase):

    def test_import_creates_team(self):
        with tempfile.TemporaryDirectory() as d:
            path = _csv([VALID_TEAM], TEAM_FIELDS, d)
            created, errors = _svc().import_teams(path)
        self.assertEqual(created, 1)
        self.assertEqual(Team.objects.count(), 1)

    def test_imported_team_fields(self):
        with tempfile.TemporaryDirectory() as d:
            path = _csv([VALID_TEAM], TEAM_FIELDS, d)
            _svc().import_teams(path)
        t = Team.objects.first()
        self.assertEqual(t.name, "Warriors")
        self.assertEqual(t.short_name, "WAR")
        self.assertEqual(t.owners, "Owner A")
        self.assertEqual(t.payment_info, 5000)

    def test_payment_info_numeric_string(self):
        row = {**VALID_TEAM, "payment_info": "7500"}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], TEAM_FIELDS, d)
            _svc().import_teams(path)
        self.assertEqual(Team.objects.first().payment_info, 7500)

    def test_payment_info_non_numeric_defaults_to_zero(self):
        row = {**VALID_TEAM, "payment_info": "pending"}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], TEAM_FIELDS, d)
            _svc().import_teams(path)
        self.assertEqual(Team.objects.first().payment_info, 0)

    def test_payment_info_empty_defaults_to_zero(self):
        row = {**VALID_TEAM, "payment_info": ""}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], TEAM_FIELDS, d)
            _svc().import_teams(path)
        self.assertEqual(Team.objects.first().payment_info, 0)

    def test_short_name_optional_blank(self):
        row = {**VALID_TEAM, "short_name": ""}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], TEAM_FIELDS, d)
            created, errors = _svc().import_teams(path)
        self.assertEqual(created, 1)
        self.assertEqual(Team.objects.first().short_name, "")

    def test_owners_optional_blank(self):
        row = {**VALID_TEAM, "owners": ""}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], TEAM_FIELDS, d)
            created, errors = _svc().import_teams(path)
        self.assertEqual(created, 1)

    def test_duplicate_team_name_gives_error(self):
        Team.objects.create(name="Warriors")
        with tempfile.TemporaryDirectory() as d:
            path = _csv([VALID_TEAM], TEAM_FIELDS, d)
            created, errors = _svc().import_teams(path)
        self.assertEqual(created, 0)
        self.assertEqual(Team.objects.count(), 1)
        self.assertTrue(len(errors) > 0)

    def test_duplicate_not_checked_in_validate(self):
        Team.objects.create(name="Warriors")
        with tempfile.TemporaryDirectory() as d:
            path = _csv([VALID_TEAM], TEAM_FIELDS, d)
            valid, errors = _svc().validate_teams_csv(path)
        self.assertEqual(valid, 1)  # dry-run: no dup check

    def test_import_4_teams(self):
        rows = [{"name": f"Team{i}", "short_name": f"T{i}", "owners": "O", "payment_info": "5000"}
                for i in range(4)]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, TEAM_FIELDS, d)
            created, errors = _svc().import_teams(path)
        self.assertEqual(created, 4)
        self.assertEqual(Team.objects.count(), 4)

    def test_import_8_teams(self):
        rows = [{"name": f"Team{i}", "short_name": f"T{i}", "owners": "O", "payment_info": "5000"}
                for i in range(8)]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, TEAM_FIELDS, d)
            created, errors = _svc().import_teams(path)
        self.assertEqual(created, 8)

    def test_import_16_teams(self):
        rows = [{"name": f"Team{i}", "short_name": f"T{i}", "owners": "O", "payment_info": "5000"}
                for i in range(16)]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, TEAM_FIELDS, d)
            created, errors = _svc().import_teams(path)
        self.assertEqual(created, 16)

    def test_second_import_all_duplicates(self):
        rows = [{"name": f"Team{i}", "short_name": f"T{i}", "owners": "O", "payment_info": "100"}
                for i in range(4)]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, TEAM_FIELDS, d)
            c1, e1 = _svc().import_teams(path)
            c2, e2 = _svc().import_teams(path)
        self.assertEqual(c1, 4)
        self.assertEqual(c2, 0)
        self.assertEqual(len(e2), 4)

    def test_partial_valid_partial_duplicate(self):
        Team.objects.create(name="Warriors")
        rows = [
            VALID_TEAM,                              # duplicate
            {**VALID_TEAM, "name": "New Team"},      # fresh
        ]
        with tempfile.TemporaryDirectory() as d:
            path = _csv(rows, TEAM_FIELDS, d)
            created, errors = _svc().import_teams(path)
        self.assertEqual(created, 1)
        self.assertEqual(len(errors), 1)

    def test_whitespace_trimmed_team_name(self):
        row = {**VALID_TEAM, "name": "  Kolige Kings  "}
        with tempfile.TemporaryDirectory() as d:
            path = _csv([row], TEAM_FIELDS, d)
            _svc().import_teams(path)
        self.assertEqual(Team.objects.first().name, "Kolige Kings")

    def test_name_only_csv_creates_team(self):
        """Minimal valid team CSV — only name column."""
        with tempfile.TemporaryDirectory() as d:
            path = _csv([{"name": "Minimal FC"}], ["name"], d)
            created, errors = _svc().import_teams(path)
        self.assertEqual(created, 1)


# ─────────────────────────────────────────────────────────────────────────────
# COMBINED  —  teams then players (realistic workflow)
# ─────────────────────────────────────────────────────────────────────────────

class TestCombinedWorkflow(TestCase):
    """Import teams first, then players — mirrors the actual UI workflow."""

    def _make_teams(self, n, directory):
        rows = [{"name": f"Team{i}", "short_name": f"T{i}", "owners": "O", "payment_info": "10000"}
                for i in range(n)]
        path = _csv(rows, TEAM_FIELDS, directory, "teams.csv")
        return _svc().import_teams(path)

    def _make_players(self, n_per_role, directory):
        rows = []
        idx = 0
        for role in ALL_ROLES:
            for j in range(n_per_role):
                rows.append({
                    "name":  f"{role}_Player_{j}",
                    "role":  role,
                    "phone": f"9800{idx:06d}",
                    "place": "Test",
                })
                idx += 1
        path = _csv(rows, PLAYER_FIELDS, directory, "players.csv")
        return _svc().import_players(path)

    def test_4_teams_20_players(self):
        with tempfile.TemporaryDirectory() as d:
            tc, te = self._make_teams(4, d)
            pc, pe = self._make_players(5, d)   # 4 roles × 5 = 20
        self.assertEqual(tc, 4)
        self.assertEqual(pc, 20)
        self.assertEqual(Team.objects.count(), 4)
        self.assertEqual(Player.objects.count(), 20)

    def test_8_teams_40_players(self):
        with tempfile.TemporaryDirectory() as d:
            tc, te = self._make_teams(8, d)
            pc, pe = self._make_players(10, d)  # 4 roles × 10 = 40
        self.assertEqual(tc, 8)
        self.assertEqual(pc, 40)

    def test_16_teams_96_players(self):
        with tempfile.TemporaryDirectory() as d:
            tc, te = self._make_teams(16, d)
            pc, pe = self._make_players(24, d)  # 4 roles × 24 = 96
        self.assertEqual(tc, 16)
        self.assertEqual(pc, 96)

    def test_player_role_distribution_correct(self):
        with tempfile.TemporaryDirectory() as d:
            self._make_teams(4, d)
            self._make_players(3, d)   # 4 × 3 = 12
        for role in ALL_ROLES:
            self.assertEqual(Player.objects.filter(role=role).count(), 3)

    def test_all_players_start_available(self):
        with tempfile.TemporaryDirectory() as d:
            self._make_teams(4, d)
            self._make_players(5, d)
        self.assertEqual(
            Player.objects.filter(status=Player.STATUS_AVAILABLE).count(), 20
        )

    def test_reimport_same_players_all_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            c1, e1 = self._make_players(3, d)
            c2, e2 = self._make_players(3, d)
        self.assertEqual(c1, 12)
        self.assertEqual(c2, 0)
        self.assertEqual(len(e2), 12)

    def test_teams_import_no_effect_on_players(self):
        with tempfile.TemporaryDirectory() as d:
            self._make_teams(4, d)
        self.assertEqual(Player.objects.count(), 0)

    def test_players_import_no_effect_on_teams(self):
        with tempfile.TemporaryDirectory() as d:
            self._make_players(5, d)
        self.assertEqual(Team.objects.count(), 0)


# ─────────────────────────────────────────────────────────────────────────────
# SAMPLE DATA FILES  —  bundled CSVs
# ─────────────────────────────────────────────────────────────────────────────

class TestSampleDataFiles(TestCase):
    """Verify the bundled sample CSV files parse cleanly with exact counts."""

    def setUp(self):
        from django.conf import settings
        self.sample_dir = os.path.join(settings.BASE_DIR, "sample_data")

    def _path(self, filename):
        p = os.path.join(self.sample_dir, filename)
        if not os.path.exists(p):
            self.skipTest(f"Sample file not found: {filename}")
        return p

    # ── validate counts ───────────────────────────────────────

    def test_small_players_validate_count(self):
        valid, errors = _svc().validate_players_csv(self._path("small_players.csv"))
        self.assertEqual(valid, 20)
        self.assertEqual(errors, [])

    def test_small_teams_validate_count(self):
        valid, errors = _svc().validate_teams_csv(self._path("small_teams.csv"))
        self.assertEqual(valid, 4)
        self.assertEqual(errors, [])

    def test_medium_players_validate_count(self):
        valid, errors = _svc().validate_players_csv(self._path("medium_players.csv"))
        self.assertEqual(valid, 43)
        self.assertEqual(errors, [])

    def test_medium_teams_validate_count(self):
        valid, errors = _svc().validate_teams_csv(self._path("medium_teams.csv"))
        self.assertEqual(valid, 8)
        self.assertEqual(errors, [])

    def test_large_players_validate_count(self):
        valid, errors = _svc().validate_players_csv(self._path("large_players.csv"))
        self.assertEqual(valid, 101)
        self.assertEqual(errors, [])

    def test_large_teams_validate_count(self):
        valid, errors = _svc().validate_teams_csv(self._path("large_teams.csv"))
        self.assertEqual(valid, 16)
        self.assertEqual(errors, [])

    # ── validate has no errors ────────────────────────────────

    def test_small_players_no_errors(self):
        _, errors = _svc().validate_players_csv(self._path("small_players.csv"))
        self.assertEqual(errors, [], f"Unexpected errors: {errors}")

    def test_small_teams_no_errors(self):
        _, errors = _svc().validate_teams_csv(self._path("small_teams.csv"))
        self.assertEqual(errors, [], f"Unexpected errors: {errors}")

    def test_medium_players_no_errors(self):
        _, errors = _svc().validate_players_csv(self._path("medium_players.csv"))
        self.assertEqual(errors, [], f"Unexpected errors: {errors}")

    def test_medium_teams_no_errors(self):
        _, errors = _svc().validate_teams_csv(self._path("medium_teams.csv"))
        self.assertEqual(errors, [], f"Unexpected errors: {errors}")

    def test_large_players_no_errors(self):
        _, errors = _svc().validate_players_csv(self._path("large_players.csv"))
        self.assertEqual(errors, [], f"Unexpected errors: {errors}")

    def test_large_teams_no_errors(self):
        _, errors = _svc().validate_teams_csv(self._path("large_teams.csv"))
        self.assertEqual(errors, [], f"Unexpected errors: {errors}")

    # ── import counts match validate counts ───────────────────

    def test_small_players_import_count(self):
        created, errors = _svc().import_players(self._path("small_players.csv"))
        self.assertEqual(created, 20)
        self.assertEqual(errors, [])

    def test_small_teams_import_count(self):
        created, errors = _svc().import_teams(self._path("small_teams.csv"))
        self.assertEqual(created, 4)
        self.assertEqual(errors, [])

    def test_medium_players_import_count(self):
        created, errors = _svc().import_players(self._path("medium_players.csv"))
        self.assertEqual(created, 43)
        self.assertEqual(errors, [])

    def test_medium_teams_import_count(self):
        created, errors = _svc().import_teams(self._path("medium_teams.csv"))
        self.assertEqual(created, 8)
        self.assertEqual(errors, [])

    def test_large_players_import_count(self):
        created, errors = _svc().import_players(self._path("large_players.csv"))
        self.assertEqual(created, 101)
        self.assertEqual(errors, [])

    def test_large_teams_import_count(self):
        created, errors = _svc().import_teams(self._path("large_teams.csv"))
        self.assertEqual(created, 16)
        self.assertEqual(errors, [])

    # ── import creates exact DB rows ──────────────────────────

    def test_small_players_creates_db_rows(self):
        _svc().import_players(self._path("small_players.csv"))
        self.assertEqual(Player.objects.count(), 20)

    def test_small_teams_creates_db_rows(self):
        _svc().import_teams(self._path("small_teams.csv"))
        self.assertEqual(Team.objects.count(), 4)

    def test_large_players_creates_db_rows(self):
        _svc().import_players(self._path("large_players.csv"))
        self.assertEqual(Player.objects.count(), 101)

    def test_large_teams_creates_db_rows(self):
        _svc().import_teams(self._path("large_teams.csv"))
        self.assertEqual(Team.objects.count(), 16)

    # ── role distribution in sample files ────────────────────

    def test_small_players_role_distribution(self):
        """small: 4 AR + 4 BAT + 4 BOWL + 8 PLY = 20"""
        _svc().import_players(self._path("small_players.csv"))
        self.assertEqual(Player.objects.filter(role="AR").count(),   4)
        self.assertEqual(Player.objects.filter(role="BAT").count(),  4)
        self.assertEqual(Player.objects.filter(role="BOWL").count(), 4)
        self.assertEqual(Player.objects.filter(role="PLY").count(),  8)

    def test_medium_players_role_distribution(self):
        """medium: 8 AR + 8 BAT + 8 BOWL + 19 PLY = 43"""
        _svc().import_players(self._path("medium_players.csv"))
        self.assertEqual(Player.objects.filter(role="AR").count(),   8)
        self.assertEqual(Player.objects.filter(role="BAT").count(),  8)
        self.assertEqual(Player.objects.filter(role="BOWL").count(), 8)
        self.assertEqual(Player.objects.filter(role="PLY").count(),  19)

    def test_large_players_role_distribution(self):
        """large: 16 AR + 16 BAT + 16 BOWL + 53 PLY = 101"""
        _svc().import_players(self._path("large_players.csv"))
        self.assertEqual(Player.objects.filter(role="AR").count(),   16)
        self.assertEqual(Player.objects.filter(role="BAT").count(),  16)
        self.assertEqual(Player.objects.filter(role="BOWL").count(), 16)
        self.assertEqual(Player.objects.filter(role="PLY").count(),  53)

    # ── all imported players start AVAILABLE ─────────────────

    def test_small_players_all_available(self):
        _svc().import_players(self._path("small_players.csv"))
        self.assertEqual(
            Player.objects.filter(status=Player.STATUS_AVAILABLE).count(), 20
        )

    def test_large_players_all_available(self):
        _svc().import_players(self._path("large_players.csv"))
        self.assertEqual(
            Player.objects.filter(status=Player.STATUS_AVAILABLE).count(), 101
        )

    # ── reimport same file → all duplicates ──────────────────

    def test_small_players_reimport_all_duplicates(self):
        p = self._path("small_players.csv")
        c1, _ = _svc().import_players(p)
        c2, e2 = _svc().import_players(p)
        self.assertEqual(c1, 20)
        self.assertEqual(c2, 0)
        self.assertEqual(len(e2), 20)

    def test_small_teams_reimport_all_duplicates(self):
        p = self._path("small_teams.csv")
        c1, _ = _svc().import_teams(p)
        c2, e2 = _svc().import_teams(p)
        self.assertEqual(c1, 4)
        self.assertEqual(c2, 0)
        self.assertEqual(len(e2), 4)
