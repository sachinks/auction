import os

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from .models import Player, Team, TournamentConfig, TournamentSettings, Jersey, ExtraJerseyMember, AuctionState, Match
from .services.auction_engine import AuctionEngine, round_label
from .services.bidding_service import BiddingService
from .services.csv_service import CSVService
from .services.audit_service import AuditService
from .services.jersey_service import JerseyService
from .utils.bid_utils import bid_increment


# ────────────────────────────────────────────────
# PUBLIC BOARD
# ────────────────────────────────────────────────

def public_board(request):
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
    })


# ────────────────────────────────────────────────
# AUCTION CONTROL PAGE
# ────────────────────────────────────────────────

@login_required
def auction_control(request):
    config = TournamentConfig.objects.first()
    ts     = TournamentSettings.get()
    if not config:
        return render(request, "auction_setup.html", {"ts": ts})

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
    engine = AuctionEngine()
    engine.advance_to_next_player()
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

        success, error, allow_force = service.sell_player(player_id, team_id, amount, force=force or extra)

        if success:
            return JsonResponse({"status": "ok"})
        elif error:
            return JsonResponse({"status": "error", "message": error, "allow_force": allow_force})
        else:
            return JsonResponse({"status": "error", "message": "Unknown error"})

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e), "allow_force": False})


# ────────────────────────────────────────────────
# UNSOLD
# ────────────────────────────────────────────────

@csrf_exempt
@login_required
def unsold_player(request):
    if request.method == "POST":
        BiddingService().mark_unsold(request.POST.get("player_id"))
        return JsonResponse({"status": "ok"})
    return JsonResponse({"status": "invalid"})


# ────────────────────────────────────────────────
# NOT PLAYING
# ────────────────────────────────────────────────

@csrf_exempt
@login_required
def not_playing_player(request):
    if request.method == "POST":
        BiddingService().mark_not_playing(request.POST.get("player_id"))
        return JsonResponse({"status": "ok"})
    return JsonResponse({"status": "invalid"})


# ────────────────────────────────────────────────
# UNDO
# ────────────────────────────────────────────────

@login_required
def undo_action(request):
    BiddingService().undo_last_action()
    return redirect("/auction/")


# ────────────────────────────────────────────────
# REFRESH — recalculate all team points (item 9)
# ────────────────────────────────────────────────

@csrf_exempt
@login_required
def refresh_points(request):
    AuctionEngine().recalculate_points()
    return JsonResponse({"status": "ok"})


# ────────────────────────────────────────────────
# COMPLETE AUCTION
# ────────────────────────────────────────────────

