from django.contrib import admin
from .models import (
    Player, Team, TournamentConfig, TournamentSettings,
    AuctionState, AuctionAction, Jersey, ExtraJerseyMember,
    TournamentPool, PoolTeam, Match,
)

admin.site.register(Player)
admin.site.register(Team)
admin.site.register(TournamentConfig)
admin.site.register(TournamentSettings)
admin.site.register(AuctionState)
admin.site.register(AuctionAction)
admin.site.register(Jersey)
admin.site.register(ExtraJerseyMember)
admin.site.register(TournamentPool)
admin.site.register(PoolTeam)
admin.site.register(Match)
