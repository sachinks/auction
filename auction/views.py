from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Player, Team, TournamentConfig, Jersey

from .services.auction_engine import AuctionEngine
from .services.bidding_service import BiddingService
from .services.csv_service import CSVService
from .services.audit_service import AuditService
from .services.jersey_service import JerseyService

from .utils.bid_utils import bid_increment
from .utils.team_utils import short_name


# ------------------------------------------------
# PUBLIC BOARD
# ------------------------------------------------

def public_board(request):

    config = TournamentConfig.objects.first()

    teams = Team.objects.all()

    player = None

    if config:
        engine = AuctionEngine()
        player = engine.next_player()

    return render(
        request,
        "public_board.html",
        {
            "player": player,
            "teams": teams,
            "auction_started": bool(config),
        },
    )

# ------------------------------------------------
# AUCTION CONTROL PAGE
# ------------------------------------------------

def auction_control(request):

    config = TournamentConfig.objects.first()

    # If config not created show setup page
    if not config:
        return render(request, "auction_setup.html")

    engine = AuctionEngine()

    player = engine.next_player()

    teams = Team.objects.all()

    increment = bid_increment()

    for t in teams:
        t.short = short_name(t.name)

    context = {
        "player": player,
        "teams": teams,
        "increment": increment,
    }

    return render(request, "auction_control.html", context)


# ------------------------------------------------
# START AUCTION (CREATE CONFIG)
# ------------------------------------------------

def start_auction(request):

    if request.method == "POST":

        total_points = int(request.POST.get("total_points"))

        config = TournamentConfig.objects.create(
            total_points=total_points,
            bidding_slots=request.POST.get("bidding_slots"),
            max_squad_size=request.POST.get("max_squad_size"),
            base_price_AR=request.POST.get("base_price_AR"),
            base_price_BAT=request.POST.get("base_price_BAT"),
            base_price_BOWL=request.POST.get("base_price_BOWL"),
            base_price_PLY=request.POST.get("base_price_PLY"),
        )

        # Initialize team wallets
        teams = Team.objects.all()

        for team in teams:
            team.remaining_points = total_points
            team.save()

    return redirect("/auction/")


# ------------------------------------------------
# SELL PLAYER
# ------------------------------------------------

@csrf_exempt
def sell_player(request):

    if request.method == "POST":

        service = BiddingService()

        player_id = request.POST.get("player_id")
        team_id = request.POST.get("team_id")
        amount = request.POST.get("amount")

        service.sell_player(player_id, team_id, amount)

        return JsonResponse({"status": "ok"})

    return JsonResponse({"status": "invalid"})


# ------------------------------------------------
# UNSOLD PLAYER
# ------------------------------------------------

@csrf_exempt
def unsold_player(request):

    if request.method == "POST":

        service = BiddingService()

        player_id = request.POST.get("player_id")

        service.mark_unsold(player_id)

        return JsonResponse({"status": "ok"})

    return JsonResponse({"status": "invalid"})


# ------------------------------------------------
# NOT PLAYING
# ------------------------------------------------

@csrf_exempt
def not_playing_player(request):

    if request.method == "POST":

        service = BiddingService()

        player_id = request.POST.get("player_id")

        service.mark_not_playing(player_id)

        return JsonResponse({"status": "ok"})

    return JsonResponse({"status": "invalid"})


# ------------------------------------------------
# UNDO LAST ACTION
# ------------------------------------------------

def undo_action(request):

    service = BiddingService()

    service.undo_last_action()

    return redirect("/auction/")


# ------------------------------------------------
# CSV IMPORT
# ------------------------------------------------

def upload_csv(request):

    csv_service = CSVService()

    if request.method == "POST":

        uploaded_file = request.FILES["file"]

        path = "players.csv"

        with open(path, "wb+") as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        created, errors = csv_service.import_players(path)

        return render(
            request,
            "upload_csv.html",
            {
                "created": created,
                "errors": errors,
            },
        )

    return render(request, "upload_csv.html")


# ------------------------------------------------
# AUDIT LOG PAGE
# ------------------------------------------------

def audit_log(request):

    audit_service = AuditService()

    actions = audit_service.get_all_actions()

    return render(
        request,
        "audit_log.html",
        {
            "actions": actions
        },
    )


# ------------------------------------------------
# RESET AUCTION
# ------------------------------------------------

def reset_auction(request):

    engine = AuctionEngine()

    engine.reset_auction()

    return redirect("/auction/")


# ------------------------------------------------
# JERSEY PORTAL
# ------------------------------------------------

def jersey_portal(request):

    jerseys = Jersey.objects.select_related("player").all()

    return render(
        request,
        "jersey_management.html",
        {
            "jerseys": jerseys
        },
    )


# ------------------------------------------------
# EXPORT JERSEY PDF
# ------------------------------------------------

def export_jersey_pdf(request):

    jersey_service = JerseyService()

    pdf_buffer = jersey_service.export_pdf()

    response = HttpResponse(pdf_buffer, content_type="application/pdf")

    response["Content-Disposition"] = "attachment; filename=jersey_list.pdf"

    return response