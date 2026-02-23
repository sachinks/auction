from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import Player, Team


def team_status(request):
    teams = Team.objects.all().prefetch_related('player_set')
    return render(request, 'cricket/team_status.html', {'teams': teams})

@staff_member_required
def auction_player(request, player_id):
    player = get_object_or_404(Player, id=player_id)
    teams = Team.objects.all()

    if request.method == "POST":
        team_id = request.POST.get("team")
        sold_price = request.POST.get("sold_price")

        if team_id and sold_price:
            player.team = Team.objects.get(id=team_id)
            player.sold_price = int(sold_price)
            player.save()
            return redirect("team_status")

    return render(request, "cricket/auction_player.html", {
        "player": player,
        "teams": teams
    })

@staff_member_required
def reset_auction(request):

    if request.method == "POST":

        # Reset all teams
        for team in Team.objects.all():
            team.remaining_points = team.total_points
            team.players_needed = team.max_players
            team.save()

        # Reset all players
        Player.objects.update(team=None, sold_price=None)

        messages.success(request, "Auction reset successfully!")

        return redirect("team_status")

    return render(request, "cricket/reset_auction.html")

