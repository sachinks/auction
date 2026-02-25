from django.urls import path
from .views import *

urlpatterns = [
    path("start/", StartAuctionView.as_view()),
    path("pick/", PickPlayerView.as_view()),
    path("sell/", SellPlayerView.as_view()),
    path("unsold/", MarkUnsoldView.as_view()),
    path("not-playing/", MarkNotPlayingView.as_view()),
    path("undo/", UndoView.as_view()),
    path("enable-rebid/", EnableRebidView.as_view()),
    path("disable-rebid/", DisableRebidView.as_view()),
    path("status/", AuctionStatusView.as_view()),
    path("teams/", TeamListView.as_view()),
]