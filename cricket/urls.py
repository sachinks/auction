from django.urls import path
from . import views

urlpatterns = [
    path('teams/', views.team_status, name='team_status'),
    path('auction/<int:player_id>/', views.auction_player, name='auction_player'),
    path('reset-auction/', views.reset_auction, name='reset_auction'),
]