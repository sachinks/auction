"""
auction_engine.py
─────────────────
Core auction flow: phase management, player picking, round transitions.
"""
import random
import logging
import traceback

from auction.models import Player, Team, TournamentConfig, AuctionState

logger = logging.getLogger("auction")

ICON_CATEGORIES = {"AR", "BAT", "BOWL"}

ROUND_DISPLAY = {
    "AR":   "All Rounder",
    "BAT":  "Batting",
    "BOWL": "Bowling",
    "PLY":  "Player",
}


def round_label(cat, phase, pass_num):
    """Human-readable round name for UI display."""
    base = ROUND_DISPLAY.get(cat, cat)
    if phase == AuctionState.PHASE_REBID:
        suffix = " Rebid" + (f" · Pass {pass_num}" if pass_num > 1 else "")
    else:
        suffix = " Round" + (f" · Pass {pass_num}" if pass_num > 1 else "")
    return base + suffix


class AuctionEngine:

    def __init__(self):
        try:
            self.config = TournamentConfig.objects.first()
        except Exception as e:
            logger.error(f"AuctionEngine.__init__ failed: {e}")
            self.config = None

    def get_current_player(self):
        try:
            return AuctionState.get().current_player
        except Exception as e:
            logger.error(f"get_current_player error: {e}")
            return None

    def get_state(self):
        return AuctionState.get()

    def activate_auction(self):
        logger.info("activate_auction called")
        try:
            config         = self.config
            category_order = config.get_category_order() if config else ["AR"]
            first_cat      = category_order[0] if category_order else "AR"

            state = AuctionState.get()
            state.is_active           = True
            state.phase               = AuctionState.PHASE_MAIN
            state.current_category    = first_cat
            state.category_pass       = 1
            state.auction_round       = 1
            state.current_player      = None
            state.awaiting_transition = True
            state.transition_message  = f"{ROUND_DISPLAY.get(first_cat, first_cat)} Round – Press Start to begin"
            state.save()
            logger.info(f"Auction activated — first category: {first_cat}")
        except Exception as e:
            logger.error(f"activate_auction error: {e}\n{traceback.format_exc()}")
            raise

    def confirm_transition(self):
        logger.info("confirm_transition called")
        try:
            state = AuctionState.get()
            state.awaiting_transition = False
            state.transition_message  = ""
            state.save()
            return self.advance_to_next_player()
        except Exception as e:
            logger.error(f"confirm_transition error: {e}\n{traceback.format_exc()}")
            raise

    def advance_to_next_player(self):
        try:
            state = AuctionState.get()

            if state.phase == AuctionState.PHASE_DONE:
                return None

            if state.awaiting_transition:
                state.current_player = None
                state.save()
                return None

            player = self._pick_from_current_slot(state)

            if player:
                state.current_player = player
                state.save()
                logger.info(f"Next player: {player.name} ({player.role})")
                return player

            logger.info(f"Pool exhausted for {state.current_category} — transitioning")
            self._set_next_transition(state)
            state = AuctionState.get()
            state.current_player = None
            state.save()
            return None
        except Exception as e:
            logger.error(f"advance_to_next_player error: {e}\n{traceback.format_exc()}")
            raise

    def _pick_from_current_slot(self, state):
        cat      = state.current_category
        phase    = state.phase
        pass_num = state.category_pass
        try:
            if phase == AuctionState.PHASE_MAIN:
                if pass_num == 1:
                    pool = list(Player.objects.filter(status=Player.STATUS_AVAILABLE, role=cat))
                else:
                    pool = list(Player.objects.filter(
                        role=cat,
                        status__in=[Player.STATUS_AVAILABLE, Player.STATUS_UNSOLD]
                    ))
                return random.choice(pool) if pool else None
            elif phase == AuctionState.PHASE_REBID:
                pool = list(Player.objects.filter(status=Player.STATUS_UNSOLD, role=cat))
                return random.choice(pool) if pool else None
            return None
        except Exception as e:
            logger.error(f"_pick_from_current_slot error: {e}\n{traceback.format_exc()}")
            return None

    def _set_next_transition(self, state):
        config         = self.config
        cat            = state.current_category
        phase          = state.phase
        pass_num       = state.category_pass
        category_order = config.get_category_order() if config else ["AR", "BAT", "BOWL", "PLY"]
        base           = ROUND_DISPLAY.get(cat, cat)

        try:
            if phase == AuctionState.PHASE_MAIN and pass_num == 1:
                all_have_one = self._all_teams_have_icon(cat) if cat in ICON_CATEGORIES else True
                unsold_exist = Player.objects.filter(status=Player.STATUS_UNSOLD, role=cat).exists()

                if not all_have_one and unsold_exist:
                    state.phase               = AuctionState.PHASE_REBID
                    state.auction_round      += 1
                    state.awaiting_transition = True
                    state.transition_message  = f"{base} Pass 1 complete · Starting {base} Rebid"
                    state.save()
                    return

                if cat in ICON_CATEGORIES:
                    more = Player.objects.filter(role=cat).exclude(
                        status__in=[Player.STATUS_NOT_PLAYING, Player.STATUS_SOLD]
                    ).exists()
                    if more:
                        state.phase               = AuctionState.PHASE_MAIN
                        state.category_pass       = 2
                        state.auction_round      += 1
                        state.awaiting_transition = True
                        state.transition_message  = f"{base} Pass 1 complete · Starting {base} Pass 2"
                        state.save()
                        return

                self._transition_to_next_category(state, cat, category_order)

            elif phase == AuctionState.PHASE_REBID:
                if cat in ICON_CATEGORIES and pass_num == 1:
                    more = Player.objects.filter(role=cat, status=Player.STATUS_AVAILABLE).exists()
                    if more:
                        state.phase               = AuctionState.PHASE_MAIN
                        state.category_pass       = 2
                        state.auction_round      += 1
                        state.awaiting_transition = True
                        state.transition_message  = f"{base} Rebid complete · Starting {base} Pass 2"
                        state.save()
                        return
                self._transition_to_next_category(state, cat, category_order)

            elif phase == AuctionState.PHASE_MAIN and pass_num == 2:
                unsold_exist = Player.objects.filter(status=Player.STATUS_UNSOLD, role=cat).exists()
                if unsold_exist:
                    state.phase               = AuctionState.PHASE_REBID
                    state.auction_round      += 1
                    state.awaiting_transition = True
                    state.transition_message  = f"{base} Pass 2 complete · Starting {base} Rebid Pass 2"
                    state.save()
                    return
                self._transition_to_next_category(state, cat, category_order)

        except Exception as e:
            logger.error(f"_set_next_transition error: {e}\n{traceback.format_exc()}")
            raise

    def _transition_to_next_category(self, state, current_cat, category_order):
        try:
            idx            = category_order.index(current_cat)
            remaining_cats = category_order[idx + 1:]
        except ValueError:
            remaining_cats = []

        for next_cat in remaining_cats:
            has_players = Player.objects.filter(role=next_cat).exclude(
                status=Player.STATUS_NOT_PLAYING
            ).exists()
            if has_players:
                base_curr = ROUND_DISPLAY.get(current_cat, current_cat)
                base_next = ROUND_DISPLAY.get(next_cat, next_cat)
                state.phase               = AuctionState.PHASE_MAIN
                state.current_category    = next_cat
                state.category_pass       = 1
                state.auction_round      += 1
                state.awaiting_transition = True
                state.transition_message  = f"{base_curr} Round complete · Starting {base_next} Round"
                state.save()
                logger.info(f"Transition → {next_cat} Round")
                return

        logger.info("All categories exhausted")
        state.awaiting_transition = False
        state.transition_message  = ""
        state.save()

    def get_blocked_team_ids(self, state):
        cat      = state.current_category
        phase    = state.phase
        pass_num = state.category_pass

        if cat not in ICON_CATEGORIES:
            return set()

        try:
            if pass_num == 1 and phase in (AuctionState.PHASE_MAIN, AuctionState.PHASE_REBID):
                blocked = Team.objects.filter(
                    player__role=cat, player__status=Player.STATUS_SOLD
                ).distinct().values_list("team_serial_number", flat=True)
                return set(blocked)
        except Exception as e:
            logger.error(f"get_blocked_team_ids error: {e}")
        return set()

    def _all_teams_have_icon(self, cat):
        try:
            total  = Team.objects.count()
            with_one = Team.objects.filter(
                player__role=cat, player__status=Player.STATUS_SOLD
            ).distinct().count()
            return with_one >= total
        except Exception as e:
            logger.error(f"_all_teams_have_icon error: {e}")
            return False

    def clear_current_player(self):
        try:
            state                = AuctionState.get()
            state.current_player = None
            state.save()
        except Exception as e:
            logger.error(f"clear_current_player error: {e}")

    def restore_player(self, player):
        try:
            state                = AuctionState.get()
            state.current_player = player
            state.is_active      = True
            state.save()
        except Exception as e:
            logger.error(f"restore_player error: {e}")

    def recalculate_points(self):
        logger.info("recalculate_points called")
        try:
            config = self.config
            if not config:
                return
            from django.db.models import Sum
            for team in Team.objects.all():
                spent = Player.objects.filter(
                    team=team, status=Player.STATUS_SOLD
                ).aggregate(total=Sum("sold_price"))["total"] or 0
                team.remaining_points = config.total_points - spent
                team.save()
        except Exception as e:
            logger.error(f"recalculate_points error: {e}\n{traceback.format_exc()}")
            raise

    def reset_auction(self):
        logger.warning("reset_auction called")
        try:
            Player.objects.all().update(
                sold_price=None, team=None,
                status=Player.STATUS_AVAILABLE, rebid_count=0
            )
            config = TournamentConfig.objects.first()
            for team in Team.objects.all():
                team.remaining_points = config.total_points if config else 0
                team.save()

            state                     = AuctionState.get()
            state.current_player      = None
            state.phase               = AuctionState.PHASE_MAIN
            state.current_category    = "AR"
            state.category_pass       = 1
            state.auction_round       = 1
            state.is_active           = False
            state.awaiting_transition = False
            state.transition_message  = ""
            state.save()
            TournamentConfig.objects.all().delete()
        except Exception as e:
            logger.error(f"reset_auction error: {e}\n{traceback.format_exc()}")
            raise
