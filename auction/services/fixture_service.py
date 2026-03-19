"""
Tournament fixture service.

Handles:
- Auto pool generation based on team count
- Round-robin match generation within pools
- Points table per pool
- Advancement calculation (with tie detection)
- Knockout stage generation
"""
import string
import logging
import traceback
from itertools import combinations

from auction.models import Team, Match, TournamentPool, PoolTeam

logger = logging.getLogger("auction")


# ─────────────────────────────────────────────
# Default pool config based on team count
# Returns (num_pools, teams_per_pool, advance_n)
# ─────────────────────────────────────────────

DEFAULT_POOL_CONFIG = {
    # team_count: (num_pools, advance_n)
    4:  (1, 2),
    6:  (2, 2),
    8:  (2, 2),
    9:  (3, 2),
    12: (3, 2),
    16: (4, 2),
    18: (6, 2),
    20: (5, 2),
    24: (6, 2),
}


def suggest_pool_config(team_count):
    """Return (num_pools, advance_n) suggestion for given team count."""
    if team_count in DEFAULT_POOL_CONFIG:
        return DEFAULT_POOL_CONFIG[team_count]
    # Best guess: pools of 4
    num_pools = max(1, round(team_count / 4))
    return num_pools, 2


def pool_names(n):
    """Return pool names: A, B, C... or Group 1, 2... for large counts."""
    if n <= 26:
        return list(string.ascii_uppercase[:n])
    return [str(i) for i in range(1, n + 1)]


# ─────────────────────────────────────────────
# Create pools and distribute teams
# ─────────────────────────────────────────────

def create_group_stage(num_pools, advance_n, teams_per_pool=4, team_ids=None, assignment_order="sequential"):
    """
    Create TournamentPool objects for group stage.
    assignment_order: "sequential" (fill pool A then B) or "roundrobin" (1 per pool, repeat)
    If team_ids given, distribute according to assignment_order.
    Returns list of created pools.
    """
    old_pools = TournamentPool.objects.filter(stage=TournamentPool.STAGE_GROUP)
    Match.objects.filter(pool__in=old_pools).delete()
    old_pools.delete()

    names = pool_names(num_pools)
    pools = []
    for i, name in enumerate(names):
        p = TournamentPool.objects.create(
            stage=TournamentPool.STAGE_GROUP,
            name=name,
            order=i,
            advance_n=advance_n,
            teams_per_pool=teams_per_pool,
            assignment_order=assignment_order,
        )
        pools.append(p)

    if team_ids:
        teams = list(Team.objects.filter(team_serial_number__in=team_ids).order_by("name"))
        if assignment_order == "sequential":
            # Fill pool A completely, then pool B, etc.
            for idx, team in enumerate(teams):
                pool_idx = idx // teams_per_pool
                seed     = idx % teams_per_pool
                if pool_idx < len(pools):
                    PoolTeam.objects.create(pool=pools[pool_idx], team=team, seed=seed)
        else:
            # Round-robin: 1 per pool, then repeat
            for idx, team in enumerate(teams):
                pool_idx = idx % num_pools
                seed     = idx // num_pools
                PoolTeam.objects.create(pool=pools[pool_idx], team=team, seed=seed)

    return pools


def add_team_to_pool(pool_id, team_id):
    """Add a team to a pool (used in drag-and-drop / manual assignment)."""
    pool = TournamentPool.objects.get(pk=pool_id)
    team = Team.objects.get(team_serial_number=team_id)
    pt, created = PoolTeam.objects.get_or_create(pool=pool, team=team,
                                                   defaults={"seed": 99})
    return pt


def remove_team_from_pool(pool_id, team_id):
    PoolTeam.objects.filter(pool_id=pool_id, team__team_serial_number=team_id).delete()


# ─────────────────────────────────────────────
# Generate round-robin matches within a pool
# ─────────────────────────────────────────────

