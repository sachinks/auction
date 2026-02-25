import logging
import random

from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from cricket.models import Player, Team, AuctionControl, AuctionLog
from cricket.exceptions import (
    AuctionBaseException,
    AuctionValidationException,
)

logger = logging.getLogger("cricket")


class AuctionEngine:

    # =====================================================
    # CONTROL
    # =====================================================

    @staticmethod
    def get_control():
        try:
            control, _ = AuctionControl.objects.get_or_create(id=1)
            return control
        except Exception as e:
            logger.error("Error getting AuctionControl: %s", str(e))
            raise AuctionBaseException("Unable to access auction control.")


    @staticmethod
    def start_auction():
        try:
            control = AuctionEngine.get_control()

            if control.is_started:
                logger.warning("Auction start attempted but already started.")
                raise AuctionValidationException("Auction already started.")

            control.is_started = True
            control.current_stage = "BAT"
            control.save()

            logger.info("Auction started successfully.")
            return control

        except AuctionBaseException:
            raise
        except Exception as e:
            logger.error("Unexpected error starting auction: %s", str(e))
            raise AuctionBaseException("Failed to start auction.")


    # =====================================================
    # PICK RANDOM PLAYER
    # =====================================================

    @staticmethod
    def pick_random_player():
        try:
            control = AuctionEngine.get_control()

            if not control.is_started:
                logger.warning("Pick attempted before auction start.")
                raise AuctionValidationException("Auction not started yet.")

            players = Player.objects.filter(
                status="UNSOLD",
                team__isnull=True
            )

            if not players.exists():
                logger.warning("No unsold players available.")
                raise AuctionValidationException("No players remaining.")

            player = random.choice(players)

            control.current_player = player
            control.save()

            logger.info("Player picked: %s (ID=%s)", player.name, player.id)
            return player

        except AuctionBaseException:
            raise
        except Exception as e:
            logger.error("Unexpected error picking player: %s", str(e))
            raise AuctionBaseException("Failed to pick player.")


    # =====================================================
    # SELL CURRENT PLAYER
    # =====================================================

    @staticmethod
    @transaction.atomic
    def sell_current_player(team_id, price, admin_user):
        try:
            control = AuctionEngine.get_control()

            if not control.current_player:
                logger.warning("Sell attempted with no current player.")
                raise AuctionValidationException("No player selected.")

            player = control.current_player

            try:
                team = Team.objects.get(id=team_id)
            except ObjectDoesNotExist:
                logger.warning("Invalid team ID: %s", team_id)
                raise AuctionValidationException("Invalid team selected.")

            if price <= 0:
                logger.warning("Invalid sell price: %s", price)
                raise AuctionValidationException("Invalid selling price.")

            if team.remaining_points < price:
                logger.warning(
                    "Insufficient budget. Team=%s Remaining=%s Price=%s",
                    team.name,
                    team.remaining_points,
                    price
                )
                raise AuctionValidationException("Not enough points.")

            # Update team
            team.remaining_points -= price
            team.auction_slots -= 1
            team.save()

            # Update player
            player.team = team
            player.sold_price = price
            player.status = "SOLD"
            player.save()

            # Create audit log
            AuctionLog.objects.create(
                player=player,
                team=team,
                action_type="SOLD",
                price=price,
                performed_by=admin_user
            )

            control.current_player = None
            control.save()

            logger.info(
                "Player SOLD: %s to %s for %s by %s",
                player.name,
                team.name,
                price,
                admin_user
            )

            return player

        except AuctionBaseException:
            raise
        except Exception as e:
            logger.error("Unexpected sell error: %s", str(e))
            raise AuctionBaseException("Failed to sell player.")


    # =====================================================
    # MARK UNSOLD
    # =====================================================

    @staticmethod
    @transaction.atomic
    def mark_unsold(admin_user):
        try:
            control = AuctionEngine.get_control()

            if not control.current_player:
                logger.warning("Unsold attempted with no current player.")
                raise AuctionValidationException("No player selected.")

            player = control.current_player
            player.status = "UNSOLD"
            player.save()

            AuctionLog.objects.create(
                player=player,
                action_type="UNSOLD",
                performed_by=admin_user
            )

            control.current_player = None
            control.save()

            logger.info("Player marked UNSOLD: %s", player.name)
            return player

        except AuctionBaseException:
            raise
        except Exception as e:
            logger.error("Unexpected unsold error: %s", str(e))
            raise AuctionBaseException("Failed to mark unsold.")


    # =====================================================
    # MARK NOT PLAYING
    # =====================================================

    @staticmethod
    @transaction.atomic
    def mark_not_playing(admin_user):
        try:
            control = AuctionEngine.get_control()

            if not control.current_player:
                logger.warning("Not playing attempted with no current player.")
                raise AuctionValidationException("No player selected.")

            player = control.current_player
            player.status = "NOT_PLAYING"
            player.save()

            AuctionLog.objects.create(
                player=player,
                action_type="NOT_PLAYING",
                performed_by=admin_user
            )

            control.current_player = None
            control.save()

            logger.info("Player marked NOT_PLAYING: %s", player.name)
            return player

        except AuctionBaseException:
            raise
        except Exception as e:
            logger.error("Unexpected not playing error: %s", str(e))
            raise AuctionBaseException("Failed to mark not playing.")


    # =====================================================
    # UNDO LAST ACTION
    # =====================================================

    @staticmethod
    @transaction.atomic
    def undo_last_action():
        try:
            last_log = AuctionLog.objects.order_by("-id").first()

            if not last_log:
                logger.warning("Undo attempted but no logs found.")
                raise AuctionValidationException("No action to undo.")

            if last_log.action_type != "SOLD":
                logger.warning("Undo attempted for non-SOLD action.")
                raise AuctionValidationException(
                    "Only SOLD actions can be undone."
                )

            player = last_log.player
            team = last_log.team

            # Restore team
            team.remaining_points += last_log.price
            team.auction_slots += 1
            team.save()

            # Restore player
            player.team = None
            player.sold_price = None
            player.status = "UNSOLD"
            player.save()

            last_log.delete()

            logger.info("Undo successful for player: %s", player.name)
            return player

        except AuctionBaseException:
            raise
        except Exception as e:
            logger.error("Unexpected undo error: %s", str(e))
            raise AuctionBaseException("Failed to undo action.")