@login_required
def complete_auction(request):
    state                = AuctionState.get()
    state.phase          = AuctionState.PHASE_DONE
    state.is_active      = False
    state.current_player = None
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
        action   = request.POST.get("action", "upload")
        csv_type = request.POST.get("csv_type", "players")
        uploaded = request.FILES.get("file")

        if not uploaded:
            result = {"error": "No file selected."}
        else:
            path = f"/tmp/kpl_upload_{csv_type}.csv"
            with open(path, "wb+") as f:
                for chunk in uploaded.chunks():
                    f.write(chunk)

            try:
                if csv_type == "teams":
                    if action == "validate":
                        created, errors = csv_service.validate_teams_csv(path)
                    else:
                        created, errors = csv_service.import_teams(path)
                else:
                    if action == "validate":
                        created, errors = csv_service.validate_players_csv(path)
                    else:
                        created, errors = csv_service.import_players(path)

                result = {
                    "action":   action,
                    "csv_type": csv_type,
                    "created":  created,
                    "errors":   errors,
                }
            except Exception as e:
                result = {"error": str(e)}

    return render(request, "upload_csv.html", {"result": result})


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
    config = TournamentConfig.objects.first()
    msg    = None

    if request.method == "POST":
        action = request.POST.get("action")

        # ── Save jersey name/number for a sold player ──
        if action == "save_player_jersey":
            try:
                player_id     = int(request.POST.get("player_id"))
                jersey_name   = request.POST.get("jersey_name", "").strip()
                jersey_number_raw = request.POST.get("jersey_number", "").strip()
                jersey_number = int(jersey_number_raw) if jersey_number_raw else None
                player = Player.objects.get(serial_number=player_id)
                if jersey_name or jersey_number is not None:
                    Jersey.objects.update_or_create(
                        player=player,
                        defaults={"jersey_name": jersey_name,
                                  "jersey_number": jersey_number or 0,
                                  "size_number": 0, "size_text": ""}
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
                team_id    = int(request.POST.get("team_id"))
                name       = request.POST.get("extra_name", "").strip()
                role_label = request.POST.get("extra_role", "").strip()
                jname      = request.POST.get("extra_jersey_name", "").strip()
                jnum_raw   = request.POST.get("extra_jersey_number", "").strip()
                jnum       = int(jnum_raw) if jnum_raw else None
                team       = Team.objects.get(team_serial_number=team_id)
                if name:
                    ExtraJerseyMember.objects.create(
                        name=name, role_label=role_label,
                        jersey_name=jname, jersey_number=jnum,
                        member_type=ExtraJerseyMember.TYPE_TEAM, team=team
                    )
                    msg = f"Added {name} to {team.name}."
            except Exception as e:
                msg = f"Error: {e}"

        # ── Add organiser member ──
        elif action == "add_organiser":
            try:
                name       = request.POST.get("org_name", "").strip()
                role_label = request.POST.get("org_role", "").strip()
                group_name = request.POST.get("org_group", "Organisers").strip() or "Organisers"
                jname      = request.POST.get("org_jersey_name", "").strip()
                jnum_raw   = request.POST.get("org_jersey_number", "").strip()
                jnum       = int(jnum_raw) if jnum_raw else None
                if name:
                    ExtraJerseyMember.objects.create(
                        name=name, role_label=role_label,
                        jersey_name=jname, jersey_number=jnum,
                        member_type=ExtraJerseyMember.TYPE_ORGANISER,
                        group_name=group_name
                    )
                    msg = f"Added organiser {name}."
            except Exception as e:
                msg = f"Error: {e}"

        # ── Update extra member jersey inline ──
        elif action == "update_extra":
            try:
                eid   = int(request.POST.get("extra_id"))
                jname = request.POST.get("jersey_name", "").strip()
                jnum_raw = request.POST.get("jersey_number", "").strip()
                jnum  = int(jnum_raw) if jnum_raw else None
                em    = ExtraJerseyMember.objects.get(pk=eid)
                em.jersey_name   = jname
                em.jersey_number = jnum
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

    return render(request, "jersey_management.html", {
        "team_sections":    team_sections,
        "org_groups":       org_groups,
        "org_group_names":  org_group_names,
        "msg":              msg,
        "config":           config,
    })


# ────────────────────────────────────────────────
# JERSEY AJAX SAVE (inline player row)
# ────────────────────────────────────────────────

@login_required
@csrf_exempt
def jersey_save_ajax(request):
    if request.method != "POST":
        return JsonResponse({"status": "invalid"})
    try:
        player_id     = int(request.POST.get("player_id"))
        jersey_name   = request.POST.get("jersey_name", "").strip()
        jersey_number_raw = request.POST.get("jersey_number", "").strip()
        jersey_number = int(jersey_number_raw) if jersey_number_raw else 0
        player = Player.objects.get(serial_number=player_id)
        Jersey.objects.update_or_create(
            player=player,
            defaults={"jersey_name": jersey_name, "jersey_number": jersey_number,
                      "size_number": 0, "size_text": ""}
        )
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})


# ────────────────────────────────────────────────
# EXPORT JERSEY PDF
# ────────────────────────────────────────────────

@login_required
def export_jersey_pdf(request):
    pdf_buffer = JerseyService().export_pdf()
    response   = HttpResponse(pdf_buffer, content_type="application/pdf")
    response["Content-Disposition"] = "attachment; filename=jersey_list.pdf"
    return response


# ────────────────────────────────────────────────
# FIXTURES — ADMIN
# ────────────────────────────────────────────────

