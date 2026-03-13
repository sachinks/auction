from django.test import TestCase
from auction.models import Player, Team, TournamentConfig, AuctionState
from auction.services.auction_engine import AuctionEngine, round_label


class RoundLabelTest(TestCase):

    def test_main_pass1(self):
        label = round_label("AR", AuctionState.PHASE_MAIN, 1)
        self.assertIn("All Rounder", label)
        self.assertIn("Round", label)

    def test_rebid(self):
        label = round_label("BAT", AuctionState.PHASE_REBID, 1)
        self.assertIn("Batting", label)
        self.assertIn("Rebid", label)

    def test_pass2(self):
        label = round_label("BOWL", AuctionState.PHASE_MAIN, 2)
        self.assertIn("Bowling", label)
        self.assertIn("Pass 2", label)

    def test_ply(self):
        label = round_label("PLY", AuctionState.PHASE_MAIN, 1)
        self.assertIn("Player", label)


class BlockedTeamsTest(TestCase):

    def setUp(self):
        TournamentConfig.objects.create(total_points=10000, bidding_slots=11)
        self.team_a = Team.objects.create(name="Team A", remaining_points=10000)
        self.team_b = Team.objects.create(name="Team B", remaining_points=10000)
        # Team A already has an AR
        Player.objects.create(name="AR Guy", role="AR", base_price=1000,
                               status=Player.STATUS_SOLD, team=self.team_a, sold_price=1000)

    def test_pass1_blocks_team_with_ar(self):
        state = AuctionState.get()
        state.phase = AuctionState.PHASE_MAIN
        state.current_category = "AR"
        state.category_pass = 1
        state.save()
        engine  = AuctionEngine()
        blocked = engine.get_blocked_team_ids(state)
        self.assertIn(self.team_a.team_serial_number, blocked)
        self.assertNotIn(self.team_b.team_serial_number, blocked)

    def test_pass2_no_blocking(self):
        state = AuctionState.get()
        state.phase = AuctionState.PHASE_MAIN
        state.current_category = "AR"
        state.category_pass = 2
        state.save()
        engine  = AuctionEngine()
        blocked = engine.get_blocked_team_ids(state)
        self.assertEqual(len(blocked), 0)

    def test_rebid_pass1_blocks(self):
        state = AuctionState.get()
        state.phase = AuctionState.PHASE_REBID
        state.current_category = "AR"
        state.category_pass = 1
        state.save()
        engine  = AuctionEngine()
        blocked = engine.get_blocked_team_ids(state)
        self.assertIn(self.team_a.team_serial_number, blocked)

    def test_ply_never_blocked(self):
        state = AuctionState.get()
        state.phase = AuctionState.PHASE_MAIN
        state.current_category = "PLY"
        state.category_pass = 1
        state.save()
        engine  = AuctionEngine()
        blocked = engine.get_blocked_team_ids(state)
        self.assertEqual(len(blocked), 0)


class RecalcPointsTest(TestCase):

    def setUp(self):
        self.config = TournamentConfig.objects.create(total_points=10000, bidding_slots=11)
        self.team   = Team.objects.create(name="T", remaining_points=10000)

    def test_recalculate_correct(self):
        Player.objects.create(name="P1", role="AR", base_price=1000,
                               status=Player.STATUS_SOLD, team=self.team, sold_price=1500)
        # Manually corrupt remaining_points to simulate the double-count bug
        self.team.remaining_points = 7000  # wrong
        self.team.save()
        AuctionEngine().recalculate_points()
        self.team.refresh_from_db()
        self.assertEqual(self.team.remaining_points, 8500)
