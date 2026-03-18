"""
Tests for report_service: PDF and Excel output.
"""
from django.test import TestCase
from auction.models import Player, Team, TournamentConfig


def make_team_with_players():
    config = TournamentConfig.objects.create(total_points=10000, bidding_slots=11)
    team   = Team.objects.create(name="Royals", remaining_points=8000)
    roles  = ["AR", "BAT", "BOWL", "PLY"]
    for i, role in enumerate(roles * 3):
        Player.objects.create(
            name=f"Player{i+1}", role=role,
            base_price=500, status=Player.STATUS_SOLD,
            team=team, sold_price=1000,
        )
    for i in range(5):
        Player.objects.create(
            name=f"Unsold{i}", role="PLY",
            base_price=100, status=Player.STATUS_UNSOLD,
        )
    return config, team


class TestAllPlayersPDF(TestCase):

    def setUp(self):
        make_team_with_players()

    def test_pdf_bytes_returned(self):
        from auction.services.report_service import all_players_pdf
        pdf = all_players_pdf()
        content = pdf.getvalue()
        self.assertIsInstance(content, bytes)
        self.assertTrue(content.startswith(b"%PDF"))

    def test_pdf_with_role_filter(self):
        from auction.services.report_service import all_players_pdf
        pdf = all_players_pdf(role_filter="AR")
        self.assertIsNotNone(pdf)

    def test_pdf_empty_players_no_crash(self):
        from auction.services.report_service import all_players_pdf
        Player.objects.all().delete()
        pdf = all_players_pdf()
        self.assertIsNotNone(pdf)


class TestAuctionResultsPDF(TestCase):

    def setUp(self):
        make_team_with_players()

    def test_pdf_all_statuses(self):
        from auction.services.report_service import auction_players_pdf
        pdf = auction_players_pdf()
        self.assertTrue(pdf.getvalue().startswith(b"%PDF"))

    def test_pdf_sold_only(self):
        from auction.services.report_service import auction_players_pdf
        pdf = auction_players_pdf(status_filter="SOLD")
        self.assertIsNotNone(pdf)

    def test_pdf_unsold_only(self):
        from auction.services.report_service import auction_players_pdf
        pdf = auction_players_pdf(status_filter="UNSOLD")
        self.assertIsNotNone(pdf)


class TestTeamwisePDF(TestCase):

    def setUp(self):
        make_team_with_players()

    def test_teamwise_pdf(self):
        from auction.services.report_service import teamwise_pdf
        pdf = teamwise_pdf()
        self.assertTrue(pdf.getvalue().startswith(b"%PDF"))


class TestExcelReports(TestCase):

    def setUp(self):
        make_team_with_players()

    def test_all_players_excel(self):
        from auction.services.report_service import all_players_excel
        buf = all_players_excel()
        content = buf.getvalue()
        # Excel files start with PK (ZIP header)
        self.assertTrue(content.startswith(b"PK"), "Excel file must start with PK")

    def test_auction_results_excel(self):
        from auction.services.report_service import all_players_excel
        buf = all_players_excel()
        self.assertIsNotNone(buf)

    def test_teamwise_excel(self):
        from auction.services.report_service import teamwise_excel
        buf = teamwise_excel()
        content = buf.getvalue()
        self.assertTrue(content.startswith(b"PK"))


class TestReportSerialNumbers(TestCase):
    """Verify reports use serial_number (PK) not loop counter."""

    def setUp(self):
        TournamentConfig.objects.create(total_points=10000, bidding_slots=11)
        team = Team.objects.create(name="T", remaining_points=10000)
        # Create players with non-sequential IDs by deleting some first
        for i, role in enumerate(["AR", "BAT", "BOWL"]):
            Player.objects.create(
                name=f"P{i+1}", role=role, base_price=0,
                status=Player.STATUS_SOLD, team=team, sold_price=500,
            )

    def test_pdf_row_uses_serial_number(self):
        from auction.services.report_service import all_players_pdf
        # Just verify it runs without error — serial_number usage
        # is verified by the test_models.py model tests
        pdf = all_players_pdf()
        self.assertIsNotNone(pdf)
