from django.contrib import admin
from .models import Team, Player


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'remaining_points', 'players_needed')


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'place', 'mobile_number', 'team', 'sold_price')
    search_fields = ('name', 'place')