def _round_robin_rounds(teams):
    """
    Generate matches using circle method — ensures each team
    plays exactly once per round (maximum rest between matches).
    Returns list of rounds, each round is a list of (team1, team2) pairs.
    """
    teams = list(teams)
    n = len(teams)
    if n % 2 == 1:
        teams.append(None)   # bye for odd counts
        n += 1

    rounds = []
    for _ in range(n - 1):
        round_matches = []
        for i in range(n // 2):
            t1 = teams[i]
            t2 = teams[n - 1 - i]
            if t1 is not None and t2 is not None:
                round_matches.append((t1, t2))
        rounds.append(round_matches)
        # Rotate: keep first fixed, rotate the rest
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]

    return rounds


def generate_pool_matches(pool_id):
    """
    Generate round-robin matches for a pool using circle method.
    Matches are created in round order so each team gets maximum rest.
    Returns (created_count, skipped_count).
    """
    pool  = TournamentPool.objects.get(pk=pool_id)
    teams = list(pool.teams.all().order_by("name"))

    rounds   = _round_robin_rounds(teams)
    created  = 0
    skipped  = 0
    next_num = (Match.objects.count() or 0) + 1

    for round_num, round_matches in enumerate(rounds, start=1):
        for t1, t2 in round_matches:
            exists = (
                Match.objects.filter(team1=t1, team2=t2, pool=pool).exists() or
                Match.objects.filter(team1=t2, team2=t1, pool=pool).exists()
            )
            if exists:
                skipped += 1
                continue
            Match.objects.create(
                match_number=next_num,
                round_label=f"Pool {pool.name}",
                team1=t1,
                team2=t2,
                pool=pool,
                notes=f"round:{round_num}",  # store round for scheduling
            )
            next_num += 1
            created  += 1

    try:
        _renumber_matches()
    except Exception as e:
        logger.error(f"_renumber_matches failed: {e}")
    logger.info(f"generate_pool_matches pool={pool_id}: {created} created, {skipped} skipped")
    return created, skipped


def generate_next_match(team_id=None, save=True):
    """
    Generate the next single match in round-robin order across all group pools.
    Follows the same circle-method round-robin logic as generate_pool_matches,
    but creates only one match at a time for spin-reveal draws.

    If team_id is given, the next undrawn match from that team's pool
    that actually involves that team is returned.

    If save=False, the match is found but not created in the DB.
    Returns a dict with match details, or None if all matches already generated.
    """
    pools = TournamentPool.objects.filter(stage=TournamentPool.STAGE_GROUP).order_by("order")

    # If a team was spun, try that team's pool first and specifically for that team
    if team_id:
        try:
            pt = PoolTeam.objects.select_related("pool").get(
                team__team_serial_number=team_id,
                pool__stage=TournamentPool.STAGE_GROUP,
            )
            result = _generate_next_match_in_pool(pt.pool, pools, team_id=team_id, save=save)
            if result:
                return result
        except PoolTeam.DoesNotExist:
            pass

    # Sequential fallback: generate next match in interleaved pool order
    # (Use next_pool_for_draw to find the most appropriate pool)
    target_pool = next_pool_for_draw()
    if target_pool:
        result = _generate_next_match_in_pool(target_pool, pools, save=save)
        if result:
            return result

    # Global fallback (should not be reached if next_pool_for_draw works)
    for pool in pools:
        result = _generate_next_match_in_pool(pool, pools, save=save)
        if result:
            return result
    return None


def _generate_next_match_in_pool(pool, all_pools, team_id=None, save=True):
    """
    Find and optionally create the next undrawn match within a single pool.
    If team_id is provided, ensures the match involves that team.
    Returns the match dict, or None if no matching undrawn pairs found.
    """
    teams = list(pool.teams.all().order_by("name"))
    rounds = _round_robin_rounds(teams)
    for round_num, round_matches in enumerate(rounds, start=1):
        for t1, t2 in round_matches:
            # Filter by team_id if provided
            if team_id:
                if t1.team_serial_number != int(team_id) and t2.team_serial_number != int(team_id):
                    continue

            exists = (
                Match.objects.filter(team1=t1, team2=t2, pool=pool).exists() or
                Match.objects.filter(team1=t2, team2=t1, pool=pool).exists()
            )
            if not exists:
                m_num = (Match.objects.count() or 0) + 1
                if save:
                    m = Match.objects.create(
                        match_number=m_num,
                        round_label=f"Pool {pool.name}",
                        team1=t1, team2=t2, pool=pool,
                        notes=f"round:{round_num}",
                    )
                    try:
                        _renumber_matches()
                        m.refresh_from_db()
                        m_num = m.match_number
                    except Exception:
                        pass
                
                remaining = _count_ungenerated_matches(all_pools)
                # If we didn't save yet, the match we just found is still 'remaining'
                if not save:
                    pass 

                # Ensure team1 in the response is the spun team if team_id given
                out_t1, out_t2 = t1, t2
                if team_id and t2.team_serial_number == int(team_id):
                    out_t1, out_t2 = t2, t1

                return {
                    "match_id": m.pk if save else None,
                    "match_number": m_num,
                    "team1": out_t1.name,
                    "team1_id": out_t1.team_serial_number,
                    "team2": out_t2.name,
                    "team2_id": out_t2.team_serial_number,
                    "pool": pool.name,
                    "pool_id": pool.pk,
                    "remaining": remaining,
                }
    return None


