from auction.models import AuctionAction


class AuditService:


    # -------------------------------------
    # RECORD AUCTION ACTION
    # -------------------------------------

    def record_action(self, player, team=None, action=None, amount=None, round_number=1):

        AuctionAction.objects.create(
            player=player,
            team=team,
            action=action,
            amount=amount,
            round=round_number
        )


    # -------------------------------------
    # GET ALL ACTIONS
    # -------------------------------------

    def get_all_actions(self):

        return AuctionAction.objects.order_by("-timestamp")


    # -------------------------------------
    # GET LAST ACTION
    # -------------------------------------

    def get_last_action(self):

        return AuctionAction.objects.last()


    # -------------------------------------
    # DELETE LAST ACTION
    # -------------------------------------

    def delete_last_action(self):

        action = AuctionAction.objects.last()

        if action:
            action.delete()


    # -------------------------------------
    # CLEAR AUDIT LOG
    # -------------------------------------

    def clear_log(self):

        AuctionAction.objects.all().delete()