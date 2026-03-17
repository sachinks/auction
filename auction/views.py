import os
import traceback

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from .models import Player, Team, TournamentConfig, TournamentSettings, Jersey, ExtraJerseyMember, AuctionState, AuctionAction, Match, TournamentPool, PoolTeam
from .services.auction_engine import AuctionEngine, round_label
from .services.bidding_service import BiddingService
from .services.csv_service import CSVService
from .services.audit_service import AuditService
from .services.jersey_service import JerseyService
from .utils.bid_utils import bid_increment
from .services.fixture_service import (
    all_pools_status, suggest_pool_config, pool_points_table,
    detect_ties, advance_teams, get_advanced_teams,
    create_group_stage, create_knockout_stage, get_interleaved_schedule,
    generate_pool_matches, add_team_to_pool, remove_team_from_pool,
    next_pool_for_draw, pool_undrawn_pairs, create_interleaved_match,
    _renumber_matches, generate_next_match,
)

from config.logging_config import auction_logger, error_logger, system_logger
from config.error_settings import api_error_response


# ────────────────────────────────────────────────
# PUBLIC BOARD
# ────────────────────────────────────────────────

def public_board(request):
    auction_logger.debug(f"public_board: user={request.user.is_authenticated}")
    state    = AuctionState.get()
    config   = TournamentConfig.objects.first()
    ts       = TournamentSettings.get()   # always exists
    teams    = Team.objects.all()

    # Build jersey lookup: player_id → jersey object
    jersey_map = {}
    for j in Jersey.objects.select_related("player").all():
        jersey_map[j.player_id] = j

    for team in teams:
        players = Player.objects.filter(
            team=team, status=Player.STATUS_SOLD
        ).order_by("role", "name")
        for p in players:
            p.jersey = jersey_map.get(p.serial_number)
        team.sold_players = players

    # Pre-auction player list: shown whenever auction has not started
    # (config doesn't exist yet OR auction state is not active)
    # Show player list before auction starts; hide when auction running or complete
    show_player_list = (not config) or (not state.is_active and state.phase != AuctionState.PHASE_DONE)
    pre_auction_players = None
    if show_player_list:
        pre_auction_players = {
            "AR":   list(Player.objects.filter(role="AR").order_by("name")),
            "BAT":  list(Player.objects.filter(role="BAT").order_by("name")),
            "BOWL": list(Player.objects.filter(role="BOWL").order_by("name")),
            "PLY":  list(Player.objects.filter(role="PLY").order_by("name")),
        }

    available_count = 0
    unsold_count    = 0
    if config and state.phase != AuctionState.PHASE_DONE:
        cat             = state.current_category
        available_count = Player.objects.filter(status=Player.STATUS_AVAILABLE, role=cat).count()
        unsold_count    = Player.objects.filter(status=Player.STATUS_UNSOLD,    role=cat).count()

    banner_url = None
    if ts.banner_path:
        banner_url = settings.MEDIA_URL + "banners/" + ts.banner_path

    # Fixtures for post-auction public display
    pools_data       = []
    interleaved_sched = []
    any_match_played  = False

    if state.phase == AuctionState.PHASE_DONE:
        group_pools = TournamentPool.objects.filter(
            stage=TournamentPool.STAGE_GROUP
        ).order_by("order").prefetch_related("teams")

        for pool in group_pools:
            pts = pool_points_table(pool)
            pools_data.append({
                "pool":  pool,
                "teams": list(pool.teams.all().order_by("name")),
                "points": pts,
            })

        interleaved_sched = get_interleaved_schedule()
        any_match_played  = any(
            m.status == Match.STATUS_COMPLETED for m in interleaved_sched
        )
        # Also include knockout matches
        knockout_matches = list(
            Match.objects.filter(pool__isnull=True)
            .select_related("team1","team2","winner").order_by("match_number")
        )
    else:
        knockout_matches = []

    return render(request, "public_board.html", {
        "player":               state.current_player,
        "teams":                teams,
        "auction_started":      config is not None and (state.is_active or state.phase == AuctionState.PHASE_DONE),
        "state":                state,
        "config":               config,
        "ts":                   ts,
        "pre_auction_players":  pre_auction_players,
        "available_count":      available_count,
        "unsold_count":         unsold_count,
        "banner_url":           banner_url,
        "round_label":          round_label(state.current_category, state.phase, state.category_pass),
        "pools_data":           pools_data,
        "interleaved_sched":    interleaved_sched,
        "any_match_played":     any_match_played,
        "knockout_matches":     knockout_matches,
    })


# ────────────────────────────────────────────────
# AUCTION CONTROL PAGE
# ────────────────────────────────────────────────

@login_required
def auction_control(request):
    config = TournamentConfig.objects.first()
    ts     = TournamentSettings.get()
    if not config:
        return render(request, "auction_setup.html", {
            "ts":           ts,
            "player_count": Player.objects.count(),
            "team_count":   Team.objects.count(),
        })

    engine = AuctionEngine()
    state  = AuctionState.get()

    # Auto-advance: if no current player and not waiting for a transition,
    # pick the next player immediately (restores post-sell/unsold behaviour)
    if (state.current_player is None
            and not state.awaiting_transition
            and state.phase != AuctionState.PHASE_DONE
            and state.is_active):
        engine.advance_to_next_player()
        state = AuctionState.get()  # re-fetch after possible state change

    player      = state.current_player
    teams       = Team.objects.all()
    increment   = bid_increment()
    blocked_ids = engine.get_blocked_team_ids(state)

    for t in teams:
        t.display_short = t.get_short()
        t.short          = t.get_short()   # alias for older template
        t.is_blocked    = t.team_serial_number in blocked_ids
        t.squad_count   = t.player_set.filter(status=Player.STATUS_SOLD).count()
        t.slots_left    = max(0, config.bidding_slots - t.squad_count)

    pool_exhausted = (
        player is None
        and not state.awaiting_transition
        and not Player.objects.filter(
            status__in=[Player.STATUS_AVAILABLE, Player.STATUS_UNSOLD]
        ).exists()
    )

    # Category base price for status bar
    category_base_price = config.base_price_for_role(state.current_category)

    # Round label (item 3)
    current_round_label = round_label(state.current_category, state.phase, state.category_pass)

    # Player count for current round (item 21)
    cat             = state.current_category
    available_count = Player.objects.filter(status=Player.STATUS_AVAILABLE, role=cat).count()
    unsold_count    = Player.objects.filter(status=Player.STATUS_UNSOLD,    role=cat).count()

    return render(request, "auction_control.html", {
        "player":               player,
        "teams":                teams,
        "increment":            increment,
        "state":                state,
        "pool_exhausted":       pool_exhausted,
        "config":               config,
        "category_base_price":  category_base_price,
        "current_round_label":  current_round_label,
        "available_count":      available_count,
        "unsold_count":         unsold_count,
        "ts":                   ts,
    })


