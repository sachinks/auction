from auction.models import Player, Team, AuctionAction
from auction.services.auction_engine import AuctionEngine


class BiddingService:

    def __init__(self):
        self.engine = AuctionEngine()

    # ----------------------------------
    # SELL PLAYER
    # ----------------------------------

    def sell_player(self, player_id, team_id, amount):

        player = Player.objects.get(serial_number=player_id)
        team = Team.objects.get(team_serial_number=team_id)

        amount = int(amount)

        # Safe bidding rule
        if not self.engine.safe_bid_allowed(team, amount):
            raise Exception("Unsafe bid")

        player.team = team
        player.sold_price = amount
        player.status = "SOLD"
        player.save()

        team.remaining_points -= amount
        team.save()

        AuctionAction.objects.create(
            player=player,
            team=team,
            action="SELL",
            amount=amount
        )

    # ----------------------------------
    # UNSOLD
    # ----------------------------------

    def mark_unsold(self, player_id):

        player = Player.objects.get(serial_number=player_id)

        player.status = "UNSOLD"
        player.save()

        AuctionAction.objects.create(
            player=player,
            action="UNSOLD"
        )

    # ----------------------------------
    # NOT PLAYING
    # ----------------------------------

    def mark_not_playing(self, player_id):

        player = Player.objects.get(serial_number=player_id)

        player.status = "NOT_PLAYING"
        player.save()

        AuctionAction.objects.create(
            player=player,
            action="NOT_PLAYING"
        )

    # ----------------------------------
    # UNDO LAST ACTION
    # ----------------------------------

    def undo_last_action(self):

        action = AuctionAction.objects.last()

        if not action:
            return

        player = action.player

        if action.action == "SELL":

            team = action.team

            team.remaining_points += action.amount
            team.save()

            player.team = None
            player.sold_price = None
            player.status = "AVAILABLE"
            player.save()

        elif action.action == "UNSOLD":

            player.status = "AVAILABLE"
            player.save()

        elif action.action == "NOT_PLAYING":

            player.status = "AVAILABLE"
            player.save()

        action.delete()