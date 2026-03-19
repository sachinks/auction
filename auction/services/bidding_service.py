import logging

from auction.models import Player, Team, AuctionAction, AuctionState
from auction.services.auction_engine import AuctionEngine

ICON_CATEGORIES = {"AR", "BAT", "BOWL"}


logger = logging.getLogger("auction")


class BiddingService:

    def __init__(self):
        self.engine = AuctionEngine()

    # ─────────────────────────────────────────────
    # VALIDATE BID
    # ─────────────────────────────────────────────

    def validate_bid(self, player, team, amount):
        """
        Returns (error_string, is_below_base) if invalid.
        Returns (None, False) if valid.

        is_below_base=True  → soft warning; admin may force-sell at any price.
        is_below_base=False → hard error; cannot be overridden by force-sell.
        """
        config = self.engine.config

        # Rule 1 (soft): minimum bid = category base price — force-sellable
        if config:
            base_price = config.base_price_for_role(player.role)
            if amount < base_price:
                return (
                    f"Bid ₹{amount} is below the base price of ₹{base_price} "
                    f"for {player.role}.",
                    True   # is_below_base
                )

        # Rule 2 (hard): bid cannot exceed available points
        if amount > team.remaining_points:
            return (
                f"Bid ₹{amount} exceeds {team.name}'s available points "
                f"(₹{team.remaining_points}).",
                False
            )

        # Rule 3 (soft): safe bid — enough left to fill remaining slots — force-sellable
        if config:
            squad_size      = team.player_set.filter(status=Player.STATUS_SOLD).count()
            remaining_slots = config.bidding_slots - squad_size
            if remaining_slots > 1:
                min_per_slot   = config.base_price_PLY or 100
                points_after   = team.remaining_points - amount
                minimum_needed = (remaining_slots - 1) * min_per_slot
                if points_after < minimum_needed:
                    return (
                        f"⚠ Unsafe bid — {team.name} would have ₹{points_after} left "
                        f"but needs ₹{int(minimum_needed)} minimum to fill "
                        f"{remaining_slots - 1} remaining slot(s).",
                        True   # is_below_base — force-sellable
                    )

        return None, False  # valid

    # ─────────────────────────────────────────────
    # SELL PLAYER
    # ─────────────────────────────────────────────

    def sell_player(self, player_id, team_id, amount, force=False, extra=False):
        """
        force=True  → bypasses below-base-price AND all other validation (force sell).
        extra=True  → user confirmed adding beyond squad slots; still validates points.
        Returns (success, error_message, is_below_base).
        is_below_base=True  → caller should offer Force Sell option.
        is_below_base=False → hard error, no force option.
        """
        logger.info(f"sell_player: player={player_id} team={team_id} amount={amount} force={force} extra={extra}")
        player = Player.objects.get(serial_number=player_id)
        team   = Team.objects.get(team_serial_number=team_id)
        amount = int(amount)

        if not force:
            error, is_below_base = self.validate_bid(player, team, amount)
            if error:
                return False, error, is_below_base

        # Check if team is over slots
        config     = self.engine.config
        squad_size = team.player_set.filter(status=Player.STATUS_SOLD).count()
        over_slots = config and squad_size >= config.bidding_slots

        if over_slots and not force and not extra:
            return False, None, False  # signal: confirm_extra required

        player.team       = team
        player.sold_price = amount
        player.status     = Player.STATUS_SOLD
        player.save()

        state = AuctionState.get()
        AuctionAction.objects.create(
            player   = player,
            team     = team,
            action   = "SELL",
            amount   = amount,
            round    = state.auction_round,
            category = state.current_category,
            phase    = state.phase,
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

        # Auto-drop when rebid limit reached
        # PLY: drop after max_rebid_attempts (default 3)
        # Icon (AR/BAT/BOWL): drop after max_rebid_attempts × 2 to give more chances
        if config:
            max_attempts = config.max_rebid_attempts  # same limit for all roles
            if player.rebid_count >= max_attempts:
                player.status = Player.STATUS_NOT_PLAYING
                action_type   = "NOT_PLAYING"
                logger.info(
                    f"mark_unsold: {player.name} ({player.role}) "
                    f"auto-dropped after {player.rebid_count} attempts"
                )

        player.save()

        AuctionAction.objects.create(
            player   = player,
            action   = action_type,
            round    = state.auction_round,
            category = state.current_category,
            phase    = state.phase,
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
            phase    = state.phase,
        )

        self.engine.clear_current_player()

    # ─────────────────────────────────────────────
    # UNDO LAST ACTION
    # ─────────────────────────────────────────────

    def undo_last_action(self):
        logger.info("undo_last_action called")
        action = AuctionAction.objects.exclude(action="UNDO").order_by("pk").last()
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
            # Decrement rebid_count if set — covers auto-drop via mark_unsold()
            if player.rebid_count > 0:
                player.rebid_count -= 1
            player.save()

        state = AuctionState.get()
        AuctionAction.objects.create(
            player   = player,
            action   = "UNDO",
            round    = state.auction_round,
            category = state.current_category,
            phase    = state.phase,
        )
        action.delete()
        self.engine.restore_player(player)
