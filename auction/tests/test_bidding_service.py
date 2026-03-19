"""
Tests for BiddingService: sell, unsold, not-playing, undo, force-sell.
"""
from django.test import TestCase
from auction.models import Player, Team, TournamentConfig, AuctionState, AuctionAction
from auction.services.bidding_service import BiddingService


def _setup_state():
    state = AuctionState.get()
    state.is_active = True
    state.phase     = AuctionState.PHASE_MAIN
    state.current_category = "AR"
    state.save()
    return state


class TestBiddingValidation(TestCase):

    def setUp(self):
        self.config = TournamentConfig.objects.create(
            total_points=10000, bidding_slots=11,
            base_price_AR=1000, base_price_BAT=400,
            base_price_BOWL=400, base_price_PLY=100,
        )
        self.team   = Team.objects.create(name="X", remaining_points=5000)
        self.player = Player.objects.create(name="Bumrah", role="AR", base_price=1000)
        _setup_state()

    def test_below_base_price_fails(self):
        err, is_below = BiddingService().validate_bid(self.player, self.team, 500)
        self.assertIsNotNone(err)
        self.assertIn("base price", err)
        self.assertTrue(is_below)

    def test_exceeds_wallet_fails(self):
        err, is_below = BiddingService().validate_bid(self.player, self.team, 6000)
        self.assertIsNotNone(err)
        self.assertIn("exceeds", err)

    def test_exact_base_price_passes(self):
        err, is_below = BiddingService().validate_bid(self.player, self.team, 1000)
        self.assertIsNone(err)
        self.assertFalse(is_below)

    def test_above_base_price_passes(self):
        err, is_below = BiddingService().validate_bid(self.player, self.team, 2500)
        self.assertIsNone(err)
        self.assertFalse(is_below)

    def test_bat_base_price_check(self):
        p   = Player.objects.create(name="Kohli", role="BAT", base_price=400)
        err, _ = BiddingService().validate_bid(p, self.team, 300)
        self.assertIsNotNone(err)

    def test_ply_base_price_check(self):
        p   = Player.objects.create(name="PLY1", role="PLY", base_price=100)
        err, _ = BiddingService().validate_bid(p, self.team, 50)
        self.assertIsNotNone(err)


class TestSellPlayer(TestCase):

    def setUp(self):
        self.config = TournamentConfig.objects.create(
            total_points=10000, bidding_slots=11,
            base_price_AR=1000,
        )
        self.team   = Team.objects.create(name="Y", remaining_points=10000)
        self.player = Player.objects.create(name="Jadeja", role="AR", base_price=1000)
        state = _setup_state()
        state.current_player = self.player
        state.save()

    def test_sell_marks_player_sold(self):
        ok, err, _ = BiddingService().sell_player(
            self.player.serial_number, self.team.team_serial_number, 1500
        )
        self.assertTrue(ok)
        self.player.refresh_from_db()
        self.assertEqual(self.player.status, Player.STATUS_SOLD)
        self.assertEqual(self.player.sold_price, 1500)
        self.assertEqual(self.player.team, self.team)

    def test_sell_deducts_team_points(self):
        BiddingService().sell_player(
            self.player.serial_number, self.team.team_serial_number, 2000
        )
        self.team.refresh_from_db()
        self.assertEqual(self.team.remaining_points, 8000)

    def test_sell_creates_action_log(self):
        BiddingService().sell_player(
            self.player.serial_number, self.team.team_serial_number, 1000
        )
        action = AuctionAction.objects.last()
        self.assertEqual(action.action, "SELL")
        self.assertEqual(action.amount, 1000)

    def test_sell_below_base_price_fails_without_force(self):
        ok, err, allow_force = BiddingService().sell_player(
            self.player.serial_number, self.team.team_serial_number, 500
        )
        self.assertFalse(ok)
        self.assertIsNotNone(err)
        self.assertTrue(allow_force)

    def test_force_sell_bypasses_validation(self):
        ok, err, _ = BiddingService().sell_player(
            self.player.serial_number, self.team.team_serial_number, 0, force=True
        )
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.player.refresh_from_db()
        self.assertEqual(self.player.status, Player.STATUS_SOLD)

    def test_sell_clears_current_player(self):
        BiddingService().sell_player(
            self.player.serial_number, self.team.team_serial_number, 1000
        )
        state = AuctionState.get()
        self.assertIsNone(state.current_player)


