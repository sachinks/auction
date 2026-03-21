"""
Tests for AuctionEngine: round labels, blocked teams,
phase transitions, recalculate points.
"""
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

    def test_ar_rebid_blocks_team_that_has_ar(self):
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


# ─────────────────────────────────────────────────────────────
# _set_next_transition(): full phase flow
# ─────────────────────────────────────────────────────────────

class TestPhaseTransitions(TestCase):
    """Verify that the transition overlay fires at each phase boundary."""

    def _state(self, phase, cat, pass_num, is_active=True):
        s = AuctionState.get()
        s.phase               = phase
        s.current_category    = cat
        s.category_pass       = pass_num
        s.is_active           = is_active
        s.awaiting_transition = False
        s.transition_message  = ""
        s.save()
        return s

    def setUp(self):
        self.config = TournamentConfig.objects.create(
            total_points=10000,
            bidding_slots=11,
            base_price_AR=1000,
            base_price_BAT=400,
            base_price_BOWL=400,
            base_price_PLY=100,
            max_rebid_attempts=4,
            category_order="AR,BAT,BOWL,PLY",
        )
        self.team_a = Team.objects.create(name="Team A", remaining_points=10000)
        self.team_b = Team.objects.create(name="Team B", remaining_points=10000)

    def test_main_pass1_to_rebid_when_unsold_exist(self):
        """MAIN pass 1 exhausted with unsold → transition to REBID."""
        Player.objects.create(name="AR1", role="AR", base_price=1000, status=Player.STATUS_UNSOLD)
        self._state(AuctionState.PHASE_MAIN, "AR", 1)

        AuctionEngine().advance_to_next_player()
        state = AuctionState.get()

        self.assertTrue(state.awaiting_transition)
        self.assertEqual(state.phase, AuctionState.PHASE_REBID)
        self.assertIn("Rebid", state.transition_message)

    def test_rebid_pass1_exhausted_shows_next_category_transition(self):
        """REBID exhausted (no AVAILABLE) → transition to next category (BAT)."""
        # AR players all dealt with (unsold, will be in rebid pool initially)
        ar1 = Player.objects.create(name="AR1", role="AR", base_price=1000, status=Player.STATUS_UNSOLD)
        # BAT players available for next round
        Player.objects.create(name="BAT1", role="BAT", base_price=400, status=Player.STATUS_AVAILABLE)

        # Simulate: AR REBID pool is now empty (AR1 just auto-dropped to NOT_PLAYING)
        ar1.status = Player.STATUS_NOT_PLAYING
        ar1.save()

        self._state(AuctionState.PHASE_REBID, "AR", 1)

        AuctionEngine().advance_to_next_player()
        state = AuctionState.get()

        # Should transition to BAT round
        self.assertTrue(state.awaiting_transition, "pass 3 transition overlay must be set")
        self.assertEqual(state.current_category, "BAT", "category must advance to BAT")
        self.assertEqual(state.phase, AuctionState.PHASE_MAIN, "phase must reset to MAIN for new category")
        self.assertIn("Batting", state.transition_message)

    def test_ply_rebid_exhausted_shows_done_transition(self):
        """PLY REBID exhausted (last category) → DONE transition."""
        Player.objects.create(name="PLY1", role="PLY", base_price=100, status=Player.STATUS_UNSOLD)
        # simulate pool empty
        Player.objects.filter(role="PLY").update(status=Player.STATUS_NOT_PLAYING)

        self._state(AuctionState.PHASE_REBID, "PLY", 1)

        AuctionEngine().advance_to_next_player()
        state = AuctionState.get()

        self.assertTrue(state.awaiting_transition)
        self.assertEqual(state.phase, AuctionState.PHASE_DONE)


# ─────────────────────────────────────────────────────────────
# Full simulation: sell/unsold through entire AR → REBID → BAT
# ─────────────────────────────────────────────────────────────

