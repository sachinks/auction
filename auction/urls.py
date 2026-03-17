from django.urls import path
from . import views

urlpatterns = [

    # ── Public ───────────────────────────────────────────────
    path("",                             views.public_board,          name="public_board"),

    # ── Auction control ──────────────────────────────────────
    path("auction/",                     views.auction_control,       name="auction_control"),
    path("auction/start/",               views.start_auction,         name="start_auction"),
    path("auction/next/",                views.next_player,           name="next_player"),
    path("auction/continue/",            views.confirm_transition,    name="confirm_transition"),
    path("auction/sell/",                views.sell_player,           name="sell_player"),
    path("auction/unsold/",              views.unsold_player,         name="unsold_player"),
    path("auction/not-playing/",         views.not_playing_player,    name="not_playing_player"),
    path("auction/undo/",                views.undo_action,           name="undo_action"),
    path("auction/refresh/",             views.refresh_points,        name="refresh_points"),
    path("auction/complete/",            views.complete_auction,      name="complete_auction"),
    path("auction/summary/",             views.auction_summary,       name="auction_summary"),
    path("auction/banner/",              views.banner_upload,         name="banner_upload"),
    path("auction/reset/",               views.reset_auction,         name="reset_auction"),

    # ── CSV / data import ────────────────────────────────────
    path("auction/upload-csv/",          views.upload_csv,            name="upload_csv"),
    path("auction/load-sample/",         views.load_sample_data,      name="load_sample_data"),
    path("auction/sample-csv/<str:name>/", views.download_sample_csv, name="download_sample_csv"),

    # ── Audit log ────────────────────────────────────────────
    path("auction/audit-log/",           views.audit_log,             name="audit_log"),
    path("auction/debug/",               views.debug_state,           name="debug_state"),

    # ── Jersey ───────────────────────────────────────────────
    path("jersey/",                      views.jersey_portal,         name="jersey_portal"),
    path("jersey/save/",                 views.jersey_save_ajax,      name="jersey_save_ajax"),
    path("jersey/size-mapping/",         views.update_size_mapping,   name="update_size_mapping"),
    path("jersey/pdf/",                  views.export_jersey_pdf,     name="jersey_pdf"),

    # ── Old fixture URLs → redirect to pool manager ─────────
    path("fixtures/",                    views.fixtures_redirect,     name="fixtures_admin"),
    path("fixtures/public/",             views.fixtures_redirect,     name="fixtures_public"),

    # ── Pools + unified fixture page ─────────────────────────
    path("fixtures/pools/",              views.pool_manager,          name="pool_manager"),
    path("fixtures/pools/create/",       views.pool_create,           name="pool_create"),
    path("fixtures/pools/reset/",        views.pool_reset,            name="pool_reset"),
    path("fixtures/pools/generate/",     views.pool_generate_matches, name="pool_generate"),
    path("fixtures/pools/generate-all/", views.pool_generate_all,     name="pool_generate_all"),
    path("fixtures/pools/advance/",      views.pool_advance,          name="pool_advance"),
    path("fixtures/pools/team-add/",     views.pool_team_add,         name="pool_team_add"),
    path("fixtures/pools/team-remove/",  views.pool_team_remove,      name="pool_team_remove"),
    path("fixtures/pools/spin-assign/",  views.pool_spin_assign,      name="pool_spin_assign"),
    path("fixtures/pools/result/",       views.pool_record_result,    name="pool_record_result"),
    path("fixtures/knockout/",           views.knockout_create,       name="knockout_create"),

    # ── Fixture draw + results ───────────────────────────────
    path("fixtures/draw/",               views.fixture_draw_view,     name="fixture_draw"),
    path("fixtures/draw/generate/",      views.generate_fixtures,     name="generate_fixtures"),
    path("fixtures/draw/spin-next/",     views.fixture_spin_next,     name="fixture_spin_next"),
    path("fixtures/draw/reset/",         views.fixtures_reset,        name="fixtures_reset"),
    path("fixtures/draw/result/",        views.fixture_record_result, name="fixture_record_result"),

    # ── Reports ──────────────────────────────────────────────
    path("reports/",                     views.reports_page,          name="reports_page"),
    path("reports/download/",            views.report_download,       name="report_download"),
]
