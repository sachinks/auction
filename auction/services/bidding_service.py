from auction.models import Player, Team, AuctionAction, AuctionState
from auction.services.auction_engine import AuctionEngine

ICON_CATEGORIES = {"AR", "BAT", "BOWL"}


class BiddingService:

    def __init__(self):
        self.engine = AuctionEngine()

    # ─────────────────────────────────────────────
    # VALIDATE BID
    # ─────────────────────────────────────────────

    def validate_bid(self, player, team, amount):
        """
        Returns None if valid.
        Returns error string if invalid.
        Raises nothing — caller decides what to do with the error.
        """
        config = self.engine.config

        # Rule 1: minimum bid = category base price
        if config:
            base_price = config.base_price_for_role(player.role)
            if amount < base_price:
                return (
                    f"Bid ₹{amount} is below the base price for "
                    f"{player.role} (minimum: ₹{base_price})."
                )

        # Rule 2: bid cannot exceed available points
        if amount > team.remaining_points:
            return (
                f"Bid ₹{amount} exceeds {team.name}'s available points "
                f"(₹{team.remaining_points})."
            )

        # Rule 3: safe bid — enough left to fill remaining slots
        if config:
            squad_size      = team.player_set.filter(status=Player.STATUS_SOLD).count()
            remaining_slots = config.bidding_slots - squad_size
            if remaining_slots > 1:
                min_per_slot   = config.total_points / 100
                points_after   = team.remaining_points - amount
                minimum_needed = (remaining_slots - 1) * min_per_slot
                if points_after < minimum_needed:
                    return (
                        f"⚠ Unsafe bid — {team.name} would have ₹{points_after} left "
                        f"but needs ₹{int(minimum_needed)} minimum to fill "
                        f"{remaining_slots - 1} remaining slot(s)."
                    )

        return None  # valid

    # ─────────────────────────────────────────────
    # SELL PLAYER
    # ─────────────────────────────────────────────

    def sell_player(self, player_id, team_id, amount, force=False):
        """
        force=True bypasses ALL validation (item 8).
        Returns (success, error_message, allow_force).
        allow_force=True means a Force Sell button should be shown.
        """
        player = Player.objects.get(serial_number=player_id)
        team   = Team.objects.get(team_serial_number=team_id)
        amount = int(amount)

        if not force:
            error = self.validate_bid(player, team, amount)
            if error:
                return False, error, True  # allow_force=True for all bid errors

        # Check if team is over slots (item 20)
        config      = self.engine.config
        squad_size  = team.player_set.filter(status=Player.STATUS_SOLD).count()
        over_slots  = config and squad_size >= config.bidding_slots

        if over_slots and not force:
            return False, None, False  # signal: confirm_extra required

        player.team       = team
        player.sold_price = amount
        player.status     = Player.STATUS_SOLD
        player.save()   # model save() handles point deduction

        state = AuctionState.get()
        AuctionAction.objects.create(
            player   = player,
            team     = team,
            action   = "SELL",
            amount   = amount,
            round    = state.auction_round,
            category = state.current_category,
        )

        self.engine.clear_current_player()
        return True, None, False

    # ─────────────────────────────────────────────
    # UNSOLD
    # Icon categories: unlimited rebid
    # PLY: max_rebid_attempts then auto-drop
    # ─────────────────────────────────────────────

    def mark_unsold(self, player_id):
        player    = Player.objects.get(serial_number=player_id)
        config    = self.engine.config
        state     = AuctionState.get()

        player.rebid_count += 1
        player.status       = Player.STATUS_UNSOLD
        action_type         = "UNSOLD"

        # Auto-drop only for PLY
        if player.role not in ICON_CATEGORIES and config:
            if player.rebid_count >= config.max_rebid_attempts:
                player.status = Player.STATUS_NOT_PLAYING
                action_type   = "NOT_PLAYING"

        player.save()

        AuctionAction.objects.create(
            player   = player,
            action   = action_type,
            round    = state.auction_round,
            category = state.current_category,
        )

        self.engine.clear_current_player()

    # ─────────────────────────────────────────────
    # NOT PLAYING
    # ─────────────────────────────────────────────

    def mark_not_playing(self, player_id):
        player = Player.objects.get(serial_number=player_id)
        state  = AuctionState.get()

        player.status = Player.STATUS_NOT_PLAYING
        player.save()

        AuctionAction.objects.create(
            player   = player,
            action   = "NOT_PLAYING",
            round    = state.auction_round,
            category = state.current_category,
        )

        self.engine.clear_current_player()

    # ─────────────────────────────────────────────
    # UNDO LAST ACTION
    # ─────────────────────────────────────────────

    def undo_last_action(self):
        action = AuctionAction.objects.exclude(action="UNDO").last()
        if not action:
            return

        player = action.player

        if action.action == "SELL":
            player.team       = None
            player.sold_price = None
            player.status     = Player.STATUS_AVAILABLE
            player.save()   # model save() handles refund

        elif action.action == "UNSOLD":
            if player.rebid_count > 0:
                player.rebid_count -= 1
            player.status = Player.STATUS_AVAILABLE
            player.save()

        elif action.action == "NOT_PLAYING":
            player.status = Player.STATUS_AVAILABLE
            player.save()

        state = AuctionState.get()
        AuctionAction.objects.create(
            player   = player,
            action   = "UNDO",
            round    = state.auction_round,
            category = state.current_category,
        )
        action.delete()
        self.engine.restore_player(player)
