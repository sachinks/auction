from django.urls import path
from . import views


urlpatterns = [

    path("", views.public_board, name="public_board"),

    path("auction/", views.auction_control, name="auction_control"),

    path("auction/start/", views.start_auction, name="start_auction"),

    path("auction/sell/", views.sell_player, name="sell_player"),

    path("auction/unsold/", views.unsold_player, name="unsold_player"),

    path("auction/not-playing/", views.not_playing_player, name="not_playing_player"),

    path("auction/undo/", views.undo_action, name="undo_action"),

    path("auction/upload-csv/", views.upload_csv, name="upload_csv"),

    path("auction/audit-log/", views.audit_log, name="audit_log"),

    path("auction/reset/", views.reset_auction, name="reset_auction"),

    path("jersey/", views.jersey_portal, name="jersey_portal"),

    path("jersey/pdf/", views.export_jersey_pdf, name="jersey_pdf"),
]