import random

from auction.models import Player, Team, TournamentConfig


class AuctionEngine:


    def __init__(self):

        self.config = TournamentConfig.objects.first()


    # -------------------------------------------------
    # GET NEXT PLAYER
    # -------------------------------------------------

    def next_player(self):

        """
        Returns the next player to auction.

        Priority:
        1. AVAILABLE players
        2. If none, try UNSOLD rebid pool
        """

        player = Player.objects.filter(status="AVAILABLE").order_by("serial_number").first()

        if player:
            return player

        # try rebid pool
        rebid_players = Player.objects.filter(status="UNSOLD")

        if rebid_players.exists():
            return random.choice(rebid_players)

        return None


    # -------------------------------------------------
    # RESET AUCTION
    # -------------------------------------------------

    def reset_auction(self):

        """
        Clears all auction results but keeps teams and players
        """

        Player.objects.all().update(
            sold_price=None,
            team=None,
            status="AVAILABLE"
        )

        for team in Team.objects.all():

            if self.config:
                team.remaining_points = self.config.total_points
                team.save()


    # -------------------------------------------------
    # SAFE BID CHECK
    # -------------------------------------------------

    def safe_bid_allowed(self, team, bid_amount):

        if not self.config:
            return True

        remaining_points = team.remaining_points

        squad_size = team.player_set.count()

        remaining_slots = self.config.bidding_slots - squad_size

        min_price = min(
            self.config.base_price_AR,
            self.config.base_price_BAT,
            self.config.base_price_BOWL,
            self.config.base_price_PLY
        )

        minimum_required = remaining_slots * min_price

        if remaining_points - bid_amount < minimum_required:
            return False

        return True

    # -------------------------------------------------
    # ICON ROUND BALANCING (simplified)
    # -------------------------------------------------

    def icon_balanced(self, role):

        """
        Ensures teams receive one icon before second layer
        """

        teams = Team.objects.all()

        for team in teams:

            count = Player.objects.filter(
                team=team,
                role=role,
                status="SOLD"
            ).count()

            if count == 0:
                return False

        return True
