"""
Tests for JerseyService and ExtraJerseyMember.
"""
from django.test import TestCase
from auction.models import (
    Player, Team, Jersey, ExtraJerseyMember, TournamentConfig
)
from auction.services.jersey_service import JerseyService


def make_sold_player(name, team, price=1000):
    return Player.objects.create(
        name=name, role="AR", base_price=0,
        status=Player.STATUS_SOLD, team=team, sold_price=price
    )


class TestJerseyModel(TestCase):

    def setUp(self):
        self.team = Team.objects.create(name="Warriors", remaining_points=10000)
        self.player = make_sold_player("Rohit", self.team)

    def test_jersey_created_with_player(self):
        j = Jersey.objects.create(
            player=self.player,
            jersey_name="ROHIT",
            jersey_number=45,
            size_number=40,
            size_text="M",
            sponsor="Sachin Kolige Premier League",
        )
        self.assertEqual(j.jersey_name, "ROHIT")
        self.assertEqual(j.jersey_number, 45)
        self.assertEqual(j.size_text, "M")
        self.assertEqual(j.sponsor, "Sachin Kolige Premier League")

    def test_jersey_nullable_fields(self):
        j = Jersey.objects.create(player=self.player, jersey_name="TEST")
        self.assertIsNone(j.jersey_number)
        self.assertIsNone(j.size_number)
        self.assertEqual(j.size_text, "")
        self.assertEqual(j.sponsor, "")


class TestExtraJerseyMember(TestCase):

    def setUp(self):
        self.team = Team.objects.create(name="Alpha", remaining_points=10000)

    def test_create_team_extra(self):
        em = ExtraJerseyMember.objects.create(
            member_type=ExtraJerseyMember.TYPE_TEAM,
            team=self.team,
            name="Coach",
            jersey_name="COACH",
            jersey_number=99,
            size_number=42,
            size_text="L",
            sponsor="SponsABC",
        )
        em.refresh_from_db()
        self.assertEqual(em.jersey_name, "COACH")
        self.assertEqual(em.size_number, 42)
        self.assertEqual(em.size_text,   "L")
        self.assertEqual(em.sponsor,     "SponsABC")

    def test_create_organiser_extra(self):
        em = ExtraJerseyMember.objects.create(
            member_type=ExtraJerseyMember.TYPE_ORGANISER,
            name="Organiser1",
            jersey_number=0,
        )
        self.assertIsNone(em.team)
        self.assertEqual(em.member_type, ExtraJerseyMember.TYPE_ORGANISER)

    def test_multiple_extras_per_team(self):
        for i in range(5):
            ExtraJerseyMember.objects.create(
                member_type=ExtraJerseyMember.TYPE_TEAM,
                team=self.team, name=f"Member{i}",
            )
        count = ExtraJerseyMember.objects.filter(team=self.team).count()
        self.assertEqual(count, 5)


class TestJerseyServicePDF(TestCase):

    def setUp(self):
        TournamentConfig.objects.create(total_points=10000, bidding_slots=11)
        team = Team.objects.create(name="Lions", remaining_points=10000)
        for name in ["Bumrah", "Rohit", "Kohli"]:
            p = make_sold_player(name, team)
            Jersey.objects.create(
                player=p, jersey_name=name.upper(),
                jersey_number=p.serial_number,
                size_text="L", sponsor="Sachin Kolige Premier League",
            )

    def test_pdf_export_returns_bytes(self):
        pdf = JerseyService().export_pdf()
        self.assertIsInstance(pdf, (bytes, memoryview))
        self.assertGreater(len(pdf), 100)

    def test_pdf_starts_with_pdf_header(self):
        pdf = bytes(JerseyService().export_pdf())
        self.assertTrue(pdf.startswith(b"%PDF"), "PDF bytes must start with %PDF")

    def test_pdf_no_players_does_not_crash(self):
        Player.objects.all().update(status=Player.STATUS_AVAILABLE, team=None, sold_price=None)
        try:
            pdf = JerseyService().export_pdf()
            self.assertIsNotNone(pdf)
        except Exception as e:
            self.fail(f"export_pdf crashed with no players: {e}")


class TestJerseyViewSave(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_superuser("a", "", "pass")
        self.client.login(username="a", password="pass")
        team = Team.objects.create(name="Tigers", remaining_points=10000)
        self.player = make_sold_player("Jadeja", team)

    def test_save_jersey_via_ajax(self):
        resp = self.client.post("/jersey/save/", {
            "player_id":    self.player.serial_number,
            "jersey_name":  "JADEJA",
            "jersey_number": 8,
            "size_number":  40,
            "size_text":    "M",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        j = Jersey.objects.get(player=self.player)
        self.assertEqual(j.jersey_name,   "JADEJA")
        self.assertEqual(j.jersey_number, 8)

    def test_save_jersey_twice_no_duplicate(self):
        for _ in range(2):
            self.client.post("/jersey/save/", {
                "player_id":   self.player.serial_number,
                "jersey_name": "JADEJA",
            })
        self.assertEqual(Jersey.objects.filter(player=self.player).count(), 1)

    def test_size_sync_number_to_text(self):
        """Saving size_number should return mapped size_text."""
        from auction.models import TournamentConfig
        TournamentConfig.objects.create(
            total_points=10000, bidding_slots=11,
            size_mapping='{"40":"M","42":"L","44":"XL"}',
        )
        resp = self.client.post("/jersey/save/", {
            "player_id":   self.player.serial_number,
            "jersey_name": "TEST",
            "size_number": 40,
        })
        data = resp.json()
        self.assertEqual(data.get("size_text"), "M")
