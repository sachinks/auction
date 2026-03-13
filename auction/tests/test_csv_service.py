import os, tempfile, csv
from django.test import TestCase
from auction.models import Player, Team
from auction.services.csv_service import CSVService


def make_csv(rows, fieldnames, tmpdir):
    path = os.path.join(tmpdir, "test.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    return path


class PlayerCSVTest(TestCase):

    def test_validate_does_not_create(self):
        svc = CSVService()
        with tempfile.TemporaryDirectory() as d:
            path = make_csv(
                [{"name": "Raj", "role": "AR", "phone": "9876543210", "place": "MNG"}],
                ["name", "role", "phone", "place"], d
            )
            valid, errors = svc.validate_players_csv(path)
        self.assertEqual(valid, 1)
        self.assertEqual(len(errors), 0)
        self.assertEqual(Player.objects.count(), 0)  # no DB write

    def test_import_creates_players(self):
        svc = CSVService()
        with tempfile.TemporaryDirectory() as d:
            path = make_csv(
                [{"name": "Kumar", "role": "BAT", "phone": "9876543211", "place": "BLR"}],
                ["name", "role", "phone", "place"], d
            )
            created, errors = svc.import_players(path)
        self.assertEqual(created, 1)
        self.assertEqual(Player.objects.count(), 1)

    def test_invalid_role_gives_error(self):
        svc = CSVService()
        with tempfile.TemporaryDirectory() as d:
            path = make_csv(
                [{"name": "Xyz", "role": "INVALID", "phone": "9876543212", "place": "X"}],
                ["name", "role", "phone", "place"], d
            )
            valid, errors = svc.validate_players_csv(path)
        self.assertEqual(valid, 0)
        self.assertTrue(len(errors) > 0)


class TeamCSVTest(TestCase):

    def test_import_teams(self):
        svc = CSVService()
        with tempfile.TemporaryDirectory() as d:
            path = make_csv(
                [{"name": "Warriors", "short_name": "WAR", "owners": "A", "payment_info": "5000"}],
                ["name", "short_name", "owners", "payment_info"], d
            )
            created, errors = svc.import_teams(path)
        self.assertEqual(created, 1)
        self.assertEqual(Team.objects.first().short_name, "WAR")

    def test_validate_teams_no_write(self):
        svc = CSVService()
        with tempfile.TemporaryDirectory() as d:
            path = make_csv(
                [{"name": "Lions", "short_name": "LIO"}],
                ["name", "short_name"], d
            )
            valid, errors = svc.validate_teams_csv(path)
        self.assertEqual(valid, 1)
        self.assertEqual(Team.objects.count(), 0)
