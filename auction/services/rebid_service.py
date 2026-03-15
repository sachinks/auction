"""
rebid_service.py
────────────────
Helpers for the rebid pool (unsold players).
"""
import random
import logging
import traceback

from auction.models import Player

logger = logging.getLogger("auction")


class RebidService:
    """Handles unsold player rebid rounds."""

    def get_unsold_players(self):
        try:
            return Player.objects.filter(status="UNSOLD")
        except Exception as e:
            logger.error(f"get_unsold_players error: {e}")
            return Player.objects.none()

    def rebid_pool_size(self):
        try:
            return self.get_unsold_players().count()
        except Exception as e:
            logger.error(f"rebid_pool_size error: {e}")
            return 0

    def get_random_rebid_player(self):
        try:
            players = list(self.get_unsold_players())
            if not players:
                return None
            return random.choice(players)
        except Exception as e:
            logger.error(f"get_random_rebid_player error: {e}")
            return None

    def reset_unsold_to_available(self):
        logger.info("reset_unsold_to_available called")
        try:
            players = self.get_unsold_players()
            count   = players.count()
            for p in players:
                p.status = "AVAILABLE"
                p.save()
            logger.info(f"reset_unsold_to_available: reset {count} players")
            return count
        except Exception as e:
            logger.error(f"reset_unsold_to_available error: {e}\n{traceback.format_exc()}")
            raise

    def clear_rebid_pool(self):
        logger.warning("clear_rebid_pool: unsold players → NOT_PLAYING")
        try:
            players = self.get_unsold_players()
            count   = players.count()
            for p in players:
                p.status = "NOT_PLAYING"
                p.save()
            logger.warning(f"clear_rebid_pool: {count} players set to NOT_PLAYING")
        except Exception as e:
            logger.error(f"clear_rebid_pool error: {e}\n{traceback.format_exc()}")
            raise
