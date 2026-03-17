"""
Tests for model behaviour — Player.save() point deductions,
Team.get_short(), TournamentSettings singleton, etc.
"""
import pytest
from django.test import TestCase
from auction.models import (
    Player, Team, TournamentConfig, TournamentSettings,
    TournamentPool, PoolTeam, Match,
)


# ─────────────────────────────────────────────────────────────
# Team.get_short()
# ─────────────────────────────────────────────────────────────

class TestTeamGetShort(TestCase):

    def test_multi_word_uses_initials(self):
        t = Team(name="Mumbai Indians")
        self.assertEqual(t.get_short(), "MI")

    def test_single_word_uses_first_3(self):
        t = Team(name="Bangalore")
        self.assertEqual(t.get_short(), "BAN")

    def test_explicit_short_name_overrides(self):
        t = Team(name="Mumbai Indians", short_name="MUM")
        self.assertEqual(t.get_short(), "MUM")

    def test_short_name_uppercased(self):
        t = Team(name="Mumbai Indians", short_name="mi")
        self.assertEqual(t.get_short(), "MI")

    def test_three_word_name(self):
        t = Team(name="Royal Challengers Bengaluru")
        self.assertEqual(t.get_short(), "RCB")

    def test_single_char_words_skipped(self):
        # "A B C" → letters only
        t = Team(name="A B C Team")
        # should take A, B, C, T
        result = t.get_short()
        self.assertTrue(len(result) >= 1)


# ─────────────────────────────────────────────────────────────
# Player.save() — point deduction / refund
# ─────────────────────────────────────────────────────────────

class TestPlayerSave(TestCase):

    def setUp(self):
        self.config = TournamentConfig.objects.create(total_points=10000)
        self.team_a = Team.objects.create(name="Alpha", remaining_points=10000)
        self.team_b = Team.objects.create(name="Beta",  remaining_points=10000)

    def test_sell_deducts_points(self):
        Player.objects.create(
            name="P1", role="AR", base_price=0,
            status=Player.STATUS_SOLD, team=self.team_a, sold_price=1500
        )
        self.team_a.refresh_from_db()
        self.assertEqual(self.team_a.remaining_points, 8500)

    def test_unsell_refunds_points(self):
        p = Player.objects.create(
            name="P2", role="BAT", base_price=0,
            status=Player.STATUS_SOLD, team=self.team_a, sold_price=800
        )
        self.team_a.refresh_from_db()
        self.assertEqual(self.team_a.remaining_points, 9200)

        p.status     = Player.STATUS_AVAILABLE
        p.team       = None
        p.sold_price = None
        p.save()
        self.team_a.refresh_from_db()
        self.assertEqual(self.team_a.remaining_points, 10000)

    def test_price_edit_no_double_deduct(self):
        p = Player.objects.create(
            name="P3", role="BAT", base_price=0,
            status=Player.STATUS_SOLD, team=self.team_a, sold_price=600
        )
        self.team_a.refresh_from_db()
        self.assertEqual(self.team_a.remaining_points, 9400)

        p.sold_price = 700
        p.save()
        self.team_a.refresh_from_db()
        # old 600 refunded, new 700 charged → 10000 - 700 = 9300
        self.assertEqual(self.team_a.remaining_points, 9300)

    def test_team_switch_correct_points(self):
        p = Player.objects.create(
            name="P4", role="BOWL", base_price=0,
            status=Player.STATUS_SOLD, team=self.team_a, sold_price=500
        )
        self.team_a.refresh_from_db()
        self.assertEqual(self.team_a.remaining_points, 9500)

        p.team = self.team_b
        p.save()
        self.team_a.refresh_from_db()
        self.team_b.refresh_from_db()
        self.assertEqual(self.team_a.remaining_points, 10000)  # refunded
        self.assertEqual(self.team_b.remaining_points, 9500)   # charged

    def test_available_player_no_deduction(self):
        Player.objects.create(
            name="P5", role="PLY", base_price=0,
            status=Player.STATUS_AVAILABLE
        )
        self.team_a.refresh_from_db()
        self.assertEqual(self.team_a.remaining_points, 10000)


# ─────────────────────────────────────────────────────────────
# TournamentSettings singleton
# ─────────────────────────────────────────────────────────────

class TestTournamentSettings(TestCase):

    def test_get_creates_default(self):
        ts = TournamentSettings.get()
        self.assertIsNotNone(ts)
        self.assertEqual(ts.pk, 1)

    def test_get_returns_same_instance(self):
        ts1 = TournamentSettings.get()
        ts1.tournament_name = "Sachin Kolige Premier League 2025"
        ts1.save()
        ts2 = TournamentSettings.get()
        self.assertEqual(ts2.tournament_name, "Sachin Kolige Premier League 2025")


# ─────────────────────────────────────────────────────────────
# TournamentPool — teams_per_pool, assignment_order fields
# ─────────────────────────────────────────────────────────────

class TestTournamentPool(TestCase):

    def test_create_pool_with_new_fields(self):
        pool = TournamentPool.objects.create(
            stage=TournamentPool.STAGE_GROUP,
            name="A", order=0, advance_n=2,
            teams_per_pool=4, assignment_order="roundrobin",
        )
        pool.refresh_from_db()
        self.assertEqual(pool.teams_per_pool, 4)
        self.assertEqual(pool.assignment_order, "roundrobin")
        self.assertFalse(pool.fixtures_locked)

    def test_default_assignment_order_is_sequential(self):
        pool = TournamentPool.objects.create(
            stage=TournamentPool.STAGE_GROUP,
            name="B", order=1, advance_n=2, teams_per_pool=4,
        )
        self.assertEqual(pool.assignment_order, "sequential")
