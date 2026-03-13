import random

from auction.models import Player, Team, TournamentConfig, AuctionState

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
        suffix = f" Rebid" + (f" · Pass {pass_num}" if pass_num > 1 else "")
    else:
        suffix = f" Round" + (f" · Pass {pass_num}" if pass_num > 1 else "")
    return base + suffix


class AuctionEngine:

    def __init__(self):
        self.config = TournamentConfig.objects.first()

    # ─────────────────────────────────────────────
    # PUBLIC: get state
    # ─────────────────────────────────────────────

    def get_current_player(self):
        return AuctionState.get().current_player

    def get_state(self):
        return AuctionState.get()

    # ─────────────────────────────────────────────
    # PUBLIC: activate auction
    # Sets up state and shows first transition banner
    # (item 10 — no auto-pick on start)
    # ─────────────────────────────────────────────

    def activate_auction(self):
        config         = self.config
        category_order = config.get_category_order() if config else ["AR"]
        first_cat      = category_order[0] if category_order else "AR"

        state = AuctionState.get()
        state.is_active             = True
        state.phase                 = AuctionState.PHASE_MAIN
        state.current_category      = first_cat
        state.category_pass         = 1
        state.auction_round         = 1
        state.current_player        = None
        state.awaiting_transition   = True
        state.transition_message    = f"{ROUND_DISPLAY.get(first_cat, first_cat)} Round – Press Start to begin"
        state.save()

    # ─────────────────────────────────────────────
    # PUBLIC: confirm transition (admin clicks Continue)
    # ─────────────────────────────────────────────

    def confirm_transition(self):
        state = AuctionState.get()
        state.awaiting_transition = False
        state.transition_message  = ""
        state.save()
        return self.advance_to_next_player()

    # ─────────────────────────────────────────────
    # PUBLIC: advance to next player
    # ─────────────────────────────────────────────

    def advance_to_next_player(self):
        state = AuctionState.get()

        if state.phase == AuctionState.PHASE_DONE:
            return None

        if state.awaiting_transition:
            # Still waiting for admin to click Continue
            state.current_player = None
            state.save()
            return None

        player = self._pick_from_current_slot(state)

        if player:
            state.current_player = player
            state.save()
            return player

        # Pool exhausted — determine next transition
        self._set_next_transition(state)
        state = AuctionState.get()  # re-fetch after _set_next_transition saves
        state.current_player = None
        state.save()
        return None

    # ─────────────────────────────────────────────
    # INTERNAL: pick from current slot
    # ─────────────────────────────────────────────

    def _pick_from_current_slot(self, state):
        cat      = state.current_category
        phase    = state.phase
        pass_num = state.category_pass

        if phase == AuctionState.PHASE_MAIN:
            if pass_num == 1:
                # Pass 1: only AVAILABLE
                pool = list(Player.objects.filter(status=Player.STATUS_AVAILABLE, role=cat))
            else:
                # Pass 2: AVAILABLE + UNSOLD (item 16)
                pool = list(Player.objects.filter(
                    role=cat,
                    status__in=[Player.STATUS_AVAILABLE, Player.STATUS_UNSOLD]
                ))
            return random.choice(pool) if pool else None

        elif phase == AuctionState.PHASE_REBID:
            pool = list(Player.objects.filter(status=Player.STATUS_UNSOLD, role=cat))
            return random.choice(pool) if pool else None

        return None

    # ─────────────────────────────────────────────
    # INTERNAL: set next transition when slot exhausted
    # (items 4, 10, 15, 16, 17)
    # ─────────────────────────────────────────────

    def _set_next_transition(self, state):
        config         = self.config
        cat            = state.current_category
        phase          = state.phase
        pass_num       = state.category_pass
        category_order = config.get_category_order() if config else ["AR", "BAT", "BOWL", "PLY"]
        base           = ROUND_DISPLAY.get(cat, cat)

        if phase == AuctionState.PHASE_MAIN and pass_num == 1:
            # Pass 1 exhausted
            all_have_one = self._all_teams_have_icon(cat) if cat in ICON_CATEGORIES else True
            unsold_exist = Player.objects.filter(status=Player.STATUS_UNSOLD, role=cat).exists()

            if not all_have_one and unsold_exist:
                # Rebid: some teams still need an icon
                state.phase         = AuctionState.PHASE_REBID
                state.auction_round += 1
                state.awaiting_transition = True
                state.transition_message  = f"{base} Pass 1 complete · Starting {base} Rebid"
                state.save()
                return

            # Check pass 2
            if cat in ICON_CATEGORIES:
                more_players = Player.objects.filter(
                    role=cat
                ).exclude(status__in=[Player.STATUS_NOT_PLAYING, Player.STATUS_SOLD]).exists()
                if more_players:
                    state.phase            = AuctionState.PHASE_MAIN
                    state.category_pass    = 2
                    state.auction_round   += 1
                    state.awaiting_transition = True
                    state.transition_message  = f"{base} Pass 1 complete · Starting {base} Pass 2"
                    state.save()
                    return

            # Move to next category
            self._transition_to_next_category(state, cat, category_order)

        elif phase == AuctionState.PHASE_REBID:
            # Rebid exhausted
            if cat in ICON_CATEGORIES and pass_num == 1:
                more_available = Player.objects.filter(
                    role=cat, status=Player.STATUS_AVAILABLE
                ).exists()
                if more_available:
                    state.phase            = AuctionState.PHASE_MAIN
                    state.category_pass    = 2
                    state.auction_round   += 1
                    state.awaiting_transition = True
                    state.transition_message  = f"{base} Rebid complete · Starting {base} Pass 2"
                    state.save()
                    return

            self._transition_to_next_category(state, cat, category_order)

        elif phase == AuctionState.PHASE_MAIN and pass_num == 2:
            # Pass 2 exhausted
            unsold_exist = Player.objects.filter(status=Player.STATUS_UNSOLD, role=cat).exists()
            if unsold_exist:
                state.phase            = AuctionState.PHASE_REBID
                state.auction_round   += 1
                state.awaiting_transition = True
                state.transition_message  = f"{base} Pass 2 complete · Starting {base} Rebid Pass 2"
                state.save()
                return

            self._transition_to_next_category(state, cat, category_order)

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
                state.phase            = AuctionState.PHASE_MAIN
                state.current_category = next_cat
                state.category_pass    = 1
                state.auction_round   += 1
                state.awaiting_transition = True
                state.transition_message  = f"{base_curr} Round complete · Starting {base_next} Round"
                state.save()
                return

        # All categories exhausted — pool empty, wait for admin
        state.awaiting_transition = False
        state.transition_message  = ""
        state.save()

    # ─────────────────────────────────────────────
    # PUBLIC: blocked teams (items 15, 16)
    # Pass 1 + rebid-pass-1 for icons: block teams with ≥1
    # Pass 2: no blocking
    # ─────────────────────────────────────────────

    def get_blocked_team_ids(self, state):
        cat      = state.current_category
        phase    = state.phase
        pass_num = state.category_pass

        if cat not in ICON_CATEGORIES:
            return set()

        # Block in pass 1 main AND rebid pass 1
        if pass_num == 1 and phase in (AuctionState.PHASE_MAIN, AuctionState.PHASE_REBID):
            blocked = Team.objects.filter(
                player__role=cat, player__status=Player.STATUS_SOLD
            ).distinct().values_list("team_serial_number", flat=True)
            return set(blocked)

        return set()

    # ─────────────────────────────────────────────
    # INTERNAL: check all teams have at least 1 of icon
    # ─────────────────────────────────────────────

    def _all_teams_have_icon(self, cat):
        total_teams    = Team.objects.count()
        teams_with_one = Team.objects.filter(
            player__role=cat, player__status=Player.STATUS_SOLD
        ).distinct().count()
        return teams_with_one >= total_teams

    # ─────────────────────────────────────────────
    # PUBLIC: clear current player after action
    # ─────────────────────────────────────────────

    def clear_current_player(self):
        state                = AuctionState.get()
        state.current_player = None
        state.save()

    # ─────────────────────────────────────────────
    # PUBLIC: restore player (undo)
    # ─────────────────────────────────────────────

    def restore_player(self, player):
        state                = AuctionState.get()
        state.current_player = player
        state.is_active      = True
        state.save()

    # ─────────────────────────────────────────────
    # PUBLIC: recalculate all team points from DB
    # (item 9 — refresh / fix double-count)
    # ─────────────────────────────────────────────

    def recalculate_points(self):
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

    # ─────────────────────────────────────────────
    # PUBLIC: reset auction
    # ─────────────────────────────────────────────

    def reset_auction(self):
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
