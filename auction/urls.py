from django.urls import path
from . import views

urlpatterns = [
    path("",                            views.public_board,       name="public_board"),
    path("auction/",                    views.auction_control,    name="auction_control"),
    path("auction/start/",              views.start_auction,      name="start_auction"),
    path("auction/next/",               views.next_player,        name="next_player"),
    path("auction/continue/",           views.confirm_transition, name="confirm_transition"),
    path("auction/sell/",               views.sell_player,        name="sell_player"),
    path("auction/unsold/",             views.unsold_player,      name="unsold_player"),
    path("auction/not-playing/",        views.not_playing_player, name="not_playing_player"),
    path("auction/undo/",               views.undo_action,        name="undo_action"),
    path("auction/refresh/",            views.refresh_points,     name="refresh_points"),
    path("auction/complete/",           views.complete_auction,   name="complete_auction"),
    path("auction/summary/",            views.auction_summary,    name="auction_summary"),
    path("auction/upload-csv/",         views.upload_csv,         name="upload_csv"),
    path("auction/audit-log/",          views.audit_log,          name="audit_log"),
    path("auction/banner/",             views.banner_upload,      name="banner_upload"),
    path("auction/reset/",              views.reset_auction,      name="reset_auction"),   # hidden
    path("jersey/",                     views.jersey_portal,      name="jersey_portal"),
    path("jersey/pdf/",                 views.export_jersey_pdf,  name="jersey_pdf"),
    path("jersey/save/",                views.jersey_save_ajax,   name="jersey_save_ajax"),
    path("fixtures/",                   views.fixtures_admin,     name="fixtures_admin"),
    path("fixtures/public/",            views.fixtures_public,    name="fixtures_public"),
    path("fixtures/spin/",              views.spin_result,        name="spin_result"),
]
