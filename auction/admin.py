from django.contrib import admin
from .models import (
    Player, Team, TournamentConfig, TournamentSettings,
    AuctionState, AuctionAction, Jersey, ExtraJerseyMember,
    TournamentPool, PoolTeam, Match,
)


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display  = ("serial_number", "name", "role", "place", "status", "team", "base_price", "sold_price")
    list_filter   = ("role", "status", "team")
    search_fields = ("name", "place")
    ordering      = ("role", "name")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display  = ("team_serial_number", "name", "short_name", "remaining_points", "owners")
    search_fields = ("name",)


@admin.register(TournamentConfig)
class TournamentConfigAdmin(admin.ModelAdmin):
    list_display = ("total_points", "bidding_slots", "max_squad_size",
                    "base_price_AR", "base_price_BAT", "base_price_BOWL", "base_price_PLY",
                    "category_order", "max_rebid_attempts")


@admin.register(AuctionAction)
class AuctionActionAdmin(admin.ModelAdmin):
    list_display  = ("timestamp", "action", "player", "team", "amount", "round")
    list_filter   = ("action",)
    ordering      = ("-timestamp",)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display  = ("match_number", "pool", "team1", "team2", "winner", "status")
    list_filter   = ("status", "pool")


@admin.register(Jersey)
class JerseyAdmin(admin.ModelAdmin):
    list_display  = ("player", "jersey_name", "jersey_number", "size_text", "sponsor")


admin.site.register(TournamentSettings)
admin.site.register(AuctionState)
admin.site.register(ExtraJerseyMember)
admin.site.register(TournamentPool)
admin.site.register(PoolTeam)