def _count_ungenerated_matches(pools):
    """Count total matches not yet generated across given pools."""
    total = 0
    for pool in pools:
        teams = list(pool.teams.all().order_by("name"))
        rounds = _round_robin_rounds(teams)
        for _, round_matches in enumerate(rounds):
            for t1, t2 in round_matches:
                exists = (
                    Match.objects.filter(team1=t1, team2=t2, pool=pool).exists() or
                    Match.objects.filter(team1=t2, team2=t1, pool=pool).exists()
                )
                if not exists:
                    total += 1
    return total


def _renumber_matches():
    """Renumber matches in interleaved schedule order so M1,M2,M3... match the display."""
    try:
        schedule = get_interleaved_schedule()
        if schedule:
            for i, m in enumerate(schedule, start=1):
                if m.match_number != i:
                    Match.objects.filter(pk=m.pk).update(match_number=i)
            return
    except Exception:
        pass
    # Fallback: simple sequential
    for i, m in enumerate(Match.objects.order_by("pool__order", "created_at"), start=1):
        if m.match_number != i:
            Match.objects.filter(pk=m.pk).update(match_number=i)


# ─────────────────────────────────────────────
# Points table per pool
# ─────────────────────────────────────────────

def pool_points_table(pool):
    """
    Returns list of dicts sorted by points desc, wins desc.
    Each dict: {team, played, won, lost, draw, points, for_wins, nrr}
    """
    teams   = list(pool.teams.all())
    matches = Match.objects.filter(pool=pool, status=Match.STATUS_COMPLETED)

    table = {t.team_serial_number: {
        "team": t, "played": 0, "won": 0, "lost": 0, "draw": 0, "points": 0
    } for t in teams}

    for m in matches:
        t1id = m.team1.team_serial_number
        t2id = m.team2.team_serial_number
        if t1id not in table or t2id not in table:
            continue
        table[t1id]["played"] += 1
        table[t2id]["played"] += 1
        if m.winner:
            wid = m.winner.team_serial_number
            lid = t2id if wid == t1id else t1id
            table[wid]["won"]    += 1
            table[wid]["points"] += 2
            table[lid]["lost"]   += 1
        else:
            # Draw / no result
            table[t1id]["draw"]   += 1
            table[t2id]["draw"]   += 1
            table[t1id]["points"] += 1
            table[t2id]["points"] += 1

    rows = sorted(table.values(), key=lambda x: (-x["points"], -x["won"]))
    return rows


def detect_ties(pool):
    """
    Returns list of groups of teams that are tied at the advancement boundary.
    e.g. if advance_n=2 and positions 2 and 3 have equal points → tie.
    """
    rows    = pool_points_table(pool)
    advance = pool.advance_n

    if len(rows) <= advance:
        return []  # everyone or no-one advances, no tie

    boundary_points = rows[advance - 1]["points"] if rows else 0
    # Check if the team just outside the boundary has same points
    if len(rows) > advance:
        outside_points = rows[advance]["points"]
        if outside_points == boundary_points:
            # Find all teams with this points value
            tied = [r for r in rows if r["points"] == boundary_points]
            return tied
    return []


