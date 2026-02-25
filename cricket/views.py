import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages

from cricket.models import Team, Player
from cricket.services.auction_engine import AuctionEngine
from cricket.exceptions import AuctionBaseException

logger = logging.getLogger("cricket")


# =====================================================
# PUBLIC VIEWS
# =====================================================

def welcome_view(request):
    logger.info("Welcome page accessed.")
    return render(request, "cricket/welcome.html")


def live_board_view(request):
    try:
        control = AuctionEngine.get_control()
        teams = Team.objects.all()

        logger.info("Live board viewed. Stage=%s", control.current_stage)

        return render(request, "cricket/live_board.html", {
            "control": control,
            "teams": teams,
        })

    except Exception as e:
        logger.error("Live board error: %s", str(e))
        messages.error(request, "Unable to load live board.")
        return redirect("welcome")


# =====================================================
# TEAM STATUS PAGE
# =====================================================

def team_status(request):
    try:
        teams = Team.objects.all()
        logger.info("Team status page accessed.")
        return render(request, "cricket/team_status.html", {"teams": teams})

    except Exception as e:
        logger.error("Team status error: %s", str(e))
        messages.error(request, "Unable to load team status.")
        return redirect("welcome")


# =====================================================
# RESET AUCTION
# =====================================================

@staff_member_required
def reset_auction(request):
    try:
        logger.info("Reset auction page accessed by %s", request.user)
        return render(request, "cricket/reset_auction.html")

    except Exception as e:
        logger.error("Reset auction view error: %s", str(e))
        messages.error(request, "Unable to load reset page.")
        return redirect("welcome")


# =====================================================
# OLD MANUAL AUCTION VIEW (IMPORTANT UPDATE)
# =====================================================

@staff_member_required
def auction_player(request, player_id):
    try:
        player = get_object_or_404(Player, id=player_id)
        teams = Team.objects.all()

        logger.info(
            "Auction page accessed for player=%s by %s",
            player.name,
            request.user
        )

        if request.method == "POST":
            try:
                team_id = int(request.POST.get("team_id"))
                price = int(request.POST.get("price"))

                AuctionEngine.sell_current_player(
                    team_id=team_id,
                    price=price,
                    admin_user=request.user
                )

                logger.info(
                    "Manual auction sale: %s sold by %s",
                    player.name,
                    request.user
                )

                messages.success(request, "Player sold successfully.")
                return redirect("team_status")

            except AuctionBaseException as e:
                logger.warning(
                    "Business validation error during manual auction: %s",
                    str(e)
                )
                messages.error(request, str(e))

            except Exception as e:
                logger.error(
                    "Unexpected error in manual auction: %s",
                    str(e)
                )
                messages.error(request, "Invalid input or unexpected error.")

        return render(request, "cricket/auction_player.html", {
            "player": player,
            "teams": teams,
        })

    except Exception as e:
        logger.error("Auction player view failure: %s", str(e))
        messages.error(request, "Unable to load auction page.")
        return redirect("team_status")


# =====================================================
# ADMIN CONTROL PANEL
# =====================================================

@staff_member_required
def control_panel_view(request):
    try:
        control = AuctionEngine.get_control()
        teams = Team.objects.all()

        logger.info("Control panel accessed by %s", request.user)

        return render(request, "cricket/control_panel.html", {
            "control": control,
            "teams": teams,
        })

    except Exception as e:
        logger.error("Control panel error: %s", str(e))
        messages.error(request, "Unable to load control panel.")
        return redirect("welcome")


# =====================================================
# CONTROL ACTIONS
# =====================================================

@staff_member_required
def start_auction_view(request):
    if request.method == "POST":
        try:
            AuctionEngine.start_auction()
            logger.info("Auction started by %s", request.user)
            messages.success(request, "Auction started.")
        except AuctionBaseException as e:
            logger.warning("Start auction validation error: %s", str(e))
            messages.error(request, str(e))
        except Exception as e:
            logger.error("Start auction unexpected error: %s", str(e))
            messages.error(request, "Unexpected error occurred.")

    return redirect("control_panel")


@staff_member_required
def pick_player_view(request):
    if request.method == "POST":
        try:
            player = AuctionEngine.pick_random_player()
            logger.info("Player picked: %s by %s", player.name, request.user)
            messages.success(request, "Player picked.")
        except AuctionBaseException as e:
            logger.warning("Pick validation error: %s", str(e))
            messages.error(request, str(e))
        except Exception as e:
            logger.error("Pick unexpected error: %s", str(e))
            messages.error(request, "Unexpected error occurred.")

    return redirect("control_panel")


@staff_member_required
def sell_player_view(request):
    if request.method == "POST":
        try:
            team_id = int(request.POST.get("team_id"))
            price = int(request.POST.get("price"))

            AuctionEngine.sell_current_player(
                team_id=team_id,
                price=price,
                admin_user=request.user
            )

            logger.info(
                "Player sold via control panel by %s",
                request.user
            )

            messages.success(request, "Player sold.")

        except AuctionBaseException as e:
            logger.warning("Sell validation error: %s", str(e))
            messages.error(request, str(e))
        except Exception as e:
            logger.error("Sell unexpected error: %s", str(e))
            messages.error(request, "Invalid input.")

    return redirect("control_panel")


@staff_member_required
def mark_unsold_view(request):
    if request.method == "POST":
        try:
            AuctionEngine.mark_unsold(admin_user=request.user)
            logger.info("Marked unsold by %s", request.user)
            messages.success(request, "Marked unsold.")
        except AuctionBaseException as e:
            logger.warning("Unsold validation error: %s", str(e))
            messages.error(request, str(e))
        except Exception as e:
            logger.error("Unsold unexpected error: %s", str(e))
            messages.error(request, "Unexpected error.")

    return redirect("control_panel")


@staff_member_required
def mark_not_playing_view(request):
    if request.method == "POST":
        try:
            AuctionEngine.mark_not_playing(admin_user=request.user)
            logger.info("Marked not playing by %s", request.user)
            messages.success(request, "Marked not playing.")
        except AuctionBaseException as e:
            logger.warning("Not playing validation error: %s", str(e))
            messages.error(request, str(e))
        except Exception as e:
            logger.error("Not playing unexpected error: %s", str(e))
            messages.error(request, "Unexpected error.")

    return redirect("control_panel")


@staff_member_required
def undo_last_view(request):
    if request.method == "POST":
        try:
            AuctionEngine.undo_last_action()
            logger.info("Undo performed by %s", request.user)
            messages.success(request, "Undo successful.")
        except AuctionBaseException as e:
            logger.warning("Undo validation error: %s", str(e))
            messages.error(request, str(e))
        except Exception as e:
            logger.error("Undo unexpected error: %s", str(e))
            messages.error(request, "Unexpected error.")

    return redirect("control_panel")