class TestFullFlowSimulation(TestCase):
    """
    Simulates a complete auction flow using BiddingService and AuctionEngine,
    verifying that the 'pass 3' transition overlay fires after REBID ends.
    """

    def setUp(self):
        self.config = TournamentConfig.objects.create(
            total_points=10000,
            bidding_slots=11,
            base_price_AR=1000,
            base_price_BAT=400,
            base_price_BOWL=400,
            base_price_PLY=100,
            max_rebid_attempts=2,   # low so REBID ends quickly in the test
            category_order="AR,BAT,BOWL,PLY",
        )
        self.team   = Team.objects.create(name="Alpha", remaining_points=10000)
        self.ar1    = Player.objects.create(name="AR1", role="AR", base_price=1000, status=Player.STATUS_AVAILABLE)
        self.bat1   = Player.objects.create(name="BAT1", role="BAT", base_price=400, status=Player.STATUS_AVAILABLE)
        self.engine = AuctionEngine()

    def _confirm(self):
        """Confirm the current transition overlay."""
        self.engine.confirm_transition()

    def _mark_unsold(self, player):
        from auction.services.bidding_service import BiddingService
        state = AuctionState.get()
        state.current_player = player
        state.save()
        BiddingService().mark_unsold(player.serial_number)

    def _auto_advance(self):
        """Simulate the view's auto-advance logic."""
        state = AuctionState.get()
        if (state.current_player is None
                and not state.awaiting_transition
                and state.phase != AuctionState.PHASE_DONE
                and state.is_active):
            self.engine.advance_to_next_player()

    def test_icon_main_rebid_spin_flow(self):
        """
        Full flow: activate → AR Main Round (AR1 unsold) → AR Rebid Round (AR1 unsold again)
        → icon player stays UNSOLD → SPIN round transition fires.
        No per-player rebid pass announcement modal (simplified flow).
        """
        # Activate
        self.engine.activate_auction()
        state = AuctionState.get()
        self.assertTrue(state.awaiting_transition)  # initial transition

        # Confirm initial transition → AR Main Round starts, AR1 on block
        self._confirm()
        state = AuctionState.get()
        self.assertFalse(state.awaiting_transition)
        self.assertEqual(state.current_player, self.ar1)

        # Mark AR1 unsold (rebid_count=1, max=2, still in rebid pool)
        self._mark_unsold(self.ar1)
        self._auto_advance()   # pool exhausted (no more AVAILABLE AR) → REBID transition
        state = AuctionState.get()
        self.assertTrue(state.awaiting_transition, "REBID transition must fire")
        self.assertEqual(state.phase, AuctionState.PHASE_REBID)
        self.assertIn("Rebid Round", state.transition_message)

        # Confirm REBID transition → AR1 is immediately on block (no extra modal)
        self._confirm()
        state = AuctionState.get()
        self.assertFalse(state.awaiting_transition, "No extra rebid pass modal should appear")
        self.ar1.refresh_from_db()
        self.assertEqual(state.current_player, self.ar1)

        # Mark AR1 unsold again (rebid_count=2 == max_rebid_attempts).
        # Icon players stay UNSOLD — NOT dropped to NOT_PLAYING (they go to spin round).
        self._mark_unsold(self.ar1)
        self.ar1.refresh_from_db()
        self.assertEqual(self.ar1.status, Player.STATUS_UNSOLD,
                         "Icon players at max rebid must stay UNSOLD for spin round")
        self.assertEqual(self.ar1.rebid_count, 2)

        # REBID pool now empty (no UNSOLD with rebid_count < 2) →
        # auto-advance should set SPIN ROUND transition (AR1 still UNSOLD + team has no AR)
        self._auto_advance()
        state = AuctionState.get()
        self.assertTrue(state.awaiting_transition, "Spin round transition must be set")
        self.assertEqual(state.phase, AuctionState.PHASE_SPIN)
        self.assertIn("SPIN Round", state.transition_message)
