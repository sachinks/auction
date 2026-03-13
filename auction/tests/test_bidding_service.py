from django.test import TestCase
from auction.models import Player, Team, TournamentConfig, AuctionState
from auction.services.bidding_service import BiddingService


class BiddingValidationTest(TestCase):

    def setUp(self):
        self.config = TournamentConfig.objects.create(
            total_points=10000, bidding_slots=11,
            base_price_AR=1000, base_price_BAT=400,
            base_price_BOWL=400, base_price_PLY=100,
        )
        self.team = Team.objects.create(name="Team X", remaining_points=5000)
        self.player = Player.objects.create(
            name="Test Player", role="AR", base_price=1000, status=Player.STATUS_AVAILABLE
        )
        AuctionState.get()  # ensure state exists

    def _service(self):
        return BiddingService()

    def test_below_base_price_rejected(self):
        svc   = self._service()
        error = svc.validate_bid(self.player, self.team, 500)
        self.assertIsNotNone(error)
        self.assertIn("base price", error)

    def test_exceeds_available_points(self):
        svc   = self._service()
        error = svc.validate_bid(self.player, self.team, 6000)
        self.assertIsNotNone(error)
        self.assertIn("exceeds", error)

    def test_valid_bid_passes(self):
        svc   = self._service()
        error = svc.validate_bid(self.player, self.team, 1000)
        self.assertIsNone(error)

    def test_force_sell_bypasses_validation(self):
        svc            = self._service()
        self.player.status = Player.STATUS_AVAILABLE
        self.player.save()
        success, err, _ = svc.sell_player(
            self.player.serial_number, self.team.team_serial_number, 0, force=True
        )
        self.assertTrue(success)
        self.assertIsNone(err)


class UnsoldRebidTest(TestCase):

    def setUp(self):
        self.config = TournamentConfig.objects.create(
            total_points=10000, bidding_slots=11,
            base_price_PLY=100, max_rebid_attempts=3
        )
        AuctionState.get()

    def test_icon_no_auto_drop(self):
        p = Player.objects.create(name="AR Player", role="AR", base_price=1000)
        svc = BiddingService()
        state = AuctionState.get()
        state.current_player = p
        state.save()
        for _ in range(5):
            p.status = Player.STATUS_AVAILABLE
            p.save()
            state.current_player = p
            state.save()
            svc.mark_unsold(p.serial_number)
        p.refresh_from_db()
        self.assertEqual(p.status, Player.STATUS_UNSOLD)  # never auto-dropped

    def test_ply_auto_drop_after_max(self):
        p = Player.objects.create(name="PLY Player", role="PLY", base_price=100)
        svc = BiddingService()
        state = AuctionState.get()
        for _ in range(3):
            p.status = Player.STATUS_AVAILABLE
            p.save()
            state.current_player = p
            state.save()
            svc.mark_unsold(p.serial_number)
        p.refresh_from_db()
        self.assertEqual(p.status, Player.STATUS_NOT_PLAYING)