def advance_teams(pool_id, team_ids):
    """
    Mark specified teams as advanced from this pool.
    team_ids: list of team_serial_numbers to advance.
    """
    pool = TournamentPool.objects.get(pk=pool_id)
    # Clear existing advancement
    PoolTeam.objects.filter(pool=pool).update(advanced=False, position=None)

    for rank, tid in enumerate(team_ids, start=1):
        PoolTeam.objects.filter(pool=pool, team__team_serial_number=tid).update(
            advanced=True, position=rank
        )
    pool.is_locked = True
    pool.save()


# ─────────────────────────────────────────────
# Knockout stage generation
# ─────────────────────────────────────────────

def get_advanced_teams(stage=TournamentPool.STAGE_GROUP):
    """Return teams that advanced from the given stage, ordered by pool then position."""
    return list(Team.objects.filter(
        pools__stage=stage,
        poolteam__advanced=True
    ).order_by("pools__order", "poolteam__position").distinct())


def create_knockout_stage(stage, team_ids, match_label=None):
    """
    Create a knockout stage (SF, Final, etc.) with given teams.
    Pairs teams 1v4, 2v3 etc. (seeded bracket).
    Returns list of Match objects created.
    """
    next_num = (Match.objects.count() or 0) + 1
    teams    = list(Team.objects.filter(team_serial_number__in=team_ids))
    # Sort by provided order
    order_map = {tid: i for i, tid in enumerate(team_ids)}
    teams.sort(key=lambda t: order_map.get(t.team_serial_number, 999))

    label   = match_label or stage
    n       = len(teams)
    matches = []

    if stage in (TournamentPool.STAGE_SF, TournamentPool.STAGE_QF):
        # Seed pairing: 1v(n), 2v(n-1) ...
        for i in range(n // 2):
            m = Match.objects.create(
                match_number=next_num,
                round_label=label,
                team1=teams[i],
                team2=teams[n - 1 - i],
            )
            matches.append(m)
            next_num += 1
    else:
        # Final / custom: just pair sequentially
        for i in range(0, n, 2):
            if i + 1 < n:
                m = Match.objects.create(
                    match_number=next_num,
                    round_label=label,
                    team1=teams[i],
                    team2=teams[i + 1],
                )
                matches.append(m)
                next_num += 1

    _renumber_matches()
    return matches


# ─────────────────────────────────────────────
# Summary helpers
# ─────────────────────────────────────────────

def all_pools_status():
    """
    Returns list of {pool, rows, ties, done, total, can_advance, advanced_ids}.
    advanced_ids is a set of team_serial_numbers that have been marked as advanced.
    """
    result = []
    for pool in TournamentPool.objects.prefetch_related("teams", "matches").all():
        rows          = pool_points_table(pool)
        ties          = detect_ties(pool)
        total_matches = pool.matches.count()
        done_matches  = pool.matches.filter(status=Match.STATUS_COMPLETED).count()
        can_advance   = (total_matches > 0 and done_matches == total_matches and not ties)
        # Pre-compute which teams have advanced so templates don't need ORM calls
        advanced_ids  = set(
            PoolTeam.objects.filter(pool=pool, advanced=True)
            .values_list("team__team_serial_number", flat=True)
        )
        result.append({
            "pool":          pool,
            "rows":          rows,
            "ties":          ties,
            "done":          done_matches,
            "total":         total_matches,
            "can_advance":   can_advance,
            "advanced_ids":  advanced_ids,
        })
    return result


# ─────────────────────────────────────────────
# Interleaved fixture draw helpers
# ─────────────────────────────────────────────

def next_pool_for_draw():
    """
    Returns the next TournamentPool that needs a fixture drawn.
    Interleaved order: pool with fewest drawn matches goes next.
    Ties broken by pool order.
    Returns None if all fixtures are drawn.
    """
    pools = list(TournamentPool.objects.filter(
        stage=TournamentPool.STAGE_GROUP
    ).order_by("order"))

    if not pools:
        return None

    # Count drawn matches per pool
    draw_counts = []
    for pool in pools:
        expected = len(list(combinations(range(pool.teams.count()), 2)))
        drawn    = pool.matches.count()
        if drawn < expected:
            draw_counts.append((drawn, pool.order, pool))

    if not draw_counts:
        return None  # all done

    draw_counts.sort(key=lambda x: (x[0], x[1]))
    return draw_counts[0][2]


def pool_undrawn_pairs(pool):
    """
    Returns list of (team1, team2) pairs in this pool that don't yet have a match.
    """
    teams = list(pool.teams.all().order_by("name"))
    existing = set()
    for m in pool.matches.all():
        a = m.team1.team_serial_number
        b = m.team2.team_serial_number
        existing.add((min(a,b), max(a,b)))

    pairs = []
    for t1, t2 in combinations(teams, 2):
        a = t1.team_serial_number
        b = t2.team_serial_number
        if (min(a,b), max(a,b)) not in existing:
            pairs.append((t1, t2))
    return pairs


def create_interleaved_match(pool, team1_id, team2_id):
    """Create a single match between two teams in the given pool."""
    t1 = Team.objects.get(team_serial_number=team1_id)
    t2 = Team.objects.get(team_serial_number=team2_id)

    # Check pair doesn't already exist
    if (Match.objects.filter(pool=pool, team1=t1, team2=t2).exists() or
            Match.objects.filter(pool=pool, team1=t2, team2=t1).exists()):
        raise ValueError(f"{t1.name} vs {t2.name} already exists in Pool {pool.name}")

    next_num = (Match.objects.count() or 0) + 1
    m = Match.objects.create(
        match_number=next_num,
        round_label=f"Pool {pool.name}",
        team1=t1,
        team2=t2,
        pool=pool,
    )
    _renumber_matches()
    return m


def get_interleaved_schedule():
    """
    Day-pair interleaved schedule with rest optimisation.

    Day grouping:  pools are paired by their order index:
        Day 1 → pools at index 0, 1  (A, B)
        Day 2 → pools at index 2, 3  (C, D)
        Day 3 → pools at index 4, 5  (E, F)  etc.

    Within each day, matches are ordered:
        Pair_A Round1_m1, Pair_B Round1_m1,
        Pair_A Round1_m2, Pair_B Round1_m2,
        Pair_A Round2_m1, Pair_B Round2_m1, ...

    This means:
    - A team in Pool A plays match 1, then has Pool B's whole
      round before their next match (maximum rest).
    - Within each pool the circle-method round ordering ensures
      no team plays two matches in a row.
    """
    pools = list(TournamentPool.objects.filter(
        stage=TournamentPool.STAGE_GROUP
    ).order_by("order"))

    if not pools:
        return []

    # Group matches by pool, ordered by creation (= round order)
    pool_matches = {}
    for pool in pools:
        # Group by round number stored in notes
        rounds_map = {}
        for m in pool.matches.select_related("team1","team2","winner").order_by("created_at"):
            rnum = 1
            if m.notes and m.notes.startswith("round:"):
                try: rnum = int(m.notes.split(":")[1])
                except: pass
            rounds_map.setdefault(rnum, []).append(m)
        pool_matches[pool.pk] = [
            rounds_map[r] for r in sorted(rounds_map)
        ]  # list of rounds, each round is a list of matches

    # Pair pools into days: (pools[0], pools[1]), (pools[2], pools[3]), ...
    schedule = []
    for day_idx in range(0, len(pools), 2):
        day_pools = pools[day_idx:day_idx + 2]

        # Find max rounds across this day's pools
        max_rounds = max(
            (len(pool_matches.get(p.pk, [])) for p in day_pools), default=0
        )

        for round_idx in range(max_rounds):
            # Within each round, interleave matches from the two pools
            # Get matches for this round from each pool
            round_slices = []
            for p in day_pools:
                rounds = pool_matches.get(p.pk, [])
                if round_idx < len(rounds):
                    round_slices.append(rounds[round_idx])
                else:
                    round_slices.append([])

            # Interleave: p1_m1, p2_m1, p1_m2, p2_m2, ...
            max_in_round = max((len(s) for s in round_slices), default=0)
            for match_idx in range(max_in_round):
                for rs in round_slices:
                    if match_idx < len(rs):
                        schedule.append(rs[match_idx])

    return schedule
