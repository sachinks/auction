"""
Tests for AuctionEngine: round labels, blocked teams,
phase transitions, recalculate points.
"""
import pytest
from django.test import TestCase
from auction.models import Player, Team, TournamentConfig, AuctionState
from auction.services.auction_engine import AuctionEngine, round_label


# ─────────────────────────────────────────────────────────────
# round_label()
# ─────────────────────────────────────────────────────────────

class TestRoundLabel(TestCase):

    def test_ar_main_pass1(self):
        label = round_label("AR", AuctionState.PHASE_MAIN, 1)
        self.assertIn("All Rounder", label)
        self.assertIn("Round", label)
        self.assertNotIn("Pass 2", label)
        self.assertNotIn("Rebid", label)

    def test_bat_main_pass2(self):
        label = round_label("BAT", AuctionState.PHASE_MAIN, 2)
        self.assertIn("Batting", label)
        self.assertIn("Pass 2", label)

    def test_bowl_rebid_pass1(self):
        label = round_label("BOWL", AuctionState.PHASE_REBID, 1)
        self.assertIn("Bowling", label)
        self.assertIn("Rebid", label)

    def test_ply_label(self):
        label = round_label("PLY", AuctionState.PHASE_MAIN, 1)
        self.assertIn("Player", label)

    def test_rebid_pass2_shows_pass(self):
        label = round_label("AR", AuctionState.PHASE_REBID, 2)
        self.assertIn("Pass 2", label)


# ─────────────────────────────────────────────────────────────
# get_blocked_team_ids()
# ─────────────────────────────────────────────────────────────

class TestBlockedTeams(TestCase):

    def setUp(self):
        TournamentConfig.objects.create(total_points=10000, bidding_slots=11)
        self.team_a = Team.objects.create(name="Team A", remaining_points=10000)
        self.team_b = Team.objects.create(name="Team B", remaining_points=10000)
        # Team A already has an AR
        Player.objects.create(
            name="AR Guy", role="AR", base_price=1000,
            status=Player.STATUS_SOLD, team=self.team_a, sold_price=1000
        )

    def _state(self, phase, cat, pass_num):
        s = AuctionState.get()
        s.phase, s.current_category, s.category_pass = phase, cat, pass_num
        s.save()
        return s

    def test_ar_pass1_blocks_team_that_has_ar(self):
        state   = self._state(AuctionState.PHASE_MAIN, "AR", 1)
        blocked = AuctionEngine().get_blocked_team_ids(state)
        self.assertIn(self.team_a.team_serial_number, blocked)
        self.assertNotIn(self.team_b.team_serial_number, blocked)

    def test_ar_pass2_no_blocking(self):
        state   = self._state(AuctionState.PHASE_MAIN, "AR", 2)
        blocked = AuctionEngine().get_blocked_team_ids(state)
        self.assertEqual(len(blocked), 0)

    def test_ar_rebid_pass1_blocks(self):
        state   = self._state(AuctionState.PHASE_REBID, "AR", 1)
        blocked = AuctionEngine().get_blocked_team_ids(state)
        self.assertIn(self.team_a.team_serial_number, blocked)

    def test_ply_never_blocked(self):
        state   = self._state(AuctionState.PHASE_MAIN, "PLY", 1)
        blocked = AuctionEngine().get_blocked_team_ids(state)
        self.assertEqual(len(blocked), 0)

    def test_bat_pass1_blocks_team_with_bat(self):
        Player.objects.create(
            name="BAT Guy", role="BAT", base_price=400,
            status=Player.STATUS_SOLD, team=self.team_b, sold_price=500
        )
        state   = self._state(AuctionState.PHASE_MAIN, "BAT", 1)
        blocked = AuctionEngine().get_blocked_team_ids(state)
        self.assertIn(self.team_b.team_serial_number, blocked)
        self.assertNotIn(self.team_a.team_serial_number, blocked)


# ─────────────────────────────────────────────────────────────
# recalculate_points()
# ─────────────────────────────────────────────────────────────

class TestRecalculatePoints(TestCase):

    def setUp(self):
        self.config = TournamentConfig.objects.create(total_points=10000, bidding_slots=11)
        self.team   = Team.objects.create(name="T", remaining_points=10000)

    def test_recalculate_fixes_corrupted_points(self):
        Player.objects.create(
            name="P1", role="AR", base_price=0,
            status=Player.STATUS_SOLD, team=self.team, sold_price=1500
        )
        self.team.remaining_points = 7000  # deliberately wrong
        self.team.save()
        AuctionEngine().recalculate_points()
        self.team.refresh_from_db()
        self.assertEqual(self.team.remaining_points, 8500)

    def test_recalculate_multiple_players(self):
        for price in [1000, 500, 750]:
            Player.objects.create(
                name=f"P{price}", role="BAT", base_price=0,
                status=Player.STATUS_SOLD, team=self.team, sold_price=price
            )
        AuctionEngine().recalculate_points()
        self.team.refresh_from_db()
        self.assertEqual(self.team.remaining_points, 10000 - 2250)

    def test_recalculate_no_config_does_not_crash(self):
        TournamentConfig.objects.all().delete()
        engine = AuctionEngine()
        engine.config = None
        # Should return silently without error
        engine.recalculate_points()


# ─────────────────────────────────────────────────────────────
# activate_auction()
# ─────────────────────────────────────────────────────────────

class TestActivateAuction(TestCase):

    def setUp(self):
        self.config = TournamentConfig.objects.create(
            total_points=10000, bidding_slots=11,
            category_order='["AR","BAT","BOWL","PLY"]',
        )

    def test_activate_sets_phase_main(self):
        AuctionEngine().activate_auction()
        state = AuctionState.get()
        self.assertTrue(state.is_active)
        self.assertEqual(state.phase, AuctionState.PHASE_MAIN)

    def test_activate_sets_first_category(self):
        AuctionEngine().activate_auction()
        state = AuctionState.get()
        self.assertEqual(state.current_category, "AR")

    def test_activate_sets_awaiting_transition(self):
        AuctionEngine().activate_auction()
        state = AuctionState.get()
        self.assertTrue(state.awaiting_transition)
        self.assertIsNotNone(state.transition_message)
