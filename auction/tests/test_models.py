from django.test import TestCase
from auction.models import Player, Team, TournamentConfig


class TeamShortNameTest(TestCase):

    def test_multi_word(self):
        t = Team(name="Mumbai Indians")
        self.assertEqual(t.get_short(), "MI")

    def test_single_word(self):
        t = Team(name="Bangalore")
        self.assertEqual(t.get_short(), "BAN")

    def test_explicit_short_name(self):
        t = Team(name="Mumbai Indians", short_name="MI")
        self.assertEqual(t.get_short(), "MI")

    def test_explicit_short_name_lowercased(self):
        t = Team(name="Mumbai Indians", short_name="mi")
        self.assertEqual(t.get_short(), "MI")


class PlayerSaveTest(TestCase):

    def setUp(self):
        self.config = TournamentConfig.objects.create(total_points=10000)
        self.team_a = Team.objects.create(name="Team A", remaining_points=10000)
        self.team_b = Team.objects.create(name="Team B", remaining_points=10000)

    def test_sell_deducts_from_team(self):
        p = Player.objects.create(name="Ramesh", role="AR", base_price=1000,
                                   status=Player.STATUS_SOLD, team=self.team_a, sold_price=1500)
        self.team_a.refresh_from_db()
        self.assertEqual(self.team_a.remaining_points, 8500)

    def test_unsell_refunds_team(self):
        p = Player.objects.create(name="Suresh", role="BAT", base_price=400,
                                   status=Player.STATUS_SOLD, team=self.team_a, sold_price=800)
        self.team_a.refresh_from_db()
        self.assertEqual(self.team_a.remaining_points, 9200)
        p.status = Player.STATUS_AVAILABLE
        p.team   = None
        p.sold_price = None
        p.save()
        self.team_a.refresh_from_db()
        self.assertEqual(self.team_a.remaining_points, 10000)

    def test_edit_price_no_double_deduct(self):
        p = Player.objects.create(name="Ganesh", role="BAT", base_price=400,
                                   status=Player.STATUS_SOLD, team=self.team_a, sold_price=600)
        self.team_a.refresh_from_db()
        self.assertEqual(self.team_a.remaining_points, 9400)
        # Edit price to 700
        p.sold_price = 700
        p.save()
        self.team_a.refresh_from_db()
        self.assertEqual(self.team_a.remaining_points, 9300)  # not 9400-700=8700

    def test_switch_team_correct_points(self):
        p = Player.objects.create(name="Mahesh", role="BOWL", base_price=400,
                                   status=Player.STATUS_SOLD, team=self.team_a, sold_price=500)
        self.team_a.refresh_from_db()
        self.assertEqual(self.team_a.remaining_points, 9500)
        p.team = self.team_b
        p.save()
        self.team_a.refresh_from_db()
        self.team_b.refresh_from_db()
        self.assertEqual(self.team_a.remaining_points, 10000)  # refunded
        self.assertEqual(self.team_b.remaining_points, 9500)   # deducted
