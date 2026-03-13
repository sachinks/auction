from django.contrib import admin
from django.utils.html import format_html
from .models import Player, Team, TournamentConfig, TournamentSettings, AuctionAction, Jersey, ExtraJerseyMember, AuctionState, Match


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display       = ("serial_number", "name", "role", "place", "status_badge", "team", "sold_price", "rebid_count")
    list_display_links = ("name",)
    list_filter        = ("role", "status", "team")
    search_fields      = ("name", "place", "phone")
    ordering           = ("serial_number",)
    readonly_fields    = ("serial_number", "rebid_count")
    fieldsets = (
        ("Player Info", {"fields": ("serial_number", "name", "role", "place", "phone", "photo", "notes")}),
        ("Auction",     {"fields": ("base_price", "sold_price", "team", "status", "rebid_count")}),
    )

    def status_badge(self, obj):
        colours = {
            "AVAILABLE":   ("#1a5c38", "#2ecc71"),
            "SOLD":        ("#0a2a4a", "#3498db"),
            "UNSOLD":      ("#6b3800", "#f39c12"),
            "NOT_PLAYING": ("#2a2a2a", "#888888"),
        }
        bg, fg = colours.get(obj.status, ("#333", "#fff"))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold;">{}</span>',
            bg, fg, obj.status
        )
    status_badge.short_description = "Status"


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display       = ("team_serial_number", "name", "short_name", "owners", "remaining_points")
    list_display_links = ("name",)
    ordering           = ("team_serial_number",)


@admin.register(TournamentConfig)
class TournamentConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "total_points", "bidding_slots", "max_squad_size", "created_at")


@admin.register(AuctionAction)
class AuctionActionAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "player", "action", "team", "amount", "category", "round")
    list_filter  = ("action", "category")
    ordering     = ("-timestamp",)


@admin.register(AuctionState)
class AuctionStateAdmin(admin.ModelAdmin):
    list_display = ("id", "phase", "current_category", "category_pass", "auction_round",
                    "is_active", "awaiting_transition", "current_player", "updated_at")


@admin.register(Jersey)
class JerseyAdmin(admin.ModelAdmin):
    list_display = ("player", "jersey_name", "jersey_number", "size_text", "sponsor")
    ordering     = ("jersey_number",)


@admin.register(TournamentSettings)
class TournamentSettingsAdmin(admin.ModelAdmin):
    list_display = ("tournament_name", "auction_date", "match_date", "banner_path")
    fieldsets = (
        (None, {"fields": ("tournament_name", "auction_date", "match_date", "banner_path")}),
    )


@admin.register(ExtraJerseyMember)
class ExtraJerseyMemberAdmin(admin.ModelAdmin):
    list_display  = ("name", "role_label", "member_type", "team", "group_name", "jersey_name", "jersey_number")
    list_filter   = ("member_type", "team")
    search_fields = ("name", "role_label", "group_name")
    ordering      = ("member_type", "team__name", "name")


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display  = ("match_number", "round_label", "team1", "team2", "winner", "status", "scheduled_date", "venue")
    list_filter   = ("status", "round_label")
    ordering      = ("match_number",)