# ────────────────────────────────────────────────
# START AUCTION
# ────────────────────────────────────────────────

@login_required
def start_auction(request):
    if request.method == "POST":
        total_points = int(request.POST.get("total_points"))

        config = TournamentConfig.objects.create(
            total_points       = total_points,
            bidding_slots      = request.POST.get("bidding_slots"),
            max_squad_size     = request.POST.get("max_squad_size"),
            base_price_AR      = request.POST.get("base_price_AR"),
            base_price_BAT     = request.POST.get("base_price_BAT"),
            base_price_BOWL    = request.POST.get("base_price_BOWL"),
            base_price_PLY     = request.POST.get("base_price_PLY"),
            category_order     = request.POST.get("category_order", "AR,BAT,BOWL,PLY"),
            max_rebid_attempts = request.POST.get("max_rebid_attempts", 3),
        )

        for team in Team.objects.all():
            team.remaining_points = total_points
            team.save()

        # Base prices applied to all players
        Player.objects.filter(role="AR").update(base_price=config.base_price_AR)
        Player.objects.filter(role="BAT").update(base_price=config.base_price_BAT)
        Player.objects.filter(role="BOWL").update(base_price=config.base_price_BOWL)
        Player.objects.filter(role="PLY").update(base_price=config.base_price_PLY)

        engine = AuctionEngine()
        engine.activate_auction()   # sets transition banner, no auto-pick

    return redirect("/auction/")


# ────────────────────────────────────────────────
# CONFIRM TRANSITION (admin clicks Continue) — item 4
# ────────────────────────────────────────────────

@login_required
def confirm_transition(request):
    engine = AuctionEngine()
    engine.confirm_transition()
    return redirect("/auction/")


# ────────────────────────────────────────────────
# NEXT PLAYER
# ────────────────────────────────────────────────

@login_required
def next_player(request):
    try:
        auction_logger.debug(f"next_player by {request.user}")
        engine = AuctionEngine()
        player = engine.advance_to_next_player()
        if player:
            auction_logger.info(f"next_player: on block → {player.name}")
        return redirect("/auction/")
    except Exception as e:
        error_logger.error(f"next_player error: {e}\n{traceback.format_exc()}")
        return redirect("/auction/")


# ────────────────────────────────────────────────
# SELL PLAYER — item 8 force sell, item 20 extra player
# ────────────────────────────────────────────────

@csrf_exempt
@login_required
def sell_player(request):
    if request.method != "POST":
        return JsonResponse({"status": "invalid"})

    service   = BiddingService()
    player_id = request.POST.get("player_id")
    team_id   = request.POST.get("team_id")
    amount    = request.POST.get("amount")
    force     = request.POST.get("force") == "true"
    extra     = request.POST.get("extra") == "true"

    try:
        player = Player.objects.get(serial_number=player_id)
        team   = Team.objects.get(team_serial_number=team_id)
        config = TournamentConfig.objects.first()

        # Extra player check (item 20)
        squad_count = team.player_set.filter(status=Player.STATUS_SOLD).count()
        over_slots  = config and squad_count >= config.bidding_slots
        if over_slots and not extra and not force:
            return JsonResponse({
                "status":       "confirm_extra",
                "team_name":    team.name,
                "squad_count":  squad_count,
                "max_slots":    config.bidding_slots if config else "?",
            })

        success, error, is_below_base = service.sell_player(player_id, team_id, amount, force=force or extra)

        if success:
            return JsonResponse({"status": "ok"})
        elif error and is_below_base:
            return JsonResponse({"status": "below_base", "message": error})
        elif error:
            return JsonResponse({"status": "error", "message": error})
        else:
            return JsonResponse({"status": "error", "message": "Unknown error"})

    except Exception as e:
        return JsonResponse({"status": "error", "message": api_error_response(e), "allow_force": False})


# ────────────────────────────────────────────────
# UNSOLD
# ────────────────────────────────────────────────

@csrf_exempt
@login_required
def unsold_player(request):
    if request.method == "POST":
        try:
            auction_logger.info(f"unsold_player: player={request.POST.get('player_id')} by {request.user}")
            BiddingService().mark_unsold(request.POST.get("player_id"))
            return JsonResponse({"status": "ok"})
        except Exception as e:
            error_logger.error(f"unsold_player error: {e}\n{traceback.format_exc()}")
            return JsonResponse({"status": "error", "message": api_error_response(e)})
    return JsonResponse({"status": "invalid"})


# ────────────────────────────────────────────────
# NOT PLAYING
# ────────────────────────────────────────────────

@csrf_exempt
@login_required
def not_playing_player(request):
    if request.method == "POST":
        try:
            auction_logger.info(f"not_playing: player={request.POST.get('player_id')} by {request.user}")
            BiddingService().mark_not_playing(request.POST.get("player_id"))
            return JsonResponse({"status": "ok"})
        except Exception as e:
            error_logger.error(f"not_playing_player error: {e}\n{traceback.format_exc()}")
            return JsonResponse({"status": "error", "message": api_error_response(e)})
    return JsonResponse({"status": "invalid"})


# ────────────────────────────────────────────────
# UNDO
# ────────────────────────────────────────────────

@login_required
def undo_action(request):
    try:
        auction_logger.info(f"undo_action by {request.user}")
        BiddingService().undo_last_action()
    except Exception as e:
        error_logger.error(f"undo_action error: {e}\n{traceback.format_exc()}")
    return redirect("/auction/")


# ────────────────────────────────────────────────
# REFRESH — recalculate all team points (item 9)
# ────────────────────────────────────────────────

@csrf_exempt
@login_required
def refresh_points(request):
    try:
        system_logger.info(f"refresh_points by {request.user}")
        AuctionEngine().recalculate_points()
        return JsonResponse({"status": "ok"})
    except Exception as e:
        error_logger.error(f"refresh_points error: {e}\n{traceback.format_exc()}")
        return JsonResponse({"status": "error", "message": api_error_response(e)})


