from django.contrib import admin
from .models import (
    Team,
    Player,
    AuctionControl,
    AuctionLog,
    JerseyProfile,
)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "total_points",
        "remaining_points",
        "max_players",
        "auction_slots",
    )
    list_display_links = ("name",)
    search_fields = ("name",)


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = (
        "serial_number",
        "name",
        "role",
        "status",
        "team",
        "sold_price",
    )
    list_display_links = ("name",)
    list_filter = ("role", "status")
    search_fields = ("name", "serial_number")


@admin.register(AuctionControl)
class AuctionControlAdmin(admin.ModelAdmin):
    list_display = (
        "is_started",
        "current_stage",
        "current_player",
        "is_rebid",
        "is_parked",
    )


@admin.register(AuctionLog)
class AuctionLogAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "action_type",
        "player",
        "team",
        "sold_price",
        "stage",
    )
    list_filter = ("action_type", "stage")


@admin.register(JerseyProfile)
class JerseyProfileAdmin(admin.ModelAdmin):
    list_display = (
        "player",
        "name_on_jersey",
        "jersey_number",
        "size_number",
        "size_text",
        "sponsor_name",
    )