@login_required
def fixtures_admin(request):
    """
    Admin page: spin wheel to generate matches one by one,
    or auto-generate full round-robin. Also record results.
    """
    teams   = list(Team.objects.all().order_by("name"))
    matches = Match.objects.select_related("team1", "team2", "winner").all()
    ts      = TournamentSettings.get()
    msg     = None

    if request.method == "POST":
        action = request.POST.get("action")

        # ── Create a single match from spin result ──
        if action == "create_match":
            t1_id = request.POST.get("team1_id")
            t2_id = request.POST.get("team2_id")
            round_label  = request.POST.get("round_label", "League").strip() or "League"
            sched        = request.POST.get("scheduled_date") or None
            venue        = request.POST.get("venue", "").strip()
            try:
                t1 = Team.objects.get(team_serial_number=t1_id)
                t2 = Team.objects.get(team_serial_number=t2_id)
                if t1 == t2:
                    msg = "Cannot create a match between the same team."
                elif Match.objects.filter(team1=t1, team2=t2).exists() or \
                     Match.objects.filter(team1=t2, team2=t1).exists():
                    msg = f"{t1.name} vs {t2.name} already exists."
                else:
                    next_num = (Match.objects.count() or 0) + 1
                    Match.objects.create(
                        match_number=next_num, round_label=round_label,
                        team1=t1, team2=t2,
                        scheduled_date=sched, venue=venue
                    )
                    msg = f"Match {next_num} created: {t1.name} vs {t2.name}"
            except Exception as e:
                msg = f"Error: {e}"

        # ── Generate full round-robin ──
        elif action == "generate_all":
            round_label = request.POST.get("round_label", "League").strip() or "League"
            sched       = request.POST.get("scheduled_date") or None
            venue       = request.POST.get("venue", "").strip()
            created = 0
            skipped = 0
            num = (Match.objects.count() or 0) + 1
            for i, t1 in enumerate(teams):
                for t2 in teams[i+1:]:
                    exists = (Match.objects.filter(team1=t1, team2=t2).exists() or
                              Match.objects.filter(team1=t2, team2=t1).exists())
                    if exists:
                        skipped += 1
                        continue
                    Match.objects.create(
                        match_number=num, round_label=round_label,
                        team1=t1, team2=t2,
                        scheduled_date=sched, venue=venue
                    )
                    num  += 1
                    created += 1
            msg = f"Generated {created} matches." + (f" Skipped {skipped} existing." if skipped else "")

        # ── Record result ──
        elif action == "record_result":
            match_id  = request.POST.get("match_id")
            winner_id = request.POST.get("winner_id")
            try:
                match = Match.objects.get(pk=match_id)
                if winner_id == "draw":
                    match.winner = None
                    match.notes  = request.POST.get("notes", "").strip() or "No result / Draw"
                else:
                    match.winner = Team.objects.get(team_serial_number=winner_id)
                match.status = Match.STATUS_COMPLETED
                match.save()
                msg = f"Result saved for Match {match.match_number}."
            except Exception as e:
                msg = f"Error: {e}"

        # ── Delete match ──
        elif action == "delete_match":
            try:
                m = Match.objects.get(pk=request.POST.get("match_id"))
                label = str(m)
                m.delete()
                # Renumber remaining
                for i, m2 in enumerate(Match.objects.all(), start=1):
                    if m2.match_number != i:
                        m2.match_number = i
                        m2.save()
                msg = f"Deleted {label}."
            except Exception as e:
                msg = f"Error: {e}"

        # ── Clear all matches ──
        elif action == "clear_all":
            Match.objects.all().delete()
            msg = "All matches cleared."

        matches = Match.objects.select_related("team1", "team2", "winner").all()

    # Points table
    points = _build_points_table(teams, matches)

    # Team colours for spin wheel (cycle through a palette)
    palette = ["#e74c3c","#3498db","#2ecc71","#f39c12","#9b59b6",
               "#1abc9c","#e67e22","#e91e63","#00bcd4","#8bc34a",
               "#ff5722","#607d8b"]
    for i, t in enumerate(teams):
        t.wheel_color = palette[i % len(palette)]

    return render(request, "fixtures_admin.html", {
        "teams":   teams,
        "matches": matches,
        "points":  points,
        "msg":     msg,
        "ts":      ts,
    })


# ────────────────────────────────────────────────
# FIXTURES — PUBLIC
# ────────────────────────────────────────────────

def fixtures_public(request):
    teams   = list(Team.objects.all().order_by("name"))
    matches = Match.objects.select_related("team1", "team2", "winner").all()
    ts      = TournamentSettings.get()
    points  = _build_points_table(teams, matches)

    # Group matches by round_label
    rounds = {}
    for m in matches:
        rounds.setdefault(m.round_label, []).append(m)

    return render(request, "fixtures_public.html", {
        "rounds":  rounds,
        "points":  points,
        "ts":      ts,
    })


# ────────────────────────────────────────────────
# SPIN RESULT — AJAX (returns random team)
# ────────────────────────────────────────────────

@csrf_exempt
def spin_result(request):
    """Returns a random team ID/name for the spin wheel landing."""
    import random
    exclude_id = request.POST.get("exclude_id")
    teams = Team.objects.all()
    if exclude_id:
        teams = teams.exclude(team_serial_number=exclude_id)
    if not teams.exists():
        return JsonResponse({"status": "error", "message": "No teams"})
    team = random.choice(list(teams))
    return JsonResponse({
        "status": "ok",
        "team_id":   team.team_serial_number,
        "team_name": team.name,
        "team_short": team.get_short(),
    })


# ────────────────────────────────────────────────
# INTERNAL: build points table
# ────────────────────────────────────────────────

def _build_points_table(teams, matches):
    table = {t.team_serial_number: {
        "team": t, "played": 0, "won": 0, "lost": 0, "points": 0
    } for t in teams}

    for m in matches:
        if m.status == Match.STATUS_COMPLETED:
            t1id = m.team1.team_serial_number
            t2id = m.team2.team_serial_number
            table[t1id]["played"] += 1
            table[t2id]["played"] += 1
            if m.winner:
                wid = m.winner.team_serial_number
                lid = t2id if wid == t1id else t1id
                table[wid]["won"]    += 1
                table[wid]["points"] += 2
                table[lid]["lost"]   += 1

    return sorted(table.values(), key=lambda x: (-x["points"], -x["won"]))