class TestMarkUnsold(TestCase):

    def setUp(self):
        self.config = TournamentConfig.objects.create(
            total_points=10000, bidding_slots=11,
            base_price_PLY=100, max_rebid_attempts=4,
        )
        _setup_state()

    def test_ar_never_auto_dropped(self):
        p   = Player.objects.create(name="AR", role="AR", base_price=1000)
        svc = BiddingService()
        for _ in range(5):
            p.status = Player.STATUS_AVAILABLE
            p.save()
            s = AuctionState.get()
            s.current_player = p
            s.save()
            svc.mark_unsold(p.serial_number)
        p.refresh_from_db()
        self.assertNotEqual(p.status, Player.STATUS_NOT_PLAYING)

    def test_ply_auto_drops_at_max(self):
        p   = Player.objects.create(name="PLY", role="PLY", base_price=100)
        svc = BiddingService()
        for _ in range(4):
            p.refresh_from_db()
            p.status = Player.STATUS_AVAILABLE
            p.save()
            s = AuctionState.get()
            s.current_player = p
            s.save()
            svc.mark_unsold(p.serial_number)
        p.refresh_from_db()
        self.assertEqual(p.status, Player.STATUS_NOT_PLAYING)

    def test_unsold_increments_rebid_count(self):
        p   = Player.objects.create(name="PLY2", role="PLY", base_price=100)
        svc = BiddingService()
        s   = AuctionState.get()
        s.current_player = p
        s.save()
        svc.mark_unsold(p.serial_number)
        p.refresh_from_db()
        self.assertEqual(p.rebid_count, 1)

    def test_unsold_creates_action(self):
        p = Player.objects.create(name="PLY3", role="PLY", base_price=100)
        s = AuctionState.get()
        s.current_player = p
        s.save()
        BiddingService().mark_unsold(p.serial_number)
        action = AuctionAction.objects.last()
        self.assertIn(action.action, ["UNSOLD", "NOT_PLAYING"])


class TestMarkNotPlaying(TestCase):

    def setUp(self):
        TournamentConfig.objects.create(total_points=10000, bidding_slots=11)
        _setup_state()

    def test_mark_not_playing_status(self):
        p = Player.objects.create(name="P", role="PLY", base_price=100)
        s = AuctionState.get()
        s.current_player = p
        s.save()
        BiddingService().mark_not_playing(p.serial_number)
        p.refresh_from_db()
        self.assertEqual(p.status, Player.STATUS_NOT_PLAYING)

    def test_not_playing_creates_action(self):
        p = Player.objects.create(name="P2", role="PLY", base_price=100)
        s = AuctionState.get()
        s.current_player = p
        s.save()
        BiddingService().mark_not_playing(p.serial_number)
        action = AuctionAction.objects.last()
        self.assertEqual(action.action, "NOT_PLAYING")


class TestUndoAction(TestCase):

    def setUp(self):
        self.config = TournamentConfig.objects.create(
            total_points=10000, bidding_slots=11,
            base_price_AR=1000,
        )
        self.team   = Team.objects.create(name="Z", remaining_points=10000)
        self.player = Player.objects.create(name="Shami", role="AR", base_price=1000)
        state = _setup_state()
        state.current_player = self.player
        state.save()

    def test_undo_sell_restores_player(self):
        svc = BiddingService()
        svc.sell_player(self.player.serial_number, self.team.team_serial_number, 2000)
        svc.undo_last_action()
        self.player.refresh_from_db()
        self.assertEqual(self.player.status, Player.STATUS_AVAILABLE)
        self.assertIsNone(self.player.team)
        self.assertIsNone(self.player.sold_price)

    def test_undo_sell_refunds_points(self):
        svc = BiddingService()
        svc.sell_player(self.player.serial_number, self.team.team_serial_number, 2000)
        self.team.refresh_from_db()
        self.assertEqual(self.team.remaining_points, 8000)
        svc.undo_last_action()
        self.team.refresh_from_db()
        self.assertEqual(self.team.remaining_points, 10000)

    def test_undo_unsold_restores_available(self):
        svc = BiddingService()
        state = AuctionState.get()
        state.current_player = self.player
        state.save()
        svc.mark_unsold(self.player.serial_number)
        state.current_player = self.player
        state.save()
        svc.undo_last_action()
        self.player.refresh_from_db()
        self.assertEqual(self.player.status, Player.STATUS_AVAILABLE)

    def test_undo_logs_undo_action(self):
        svc = BiddingService()
        svc.sell_player(self.player.serial_number, self.team.team_serial_number, 1000)
        svc.undo_last_action()
        last = AuctionAction.objects.last()
        self.assertEqual(last.action, "UNDO")

    def test_undo_with_no_actions_does_not_crash(self):
        AuctionAction.objects.all().delete()
        BiddingService().undo_last_action()  # should not raise
