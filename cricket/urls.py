from django.urls import path
from . import views

urlpatterns = [
    # Existing
    path('teams/', views.team_status, name='team_status'),
    path('auction/<int:player_id>/', views.auction_player, name='auction_player'),
    path('reset-auction/', views.reset_auction, name='reset_auction'),

    # Public UI
    path('', views.welcome_view, name='welcome'),
    path('auction/live/', views.live_board_view, name='live_board'),

    # Admin Control
    path('auction/control/', views.control_panel_view, name='control_panel'),
    path('auction/start/', views.start_auction_view, name='start'),
    path('auction/pick/', views.pick_player_view, name='pick'),
    path('auction/sell/', views.sell_player_view, name='sell'),
    path('auction/unsold/', views.mark_unsold_view, name='unsold'),
    path('auction/not-playing/', views.mark_not_playing_view, name='not_playing'),
    path('auction/undo/', views.undo_last_view, name='undo'),
]