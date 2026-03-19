"""
audit_service.py
────────────────
Audit log queries for the action log page.
"""
import logging
import traceback

from auction.models import AuctionAction

logger = logging.getLogger("system")


class AuditService:

    def record_action(self, player, team=None, action=None, amount=None, round_number=1):
        logger.debug(f"record_action: {action} player={player} team={team} amount={amount}")
        try:
            AuctionAction.objects.create(
                player=player, team=team,
                action=action, amount=amount, round=round_number,
            )
        except Exception as e:
            logger.error(f"record_action error: {e}\n{traceback.format_exc()}")
            raise

    def get_all_actions(self):
        try:
            return AuctionAction.objects.select_related("player", "team").order_by("-pk")
        except Exception as e:
            logger.error(f"get_all_actions error: {e}")
            return AuctionAction.objects.none()

    def get_last_action(self):
        try:
            return AuctionAction.objects.last()
        except Exception as e:
            logger.error(f"get_last_action error: {e}")
            return None

    def delete_last_action(self):
        logger.info("delete_last_action called")
        try:
            action = AuctionAction.objects.last()
            if action:
                action.delete()
        except Exception as e:
            logger.error(f"delete_last_action error: {e}\n{traceback.format_exc()}")
            raise

    def clear_log(self):
        logger.warning("clear_log called — all auction actions will be deleted")
        try:
            count = AuctionAction.objects.count()
            AuctionAction.objects.all().delete()
            logger.warning(f"clear_log: deleted {count} records")
        except Exception as e:
            logger.error(f"clear_log error: {e}\n{traceback.format_exc()}")
            raise
