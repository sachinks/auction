import random
from auction.models import Player


class RebidService:

    """
    Handles unsold player rebid rounds
    """

    def get_unsold_players(self):

        return Player.objects.filter(status="UNSOLD")

    def rebid_pool_size(self):

        return self.get_unsold_players().count()

    def get_random_rebid_player(self):

        players = list(self.get_unsold_players())

        if not players:
            return None

        return random.choice(players)

    def reset_unsold_to_available(self):

        players = self.get_unsold_players()

        for p in players:
            p.status = "AVAILABLE"
            p.save()

        return players.count()

    def clear_rebid_pool(self):

        players = self.get_unsold_players()

        for p in players:
            p.status = "NOT_PLAYING"
            p.save()
