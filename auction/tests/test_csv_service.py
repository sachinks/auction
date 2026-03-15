"""
Tests for CSVService: player + team import/validate.
"""
import csv, os, tempfile
from django.test import TestCase
from auction.models import Player, Team
from auction.services.csv_service import CSVService


# ── Helper ──────────────────────────────────────────────────

def write_csv(rows, fieldnames, directory):
    path = os.path.join(directory, "test.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    return path


PLAYER_FIELDS = ["name", "role", "phone", "place"]
TEAM_FIELDS   = ["name", "short_name", "owners", "payment_info"]

VALID_PLAYER  = {"name": "Rohit", "role": "BAT", "phone": "9876543210", "place": "MUM"}
VALID_TEAM    = {"name": "Warriors", "short_name": "WAR", "owners": "Owner A", "payment_info": "5000"}


# ── Player CSV ───────────────────────────────────────────────

class TestPlayerCSVValidate(TestCase):

    def test_validate_counts_valid_rows(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_csv([VALID_PLAYER], PLAYER_FIELDS, d)
            valid, errors = CSVService().validate_players_csv(path)
        self.assertEqual(valid, 1)
        self.assertEqual(len(errors), 0)

    def test_validate_does_not_write_db(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_csv([VALID_PLAYER], PLAYER_FIELDS, d)
            CSVService().validate_players_csv(path)
        self.assertEqual(Player.objects.count(), 0)

    def test_invalid_role_gives_error(self):
        row = {**VALID_PLAYER, "role": "WICKETKEEPER"}
        with tempfile.TemporaryDirectory() as d:
            path = write_csv([row], PLAYER_FIELDS, d)
            valid, errors = CSVService().validate_players_csv(path)
        self.assertEqual(valid, 0)
        self.assertTrue(len(errors) > 0)

    def test_invalid_phone_gives_error(self):
        row = {**VALID_PLAYER, "phone": "123"}
        with tempfile.TemporaryDirectory() as d:
            path = write_csv([row], PLAYER_FIELDS, d)
            valid, errors = CSVService().validate_players_csv(path)
        self.assertEqual(valid, 0)
        self.assertTrue(len(errors) > 0)

    def test_all_four_roles_accepted(self):
        rows = [
            {**VALID_PLAYER, "name": f"P{r}", "role": r}
            for r in ["BAT", "BOWL", "AR", "PLY"]
        ]
        with tempfile.TemporaryDirectory() as d:
            path = write_csv(rows, PLAYER_FIELDS, d)
            valid, errors = CSVService().validate_players_csv(path)
        self.assertEqual(valid, 4)
        self.assertEqual(len(errors), 0)

    def test_missing_header_raises(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_csv([{"a": "b"}], ["a"], d)
            with self.assertRaises(Exception):
                CSVService().validate_players_csv(path)

    def test_empty_name_gives_error(self):
        row = {**VALID_PLAYER, "name": ""}
        with tempfile.TemporaryDirectory() as d:
            path = write_csv([row], PLAYER_FIELDS, d)
            valid, errors = CSVService().validate_players_csv(path)
        self.assertEqual(valid, 0)


class TestPlayerCSVImport(TestCase):

    def test_import_creates_player(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_csv([VALID_PLAYER], PLAYER_FIELDS, d)
            created, errors = CSVService().import_players(path)
        self.assertEqual(created, 1)
        self.assertEqual(Player.objects.count(), 1)

    def test_import_sets_correct_fields(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_csv([VALID_PLAYER], PLAYER_FIELDS, d)
            CSVService().import_players(path)
        p = Player.objects.first()
        self.assertEqual(p.name, "Rohit")
        self.assertEqual(p.role, "BAT")
        self.assertEqual(p.place, "MUM")

    def test_duplicate_gives_error_not_crash(self):
        Player.objects.create(name="Rohit", role="BAT", base_price=0)
        with tempfile.TemporaryDirectory() as d:
            path = write_csv([VALID_PLAYER], PLAYER_FIELDS, d)
            created, errors = CSVService().import_players(path)
        self.assertEqual(created, 0)
        self.assertTrue(len(errors) > 0)

    def test_partial_valid_partial_invalid(self):
        rows = [
            VALID_PLAYER,
            {**VALID_PLAYER, "name": "Kohli", "role": "INVALID"},
        ]
        with tempfile.TemporaryDirectory() as d:
            path = write_csv(rows, PLAYER_FIELDS, d)
            created, errors = CSVService().import_players(path)
        self.assertEqual(created, 1)
        self.assertEqual(len(errors), 1)

    def test_import_100_players(self):
        rows = [
            {"name": f"Player{i}", "role": "PLY", "phone": f"98765432{i:02d}", "place": "X"}
            for i in range(10, 110)
        ]
        with tempfile.TemporaryDirectory() as d:
            path = write_csv(rows, PLAYER_FIELDS, d)
            created, errors = CSVService().import_players(path)
        self.assertEqual(created, 100)
        self.assertEqual(len(errors), 0)


# ── Team CSV ─────────────────────────────────────────────────

class TestTeamCSV(TestCase):

    def test_validate_does_not_write_db(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_csv([VALID_TEAM], TEAM_FIELDS, d)
            CSVService().validate_teams_csv(path)
        self.assertEqual(Team.objects.count(), 0)

    def test_import_creates_team(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_csv([VALID_TEAM], TEAM_FIELDS, d)
            created, errors = CSVService().import_teams(path)
        self.assertEqual(created, 1)
        self.assertEqual(Team.objects.count(), 1)

    def test_import_sets_short_name(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_csv([VALID_TEAM], TEAM_FIELDS, d)
            CSVService().import_teams(path)
        self.assertEqual(Team.objects.first().short_name, "WAR")

    def test_duplicate_team_gives_error(self):
        Team.objects.create(name="Warriors")
        with tempfile.TemporaryDirectory() as d:
            path = write_csv([VALID_TEAM], TEAM_FIELDS, d)
            created, errors = CSVService().import_teams(path)
        self.assertEqual(created, 0)
        self.assertTrue(len(errors) > 0)

    def test_import_16_teams(self):
        rows = [
            {"name": f"Team {i}", "short_name": f"T{i}", "owners": "O", "payment_info": "5000"}
            for i in range(1, 17)
        ]
        with tempfile.TemporaryDirectory() as d:
            path = write_csv(rows, TEAM_FIELDS, d)
            created, errors = CSVService().import_teams(path)
        self.assertEqual(created, 16)
        self.assertEqual(len(errors), 0)


# ── Sample data files ─────────────────────────────────────────

class TestSampleDataFiles(TestCase):
    """Verify the bundled sample CSV files are valid."""

    SAMPLE_DIR = None

    def setUp(self):
        from django.conf import settings
        self.sample_dir = os.path.join(settings.BASE_DIR, "sample_data")

    def _validate_file(self, filename, file_type):
        path = os.path.join(self.sample_dir, filename)
        if not os.path.exists(path):
            self.skipTest(f"Sample file not found: {filename}")
        svc = CSVService()
        if file_type == "players":
            valid, errors = svc.validate_players_csv(path)
        else:
            valid, errors = svc.validate_teams_csv(path)
        return valid, errors

    def test_short_players_valid(self):
        valid, errors = self._validate_file("short_players.csv", "players")
        self.assertGreater(valid, 0)
        self.assertEqual(len(errors), 0)

    def test_short_teams_valid(self):
        valid, errors = self._validate_file("short_teams.csv", "teams")
        self.assertGreater(valid, 0)
        self.assertEqual(len(errors), 0)

    def test_long_players_valid(self):
        valid, errors = self._validate_file("long_players.csv", "players")
        self.assertGreater(valid, 100, "Expected >100 players in long_players.csv")
        self.assertEqual(len(errors), 0)

    def test_long_teams_valid(self):
        valid, errors = self._validate_file("long_teams.csv", "teams")
        self.assertGreaterEqual(valid, 16, "Expected 16 teams in long_teams.csv")
        self.assertEqual(len(errors), 0)