# ────────────────────────────────────────────────
# COMPLETE AUCTION
# ────────────────────────────────────────────────

@login_required
@login_required
def complete_auction(request):
    state                     = AuctionState.get()
    state.phase               = AuctionState.PHASE_DONE
    state.is_active           = False
    state.current_player      = None
    state.awaiting_transition = False
    state.transition_message  = ""
    state.save()
    return redirect("/auction/summary/")


# ────────────────────────────────────────────────
# AUCTION SUMMARY — always accessible (item 5)
# ────────────────────────────────────────────────

@login_required
def auction_summary(request):
    teams  = Team.objects.all()
    config = TournamentConfig.objects.first()
    state  = AuctionState.get()
    ts     = TournamentSettings.get()

    for team in teams:
        sold = Player.objects.filter(
            team=team, status=Player.STATUS_SOLD
        ).order_by("role", "name")
        team.sold_players = sold
        team.total_spent  = sum(p.sold_price or 0 for p in sold)
        team.player_count = sold.count()

    return render(request, "auction_summary.html", {
        "teams":  teams,
        "config": config,
        "state":  state,
        "ts":     ts,
    })


# ────────────────────────────────────────────────
# BANNER UPLOAD — item 1
# ────────────────────────────────────────────────

@login_required
def banner_upload(request):
    ts  = TournamentSettings.get()   # always exists — no config needed
    msg = None

    if request.method == "POST":
        tournament_name = request.POST.get("tournament_name", "").strip()
        auction_dt      = request.POST.get("auction_date") or None
        match_dt        = request.POST.get("match_date")   or None
        uploaded        = request.FILES.get("banner")

        if tournament_name:
            ts.tournament_name = tournament_name
        if auction_dt is not None:
            ts.auction_date = auction_dt
        if match_dt is not None:
            ts.match_date = match_dt

        if uploaded:
            banner_dir = os.path.join(settings.MEDIA_ROOT, "banners")
            os.makedirs(banner_dir, exist_ok=True)
            filename = "tournament_banner" + os.path.splitext(uploaded.name)[1]
            path     = os.path.join(banner_dir, filename)
            with open(path, "wb+") as f:
                for chunk in uploaded.chunks():
                    f.write(chunk)
            ts.banner_path = filename
            msg = "Settings saved."
        else:
            msg = "Settings saved."

        ts.save()

    current_banner = None
    if ts.banner_path:
        current_banner = settings.MEDIA_URL + "banners/" + ts.banner_path

    return render(request, "banner_upload.html", {
        "msg":            msg,
        "current_banner": current_banner,
        "ts":             ts,
    })


# ────────────────────────────────────────────────
# CSV UPLOAD + VALIDATE — items 2, 14
# ────────────────────────────────────────────────

@login_required
def upload_csv(request):
    csv_service = CSVService()
    result      = None

    if request.method == "POST":
        action   = request.POST.get("action", "import")
        csv_type = request.POST.get("csv_type", "players")

        # ── Load a bundled demo file (no upload needed) ──────
        if action == "load_demo":
            demo_file = request.POST.get("demo_file", "short_players")
            FILE_MAP  = {
                "short_teams":   ("teams",   "short_teams.csv"),
                "short_players": ("players", "short_players.csv"),
                "long_teams":    ("teams",   "long_teams.csv"),
                "long_players":  ("players", "long_players.csv"),
            }
            if demo_file not in FILE_MAP:
                result = {"error": "Unknown demo file selected."}
            else:
                file_type, filename = FILE_MAP[demo_file]
                filepath = settings.BASE_DIR / "sample_data" / filename
                if not filepath.exists():
                    result = {"error": f"Demo file not found on server: {filename}. Make sure it is committed to the repository."}
                else:
                    try:
                        system_logger.info(f"upload_csv load_demo: {demo_file} by {request.user}")
                        if file_type == "teams":
                            created, errors = csv_service.import_teams(filepath)
                        else:
                            created, errors = csv_service.import_players(filepath)
                        result = {
                            "action":   "import",
                            "csv_type": file_type,
                            "created":  created,
                            "errors":   errors,
                            "source":   filename,
                        }
                    except Exception as e:
                        error_logger.error(f"upload_csv load_demo error: {e}\n{traceback.format_exc()}")
                        result = {"error": str(e)}

        # ── Upload a file ────────────────────────────────────
        else:
            uploaded = request.FILES.get("file")
            if not uploaded:
                result = {"error": "No file selected."}
            else:
                path = f"/tmp/kpl_upload_{csv_type}.csv"
                with open(path, "wb+") as f:
                    for chunk in uploaded.chunks():
                        f.write(chunk)
                try:
                    system_logger.info(f"upload_csv {action}: {csv_type} '{uploaded.name}' by {request.user}")
                    if csv_type == "teams":
                        fn = csv_service.validate_teams_csv if action == "validate" else csv_service.import_teams
                    else:
                        fn = csv_service.validate_players_csv if action == "validate" else csv_service.import_players
                    created, errors = fn(path)
                    result = {
                        "action":   action,
                        "csv_type": csv_type,
                        "created":  created,
                        "errors":   errors,
                        "source":   uploaded.name,
                    }
                except Exception as e:
                    error_logger.error(f"upload_csv error: {e}\n{traceback.format_exc()}")
                    result = {"error": str(e)}

    return render(request, "upload_csv.html", {"result": result})


# ────────────────────────────────────────────────
# LOAD SAMPLE DATA
# ────────────────────────────────────────────────

@csrf_exempt
@login_required
def load_sample_data(request):
    """Load a bundled sample CSV directly — no file upload needed."""
    import os
    if request.method != "POST":
        return JsonResponse({"status": "invalid"})
    try:
        dataset  = request.POST.get("dataset")  # short_players | short_teams | long_players | long_teams
        csv_type = request.POST.get("csv_type") # players | teams

        allowed = {
            "short_players": ("players", "short_players.csv"),
            "short_teams":   ("teams",   "short_teams.csv"),
            "long_players":  ("players", "long_players.csv"),
            "long_teams":    ("teams",   "long_teams.csv"),
        }
        if dataset not in allowed:
            return JsonResponse({"status": "error", "message": "Unknown dataset"})

        file_type, filename = allowed[dataset]
        filepath = settings.BASE_DIR / "sample_data" / filename

        if not filepath.exists():
            return JsonResponse({"status": "error", "message": f"File not found: {filename}"})

        service = CSVService()
        system_logger.info(f"load_sample_data: {dataset} by {request.user}")

        if file_type == "teams":
            created, errors = service.import_teams(filepath)
        else:
            created, errors = service.import_players(filepath)

        return JsonResponse({
            "status":  "ok",
            "created": created,
            "errors":  errors,
            "dataset": dataset,
        })
    except Exception as e:
        error_logger.error(f"load_sample_data error: {e}\n{traceback.format_exc()}")
        return JsonResponse({"status": "error", "message": api_error_response(e)})


@login_required
def download_sample_csv(request, name):
    """Serve a sample CSV file as a download."""
    import os
    allowed = {
        "short_teams":   "short_teams.csv",
        "short_players": "short_players.csv",
        "long_teams":    "long_teams.csv",
        "long_players":  "long_players.csv",
    }
    if name not in allowed:
        from django.http import Http404
        raise Http404("Sample file not found")
    filepath = settings.BASE_DIR / "sample_data" / allowed[name]
    try:
        with open(filepath, "rb") as f:
            content = f.read()
        response = HttpResponse(content, content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{allowed[name]}"'
        system_logger.info(f"download_sample_csv: {name} by {request.user}")
        return response
    except FileNotFoundError:
        from django.http import Http404
        raise Http404("Sample file not found")


# ────────────────────────────────────────────────
# DEBUG STATE (remove before production)
# ────────────────────────────────────────────────

@login_required
def debug_state(request):
    """Visit /auction/debug/ to see current auction state."""
    from django.http import HttpResponse
    import json
    try:
        state  = AuctionState.get()
        config = TournamentConfig.objects.first()
        lines  = [
            f"phase:             {state.phase}",
            f"current_category:  {state.current_category}",
            f"category_pass:     {state.category_pass}",
            f"auction_round:     {state.auction_round}",
            f"is_active:         {state.is_active}",
            f"awaiting_trans:    {state.awaiting_transition}",
            f"transition_msg:    {state.transition_message}",
            f"current_player:    {state.current_player}",
            "",
            "--- Player counts ---",
        ]
        for role in ["AR", "BAT", "BOWL", "PLY"]:
            av = Player.objects.filter(role=role, status="AVAILABLE").count()
            so = Player.objects.filter(role=role, status="SOLD").count()
            un = Player.objects.filter(role=role, status="UNSOLD").count()
            np = Player.objects.filter(role=role, status="NOT_PLAYING").count()
            lines.append(f"{role}: AVAIL={av} SOLD={so} UNSOLD={un} NOT_PLAYING={np}")
        if config:
            lines += ["", f"category_order: {config.get_category_order()}",
                      f"max_rebid_attempts: {config.max_rebid_attempts}"]
        return HttpResponse("\n".join(lines), content_type="text/plain")
    except Exception as e:
        return HttpResponse(f"Error: {e}", content_type="text/plain")


# ────────────────────────────────────────────────
# AUDIT LOG
# ────────────────────────────────────────────────

@login_required
def audit_log(request):
    return render(request, "audit_log.html", {
        "actions": AuditService().get_all_actions()
    })


# ────────────────────────────────────────────────
# RESET AUCTION (URL kept, not linked in UI — item 11)
# ────────────────────────────────────────────────

@login_required
def reset_auction(request):
    AuctionEngine().reset_auction()
    return redirect("/auction/")



# ────────────────────────────────────────────────
# JERSEY PORTAL — admin only, auto-populated by team
# ────────────────────────────────────────────────

@login_required
def jersey_portal(request):
    import json
    system_logger.debug(f"jersey_portal: user={request.user}")
    config = TournamentConfig.objects.first()
    msg    = None

    if request.method == "POST":
        action = request.POST.get("action")

        # ── Save jersey name/number for a sold player ──
        if action == "save_player_jersey":
            try:
                import json as _j2
                player_id         = int(request.POST.get("player_id"))
                jersey_name       = request.POST.get("jersey_name", "").strip()
                jersey_number_raw = request.POST.get("jersey_number", "").strip()
                jersey_number     = int(jersey_number_raw) if jersey_number_raw else None
                snum_raw          = request.POST.get("size_number", "").strip()
                snum              = int(snum_raw) if snum_raw else 0
                # Derive size_text from config mapping
                _cfg2  = TournamentConfig.objects.first()
                _smap2 = {}
                if _cfg2 and _cfg2.size_mapping:
                    try: _smap2 = _j2.loads(_cfg2.size_mapping)
                    except: pass
                stxt = _smap2.get(str(snum), "") if snum else ""
                player = Player.objects.get(serial_number=player_id)
                if jersey_name or jersey_number is not None:
                    Jersey.objects.update_or_create(
                        player=player,
                        defaults={"jersey_name":   jersey_name,
                                  "jersey_number":  jersey_number or 0,
                                  "size_number":    snum,
                                  "size_text":      stxt}
                    )
                    msg = f"Saved jersey for {player.name}."
                else:
                    Jersey.objects.filter(player=player).delete()
                    msg = f"Cleared jersey for {player.name}."
            except Exception as e:
                msg = f"Error: {e}"

        # ── Add extra team member (manager/supporter etc.) ──
        elif action == "add_team_extra":
            try:
                import json as _j2
                team_id    = int(request.POST.get("team_id"))
                name       = request.POST.get("extra_name", "").strip()
                role_label = request.POST.get("extra_role", "").strip()
                jname      = request.POST.get("extra_jersey_name", "").strip()
                jnum_raw   = request.POST.get("extra_jersey_number", "").strip()
                jnum       = int(jnum_raw) if jnum_raw else None
                snum_raw   = request.POST.get("extra_size_number", "").strip()
                snum       = int(snum_raw) if snum_raw else None
                sponsor    = request.POST.get("extra_sponsor", "").strip()
                _cfg2 = TournamentConfig.objects.first()
                _smap2 = {}
                if _cfg2 and _cfg2.size_mapping:
                    try: _smap2 = _j2.loads(_cfg2.size_mapping)
                    except: pass
                stxt = _smap2.get(str(snum), "") if snum else ""
                team = Team.objects.get(team_serial_number=team_id)
                if name:
                    ExtraJerseyMember.objects.create(
                        name=name, role_label=role_label,
                        jersey_name=jname, jersey_number=jnum,
                        size_number=snum, size_text=stxt, sponsor=sponsor,
                        member_type=ExtraJerseyMember.TYPE_TEAM, team=team
                    )
                    msg = f"Added {name} to {team.name}."
            except Exception as e:
                msg = f"Error: {e}"

        # ── Add organiser member ──
        elif action == "add_organiser":
            try:
                import json as _j2
                name       = request.POST.get("org_name", "").strip()
                role_label = request.POST.get("org_role", "").strip()
                group_name = request.POST.get("org_group", "Organisers").strip() or "Organisers"
                jname      = request.POST.get("org_jersey_name", "").strip()
                jnum_raw   = request.POST.get("org_jersey_number", "").strip()
                jnum       = int(jnum_raw) if jnum_raw else None
                snum_raw   = request.POST.get("org_size_number", "").strip()
                snum       = int(snum_raw) if snum_raw else None
                sponsor    = request.POST.get("org_sponsor", "").strip()
                _cfg2 = TournamentConfig.objects.first()
                _smap2 = {}
                if _cfg2 and _cfg2.size_mapping:
                    try: _smap2 = _j2.loads(_cfg2.size_mapping)
                    except: pass
                stxt = _smap2.get(str(snum), "") if snum else ""
                if name:
                    ExtraJerseyMember.objects.create(
                        name=name, role_label=role_label,
                        jersey_name=jname, jersey_number=jnum,
                        size_number=snum, size_text=stxt, sponsor=sponsor,
                        member_type=ExtraJerseyMember.TYPE_ORGANISER,
                        group_name=group_name
                    )
                    msg = f"Added organiser {name}."
            except Exception as e:
                msg = f"Error: {e}"

        # ── Update extra member jersey inline ──
        elif action == "update_extra":
            try:
                import json as _j2
                eid      = int(request.POST.get("extra_id"))
                jname    = request.POST.get("jersey_name", "").strip()
                jnum_raw = request.POST.get("jersey_number", "").strip()
                jnum     = int(jnum_raw) if jnum_raw else None
                snum_raw = request.POST.get("size_number", "").strip()
                snum     = int(snum_raw) if snum_raw else None
                stxt_in  = request.POST.get("size_text", "").strip().upper()
                sponsor  = request.POST.get("sponsor", "").strip()
                _cfg2 = TournamentConfig.objects.first()
                _smap2 = {}
                if _cfg2 and _cfg2.size_mapping:
                    try: _smap2 = _j2.loads(_cfg2.size_mapping)
                    except: pass
                # Derive size_text from number if not provided
                stxt = stxt_in or (_smap2.get(str(snum), "") if snum else "")
                # Derive size_number from text if not provided
                if not snum and stxt_in:
                    rev = {v: k for k, v in _smap2.items()}
                    snum_str = rev.get(stxt_in)
                    snum = int(snum_str) if snum_str else None
                em = ExtraJerseyMember.objects.get(pk=eid)
                em.jersey_name   = jname
                em.jersey_number = jnum
                em.size_number   = snum
                em.size_text     = stxt
                em.sponsor       = sponsor
                em.save()
                msg = f"Updated {em.name}."
            except Exception as e:
                msg = f"Error: {e}"

        # ── Delete extra member ──
        elif action == "delete_extra":
            try:
                eid = int(request.POST.get("extra_id"))
                em  = ExtraJerseyMember.objects.get(pk=eid)
                msg = f"Deleted {em.name}."
                em.delete()
            except Exception as e:
                msg = f"Error: {e}"

    # ── Build page data ──
    # All teams with their sold players and extras
    teams = Team.objects.all().order_by("name")
    jersey_map = {j.player_id: j for j in Jersey.objects.select_related("player").all()}
    extras_by_team = {}
    for em in ExtraJerseyMember.objects.filter(
            member_type=ExtraJerseyMember.TYPE_TEAM).select_related("team"):
        extras_by_team.setdefault(em.team_id, []).append(em)

    team_sections = []
    for team in teams:
        players = list(Player.objects.filter(
            team=team, status=Player.STATUS_SOLD
        ).order_by("role", "name"))
        for p in players:
            p.jersey = jersey_map.get(p.serial_number)
        team_sections.append({
            "team":    team,
            "players": players,
            "extras":  extras_by_team.get(team.team_serial_number, []),
        })

    # Organiser groups
    organisers_raw = ExtraJerseyMember.objects.filter(
        member_type=ExtraJerseyMember.TYPE_ORGANISER
    ).order_by("group_name", "name")
    org_groups = {}
    for em in organisers_raw:
        org_groups.setdefault(em.group_name, []).append(em)

    # Unique organiser group names for datalist suggestion
    org_group_names = list(org_groups.keys())

    # Size mapping for display
    import json as _json
    try:
        size_mapping = _json.loads(config.size_mapping) if config and config.size_mapping else {}
    except Exception:
        size_mapping = {}
    size_mapping_pairs = sorted(
        [(k, v) for k, v in size_mapping.items()],
        key=lambda x: int(x[0]) if x[0].isdigit() else 0
    )

    return render(request, "jersey_management.html", {
        "team_sections":      team_sections,
        "org_groups":         org_groups,
        "org_group_names":    org_group_names,
        "msg":                msg,
        "config":             config,
        "size_mapping":       size_mapping,
        "size_mapping_pairs": size_mapping_pairs,
    })


# ────────────────────────────────────────────────
# JERSEY AJAX SAVE (inline player row)
# ────────────────────────────────────────────────

@csrf_exempt
@login_required
def jersey_save_ajax(request):
    if request.method != "POST":
        return JsonResponse({"status": "invalid"})
    import json as _json
    try:
        player_id         = int(request.POST.get("player_id"))
        jersey_name       = request.POST.get("jersey_name", "").strip()
        jersey_number_raw = request.POST.get("jersey_number", "").strip()
        jersey_number     = int(jersey_number_raw) if jersey_number_raw else 0
        size_number_raw   = request.POST.get("size_number", "").strip()
        size_number       = int(size_number_raw) if size_number_raw else 0
        size_text_raw     = request.POST.get("size_text", "").strip().upper()

        # Build size map from config
        config  = TournamentConfig.objects.first()
        smap    = {}
        smap_rev = {}
        if config and config.size_mapping:
            try:
                smap     = _json.loads(config.size_mapping)
                smap_rev = {v.upper(): k for k, v in smap.items()}
            except Exception:
                pass

        # Derive size_text from size_number if text not provided
        if size_number and not size_text_raw:
            size_text = smap.get(str(size_number), "")
        elif size_text_raw and not size_number:
            # Derive size_number from size_text if number not provided
            num_str     = smap_rev.get(size_text_raw, "")
            size_number = int(num_str) if num_str else 0
            size_text   = size_text_raw
        else:
            size_text = size_text_raw or smap.get(str(size_number), "")

        sponsor = request.POST.get("sponsor", "").strip()
        player  = Player.objects.get(serial_number=player_id)
        Jersey.objects.update_or_create(
            player=player,
            defaults={
                "jersey_name":   jersey_name,
                "jersey_number": jersey_number,
                "size_number":   size_number,
                "size_text":     size_text,
                "sponsor":       sponsor,
            }
        )
        return JsonResponse({"status": "ok", "size_text": size_text, "size_number": size_number})
    except Exception as e:
        return JsonResponse({"status": "error", "message": api_error_response(e)})


# ────────────────────────────────────────────────
# EXPORT JERSEY PDF
# ────────────────────────────────────────────────

@csrf_exempt
@login_required
def update_size_mapping(request):
    import json as _json
    if request.method != "POST":
        return JsonResponse({"status": "invalid"})
    config = TournamentConfig.objects.first()
    if not config:
        return JsonResponse({"status": "error", "message": "No tournament config"})
    try:
        body    = request.body.decode("utf-8")
        mapping = _json.loads(body)
        clean   = {str(k).strip(): str(v).strip().upper() for k, v in mapping.items() if str(k).strip() and str(v).strip()}
        config.size_mapping = _json.dumps(clean)
        config.save()
        return JsonResponse({"status": "ok", "mapping": clean})
    except Exception as e:
        error_logger.error(f"update_size_mapping error: {e}\n{traceback.format_exc()}")
        return JsonResponse({"status": "error", "message": api_error_response(e)})


@login_required
def export_jersey_pdf(request):
    try:
        pdf_buffer = JerseyService().export_pdf()
        system_logger.info(f"export_jersey_pdf downloaded by {request.user}")
        response   = HttpResponse(pdf_buffer, content_type="application/pdf")
        response["Content-Disposition"] = "attachment; filename=jersey_list.pdf"
        return response
    except Exception as e:
        error_logger.error(f"export_jersey_pdf error: {e}\n{traceback.format_exc()}")
        return HttpResponse(f"PDF generation error: {e}", status=500)


# ────────────────────────────────────────────────
# FIXTURES — old URLs redirect to pool manager
# ────────────────────────────────────────────────

def fixtures_redirect(request):
    return redirect("/fixtures/pools/")



@login_required
def pool_manager(request):
    """Unified pools + fixtures page."""
    system_logger.debug(f"pool_manager: user={request.user}")
    teams       = list(Team.objects.all().order_by("name"))
    pools_info  = all_pools_status()
    group_pools = TournamentPool.objects.filter(stage=TournamentPool.STAGE_GROUP).order_by("order")
    ts          = TournamentSettings.get()
    num_teams   = len(teams)
    suggested_n, suggested_adv = suggest_pool_config(num_teams)
    teams_per_pool = (num_teams // suggested_n) if suggested_n else 4

    in_pool_ids = set(
        PoolTeam.objects.filter(
            pool__stage=TournamentPool.STAGE_GROUP
        ).values_list("team__team_serial_number", flat=True)
    )
    unassigned     = [t for t in teams if t.team_serial_number not in in_pool_ids]
    assignment_done = (len(unassigned) == 0 and group_pools.exists())

    pool_fill = [
        {"id": p.pk, "name": p.name, "count": p.teams.count(), "max": teams_per_pool}
        for p in group_pools
    ]

    # Fixture schedule
    schedule  = get_interleaved_schedule() if assignment_done else []

    # Build day-column structure for two-column display
    day_cols = []
    pools_list = list(group_pools)
    if schedule and pools_list:
        pool_match_map = {}
        for p in pools_list:
            rounds_map = {}
            for m in p.matches.select_related("team1","team2","winner").order_by("created_at"):
                rnum = 1
                if m.notes and m.notes.startswith("round:"):
                    try: rnum = int(m.notes.split(":")[1])
                    except: pass
                rounds_map.setdefault(rnum, []).append(m)
            pool_match_map[p.pk] = [rounds_map[r] for r in sorted(rounds_map)]

        for day_idx in range(0, len(pools_list), 2):
            lp = pools_list[day_idx]
            rp = pools_list[day_idx + 1] if day_idx + 1 < len(pools_list) else None
            left_rounds  = pool_match_map.get(lp.pk, [])
            right_rounds = pool_match_map.get(rp.pk, []) if rp else []
            max_rounds   = max(len(left_rounds), len(right_rounds))
            rows = []
            for ri in range(max_rounds):
                lr = left_rounds[ri]  if ri < len(left_rounds)  else []
                rr = right_rounds[ri] if ri < len(right_rounds) else []
                for mi in range(max(len(lr), len(rr))):
                    rows.append({
                        "left":  lr[mi] if mi < len(lr) else None,
                        "right": rr[mi] if mi < len(rr) else None,
                    })
            day_cols.append({
                "day":        day_idx // 2 + 1,
                "left_pool":  lp.name,
                "right_pool": rp.name if rp else None,
                "left_pk":    lp.pk,
                "right_pk":   rp.pk if rp else None,
                "rows":       rows,
            })

    msg = request.GET.get("msg", "")

    return render(request, "pool_manager.html", {
        "teams":           teams,
        "pools_info":      pools_info,
        "group_pools":     group_pools,
        "unassigned":      unassigned,
        "pool_fill":       pool_fill,
        "num_teams":       num_teams,
        "suggested_n":     suggested_n,
        "suggested_adv":   suggested_adv,
        "teams_per_pool":  teams_per_pool,
        "assignment_done": assignment_done,
        "schedule":        schedule,
        "day_cols":        day_cols,
        "ts":              ts,
        "msg":             msg,
    })


@csrf_exempt
@login_required
def pool_generate_all(request):
    """Generate round-robin matches for ALL group stage pools at once."""
    if request.method == "POST":
        total_created = 0
        for pool in TournamentPool.objects.filter(stage=TournamentPool.STAGE_GROUP):
            created, _ = generate_pool_matches(pool.pk)
            total_created += created
        return redirect(f"/fixtures/pools/?msg=Generated+{total_created}+matches+across+all+pools")
    return redirect("/fixtures/pools/")


@csrf_exempt
@login_required
def pool_reset(request):
    """Wipe all group-stage pools, their matches, and pool-team assignments."""
    if request.method == "POST":
        try:
            old_pools   = TournamentPool.objects.filter(stage=TournamentPool.STAGE_GROUP)
            pool_names  = list(old_pools.values_list("name", flat=True))
            match_count = Match.objects.filter(pool__in=old_pools).count()
            Match.objects.filter(pool__in=old_pools).delete()
            old_pools.delete()
            system_logger.warning(f"pool_reset: deleted pools {pool_names} + {match_count} matches by {request.user}")
            return redirect("/fixtures/pools/?msg=Pools+reset+successfully")
        except Exception as e:
            error_logger.error(f"pool_reset error: {e}\n{traceback.format_exc()}")
            return redirect(f"/fixtures/pools/?msg=Error:+{e}")
    return redirect("/fixtures/pools/")


@csrf_exempt
@login_required
def fixtures_reset(request):
    """Wipe all pool matches only — keeps pool/team assignments intact."""
    if request.method == "POST":
        pool_matches = Match.objects.filter(pool__stage=TournamentPool.STAGE_GROUP)
        count = pool_matches.count()
        pool_matches.delete()
        # Un-lock pools so fixtures can be redrawn
        TournamentPool.objects.filter(stage=TournamentPool.STAGE_GROUP).update(
            fixtures_locked=False
        )
        _renumber_matches()
        return redirect(f"/fixtures/pools/?msg=Cleared+{count}+matches.+Pools+intact.")
    return redirect("/fixtures/pools/")


@login_required
def pool_create(request):
    """Create group stage pools (wipes existing group pools)."""
    if request.method == "POST":
        num_pools      = int(request.POST.get("num_pools", 4))
        advance_n      = int(request.POST.get("advance_n", 2))
        teams_per_pool = int(request.POST.get("teams_per_pool", 4))
        assignment_order = request.POST.get("assignment_order", "sequential")
        auto_dist      = request.POST.get("auto_distribute") == "1"
        team_ids       = None
        if auto_dist:
            team_ids = list(Team.objects.values_list("team_serial_number", flat=True))
        create_group_stage(num_pools, advance_n, teams_per_pool, team_ids, assignment_order)
        return redirect("/fixtures/pools/?msg=Group+stage+created")
    return redirect("/fixtures/pools/")


@csrf_exempt
@login_required
def pool_generate_matches(request):
    """Generate round-robin matches for a specific pool."""
    if request.method == "POST":
        pool_id = request.POST.get("pool_id")
        try:
            created, skipped = generate_pool_matches(pool_id)
            msg = f"Generated {created} matches"
            if skipped:
                msg += f" ({skipped} already existed)"
        except Exception as e:
            msg = f"Error: {e}"
        return redirect(f"/fixtures/pools/?msg={msg}")
    return redirect("/fixtures/pools/")


@csrf_exempt
@login_required
def pool_advance(request):
    """Mark teams as advanced from a pool — handle ties manually."""
    if request.method == "POST":
        pool_id  = request.POST.get("pool_id")
        team_ids = request.POST.getlist("team_ids")
        try:
            advance_teams(pool_id, [int(t) for t in team_ids])
            return redirect("/fixtures/pools/?msg=Advancement+saved")
        except Exception as e:
            return redirect(f"/fixtures/pools/?msg=Error:+{e}")
    return redirect("/fixtures/pools/")


@csrf_exempt
@login_required
def pool_team_add(request):
    if request.method == "POST":
        try:
            add_team_to_pool(
                int(request.POST.get("pool_id")),
                int(request.POST.get("team_id"))
            )
        except Exception as e:
            return JsonResponse({"status": "error", "message": api_error_response(e)})
        return JsonResponse({"status": "ok"})
    return JsonResponse({"status": "invalid"})


@csrf_exempt
@login_required
def pool_team_remove(request):
    if request.method == "POST":
        try:
            remove_team_from_pool(
                int(request.POST.get("pool_id")),
                int(request.POST.get("team_id"))
            )
        except Exception as e:
            return JsonResponse({"status": "error", "message": api_error_response(e)})
        return JsonResponse({"status": "ok"})
    return JsonResponse({"status": "invalid"})


@csrf_exempt
@login_required
def pool_spin_assign(request):
    """
    AJAX: Auto-assign a spun team to the correct pool based on assignment_order.
    POST: team_id only — pool is determined server-side from assignment_order.
    Returns: assigned_pool name + updated state.
    """
    if request.method != "POST":
        return JsonResponse({"status": "invalid"})

    team_id = request.POST.get("team_id")
    if not team_id:
        return JsonResponse({"status": "error", "message": "Missing team_id"})

    try:
        pools = list(TournamentPool.objects.filter(
            stage=TournamentPool.STAGE_GROUP
        ).order_by("order"))

        if not pools:
            return JsonResponse({"status": "error", "message": "No pools exist"})

        # Count how many teams have been assigned so far (before this one)
        total_assigned = PoolTeam.objects.filter(
            pool__stage=TournamentPool.STAGE_GROUP
        ).count()

        assignment_order = pools[0].assignment_order  # same on all pools
        teams_per_pool   = pools[0].teams_per_pool
        num_pools        = len(pools)

        # Determine target pool index
        if assignment_order == "sequential":
            pool_idx = min(total_assigned // teams_per_pool, num_pools - 1)
        else:  # roundrobin
            pool_idx = total_assigned % num_pools

        target_pool = pools[pool_idx]

        # Safety: if target pool is full, find next pool with space
        for attempt in range(num_pools):
            if target_pool.teams.count() < target_pool.teams_per_pool:
                break
            pool_idx = (pool_idx + 1) % num_pools
            target_pool = pools[pool_idx]
        else:
            return JsonResponse({"status": "error", "message": "All pools are full"})

        add_team_to_pool(target_pool.pk, int(team_id))

        # Build response
        assigned_ids = set(
            PoolTeam.objects.filter(pool__stage=TournamentPool.STAGE_GROUP)
            .values_list("team__team_serial_number", flat=True)
        )
        remaining = [
            {"id": t.team_serial_number, "name": t.name}
            for t in Team.objects.exclude(team_serial_number__in=assigned_ids).order_by("name")
        ]
        pools_state = [
            {"id": p.pk, "name": p.name, "count": p.teams.count(), "max": p.teams_per_pool}
            for p in pools
        ]

        team = Team.objects.get(team_serial_number=int(team_id))
        return JsonResponse({
            "status":        "ok",
            "assigned_pool": target_pool.name,
            "assigned_pool_id": target_pool.pk,
            "team_name":     team.name,
            "remaining":     remaining,
            "pools":         pools_state,
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": api_error_response(e)})


@csrf_exempt
@login_required
def pool_record_result(request):
    """Record a match result from the pools page."""
    if request.method != "POST":
        return JsonResponse({"status": "invalid"})
    try:
        match_id  = int(request.POST.get("match_id"))
        winner_id = request.POST.get("winner_id")
        match = Match.objects.get(pk=match_id)
        if winner_id == "draw":
            match.winner = None
            # Preserve round:N prefix so interleaved schedule ordering is intact
            existing = match.notes or ""
            if existing.startswith("round:"):
                round_part  = existing.split("|")[0].rstrip()
                match.notes = round_part + " | draw"
            else:
                match.notes = "draw"
        else:
            match.winner = Team.objects.get(team_serial_number=int(winner_id))
        match.status = Match.STATUS_COMPLETED
        match.save()
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": api_error_response(e)})


@login_required
def knockout_create(request):
    """Create knockout stage (SF/QF/Final) from advanced teams or manual selection."""
    if request.method == "POST":
        stage      = request.POST.get("stage", TournamentPool.STAGE_SF)
        label      = request.POST.get("match_label", "")
        source     = request.POST.get("source", "manual")
        team_ids   = request.POST.getlist("team_ids")

        if source == "auto":
            prev_stage = request.POST.get("prev_stage", TournamentPool.STAGE_GROUP)
            adv_teams  = get_advanced_teams(prev_stage)
            team_ids   = [t.team_serial_number for t in adv_teams]

        try:
            matches = create_knockout_stage(stage, [int(t) for t in team_ids],
                                            match_label=label or None)
            return redirect(f"/fixtures/pools/?msg=Created+{len(matches)}+knockout+matches")
        except Exception as e:
            return redirect(f"/fixtures/pools/?msg=Error:+{e}")
    return redirect("/fixtures/pools/")



@login_required
def generate_fixtures(request):
    """Generate all pool fixtures in interleaved order (auto, no spin wheel)."""
    if request.method == "POST":
        pools = TournamentPool.objects.filter(stage=TournamentPool.STAGE_GROUP).order_by("order")
        total = 0
        for pool in pools:
            created, _ = generate_pool_matches(pool.pk)
            total += created
        return redirect(f"/fixtures/pools/?msg=Generated+{total}+matches")
    return redirect("/fixtures/pools/")


@csrf_exempt
@login_required
def fixture_spin_next(request):
    """Generate one match at a time for the spin-reveal draw ceremony."""
    if request.method != "POST":
        return JsonResponse({"status": "invalid"})
    try:
        result = generate_next_match()
        if result is None:
            return JsonResponse({"status": "done"})
        return JsonResponse({"status": "ok", **result})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})


@csrf_exempt
@login_required
def fixture_record_result(request):
    """Record a match result."""
    if request.method != "POST":
        return JsonResponse({"status": "invalid"})
    try:
        match_id  = int(request.POST.get("match_id"))
        winner_id = request.POST.get("winner_id")
        match = Match.objects.get(pk=match_id)
        if winner_id == "draw":
            match.winner = None
            # Preserve round:N prefix so interleaved schedule ordering is intact
            existing = match.notes or ""
            if existing.startswith("round:"):
                round_part  = existing.split("|")[0].rstrip()
                match.notes = round_part + " | draw"
            else:
                match.notes = "draw"
        else:
            match.winner = Team.objects.get(team_serial_number=int(winner_id))
        match.status = Match.STATUS_COMPLETED
        match.save()
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": api_error_response(e)})


# ════════════════════════════════════════════════════════════════
# REPORTS
# ════════════════════════════════════════════════════════════════

from .services.report_service import (
    all_players_pdf, auction_players_pdf, teamwise_pdf,
)

# Excel exports require openpyxl — check at startup so report_download
# can return a clean 501 immediately rather than a cryptic ImportError.
try:
    import openpyxl as _openpyxl  # noqa: F401
    from .services.report_service import (
        all_players_excel, auction_players_excel, teamwise_excel,
    )
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False


@login_required
def reports_page(request):
    ts = TournamentSettings.get()
    role_choices = [("AR","All Rounders"),("BAT","Batsmen"),("BOWL","Bowlers"),("PLY","Players")]
    return render(request, "reports.html", {
        "ts":              ts,
        "role_choices":    role_choices,
        "excel_available": EXCEL_AVAILABLE,
    })


@login_required
def report_download(request):
    report_type   = request.GET.get("type", "all_players")
    fmt           = request.GET.get("fmt", "pdf")
    role_filter   = request.GET.get("role") or None
    status_filter = request.GET.get("status") or None

    # Gate Excel exports — openpyxl is not installed in this environment.
    if fmt == "xlsx" and not EXCEL_AVAILABLE:
        return HttpResponse(
            "Excel export is unavailable — openpyxl is not installed. "
            "Download the PDF version instead, or install openpyxl>=3.1 "
            "and redeploy.",
            status=501,
            content_type="text/plain",
        )

    try:
        if report_type == "all_players":
            if fmt == "xlsx":
                buf      = all_players_excel(role_filter)
                fname    = "all_players.xlsx"
                mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            else:
                buf      = all_players_pdf(role_filter)
                fname    = "all_players.pdf"
                mimetype = "application/pdf"

        elif report_type == "auction_results":
            if fmt == "xlsx":
                buf      = auction_players_excel(status_filter)
                fname    = "auction_results.xlsx"
                mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            else:
                buf      = auction_players_pdf(status_filter)
                fname    = "auction_results.pdf"
                mimetype = "application/pdf"

        elif report_type == "teamwise":
            if fmt == "xlsx":
                buf      = teamwise_excel()
                fname    = "team_squads.xlsx"
                mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            else:
                buf      = teamwise_pdf()
                fname    = "team_squads.pdf"
                mimetype = "application/pdf"

        else:
            return HttpResponse("Unknown report type", status=400)

        response = HttpResponse(buf, content_type=mimetype)
        response["Content-Disposition"] = f'attachment; filename="{fname}"'
        return response

    except Exception as e:
        error_logger.error(f"report_download error: {e}\n{traceback.format_exc()}")
        return HttpResponse(f"Report error: {e}", status=500)
