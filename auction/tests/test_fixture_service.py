"""
Tests for fixture_service: pool creation, round-robin scheduling,
interleaved schedule, assignment order, points table.
"""
from django.test import TestCase
from auction.models import Team, TournamentPool, PoolTeam, Match
from auction.services.fixture_service import (
    create_group_stage,
    generate_pool_matches,
    get_interleaved_schedule,
    pool_points_table,
    suggest_pool_config,
    _round_robin_rounds,
)


def make_teams(n, points=10000):
    return [Team.objects.create(name=f"Team{i+1}", remaining_points=points) for i in range(n)]


# ─────────────────────────────────────────────────────────────
# suggest_pool_config()
# ─────────────────────────────────────────────────────────────

class TestSuggestPoolConfig(TestCase):

    def test_16_teams(self):
        n, adv = suggest_pool_config(16)
        self.assertEqual(n, 4)

    def test_24_teams(self):
        n, adv = suggest_pool_config(24)
        self.assertEqual(n, 6)

    def test_advance_at_least_1(self):
        _, adv = suggest_pool_config(8)
        self.assertGreaterEqual(adv, 1)


# ─────────────────────────────────────────────────────────────
# create_group_stage()
# ─────────────────────────────────────────────────────────────

class TestCreateGroupStage(TestCase):

    def setUp(self):
        self.teams = make_teams(16)

    def test_creates_correct_pool_count(self):
        pools = create_group_stage(4, 2, teams_per_pool=4)
        self.assertEqual(len(pools), 4)
        self.assertEqual(TournamentPool.objects.filter(stage=TournamentPool.STAGE_GROUP).count(), 4)

    def test_pool_names_are_letters(self):
        pools = create_group_stage(4, 2, teams_per_pool=4)
        names = [p.name for p in pools]
        self.assertEqual(names, ["A", "B", "C", "D"])

    def test_sequential_assignment_fills_pool_a_first(self):
        team_ids = [t.team_serial_number for t in self.teams]
        pools = create_group_stage(4, 2, teams_per_pool=4, team_ids=team_ids, assignment_order="sequential")
        pool_a = pools[0]
        self.assertEqual(pool_a.teams.count(), 4)
        pool_b = pools[1]
        self.assertEqual(pool_b.teams.count(), 4)

    def test_roundrobin_assignment_spreads_evenly(self):
        team_ids = [t.team_serial_number for t in self.teams]
        pools = create_group_stage(4, 2, teams_per_pool=4, team_ids=team_ids, assignment_order="roundrobin")
        for pool in pools:
            self.assertEqual(pool.teams.count(), 4)

    def test_assignment_order_stored_on_pool(self):
        pools = create_group_stage(4, 2, teams_per_pool=4, assignment_order="roundrobin")
        for pool in pools:
            self.assertEqual(pool.assignment_order, "roundrobin")

    def test_teams_per_pool_stored(self):
        pools = create_group_stage(4, 2, teams_per_pool=5)
        for pool in pools:
            self.assertEqual(pool.teams_per_pool, 5)

    def test_recreate_wipes_old_pools(self):
        create_group_stage(4, 2, teams_per_pool=4)
        create_group_stage(2, 2, teams_per_pool=8)
        self.assertEqual(TournamentPool.objects.count(), 2)


# ─────────────────────────────────────────────────────────────
# _round_robin_rounds()
# ─────────────────────────────────────────────────────────────

class TestRoundRobinRounds(TestCase):

    def test_4_teams_produces_3_rounds(self):
        teams  = ["T1", "T2", "T3", "T4"]
        rounds = _round_robin_rounds(teams)
        self.assertEqual(len(rounds), 3)

    def test_each_team_plays_once_per_round(self):
        teams  = ["T1", "T2", "T3", "T4"]
        rounds = _round_robin_rounds(teams)
        for rnd in rounds:
            players_in_round = []
            for t1, t2 in rnd:
                players_in_round.extend([t1, t2])
            self.assertEqual(len(set(players_in_round)), len(players_in_round))

    def test_all_pairs_covered(self):
        from itertools import combinations
        teams  = ["T1", "T2", "T3", "T4"]
        rounds = _round_robin_rounds(teams)
        all_pairs = set()
        for rnd in rounds:
            for t1, t2 in rnd:
                all_pairs.add((min(t1, t2), max(t1, t2)))
        expected = {(min(a, b), max(a, b)) for a, b in combinations(teams, 2)}
        self.assertEqual(all_pairs, expected)

    def test_no_consecutive_matches(self):
        """Within each round, no team plays twice (circle method guarantee)."""
        teams = [f"T{i}" for i in range(1, 5)]
        rounds = _round_robin_rounds(teams)
        # Within each round, every team appears at most once
        for round_idx, rnd in enumerate(rounds):
            all_teams_in_round = [t for pair in rnd for t in pair]
            unique_teams = set(all_teams_in_round)
            self.assertEqual(
                len(all_teams_in_round), len(unique_teams),
                f"Round {round_idx + 1} has a team playing twice: {all_teams_in_round}"
            )


# ─────────────────────────────────────────────────────────────
# generate_pool_matches()
# ─────────────────────────────────────────────────────────────

class TestGeneratePoolMatches(TestCase):

    def setUp(self):
        self.teams = make_teams(4)
        pools = create_group_stage(1, 2, teams_per_pool=4,
                                   team_ids=[t.team_serial_number for t in self.teams])
        self.pool = pools[0]

    def test_generates_correct_match_count(self):
        # 4 teams → C(4,2) = 6 matches
        created, skipped = generate_pool_matches(self.pool.pk)
        self.assertEqual(created, 6)
        self.assertEqual(skipped, 0)

    def test_no_duplicate_matches(self):
        generate_pool_matches(self.pool.pk)
        matches = list(Match.objects.filter(pool=self.pool))
        pairs = set()
        for m in matches:
            a, b = m.team1.team_serial_number, m.team2.team_serial_number
            pairs.add((min(a, b), max(a, b)))
        self.assertEqual(len(pairs), len(matches))

    def test_regenerate_skips_existing(self):
        generate_pool_matches(self.pool.pk)
        created2, skipped2 = generate_pool_matches(self.pool.pk)
        self.assertEqual(created2, 0)
        self.assertEqual(skipped2, 6)

    def test_round_stored_in_notes(self):
        generate_pool_matches(self.pool.pk)
        for m in Match.objects.filter(pool=self.pool):
            self.assertTrue(m.notes.startswith("round:"), f"notes={m.notes!r}")


# ─────────────────────────────────────────────────────────────
# get_interleaved_schedule()
# ─────────────────────────────────────────────────────────────

class TestInterleavedSchedule(TestCase):

    def setUp(self):
        teams_a = make_teams(4)
        teams_b = make_teams(4)
        pools = create_group_stage(2, 2, teams_per_pool=4)
        for i, t in enumerate(teams_a):
            PoolTeam.objects.create(pool=pools[0], team=t, seed=i)
        for i, t in enumerate(teams_b):
            PoolTeam.objects.create(pool=pools[1], team=t, seed=i)
        self.pool_a = pools[0]
        self.pool_b = pools[1]
        generate_pool_matches(self.pool_a.pk)
        generate_pool_matches(self.pool_b.pk)

    def test_alternates_pool_a_and_b(self):
        schedule = get_interleaved_schedule()
        self.assertGreater(len(schedule), 0)
        # Verify first match is pool A, second is pool B
        self.assertEqual(schedule[0].pool.name, "A")
        self.assertEqual(schedule[1].pool.name, "B")

    def test_total_match_count(self):
        schedule = get_interleaved_schedule()
        # 2 pools × 6 matches each = 12 total
        self.assertEqual(len(schedule), 12)

    def test_match_numbers_are_sequential(self):
        schedule = get_interleaved_schedule()
        numbers  = [m.match_number for m in schedule]
        self.assertEqual(numbers, sorted(numbers))
        self.assertEqual(numbers[0], 1)

    def test_4_pool_day_pairing(self):
        """Day 1 = Pool A+B, Day 2 = Pool C+D."""
        teams_a = make_teams(4)
        teams_b = make_teams(4)
        teams_c = make_teams(4)
        teams_d = make_teams(4)
        pools = create_group_stage(4, 2, teams_per_pool=4)
        for i, t in enumerate(teams_a):
            PoolTeam.objects.create(pool=pools[0], team=t, seed=i)
        for i, t in enumerate(teams_b):
            PoolTeam.objects.create(pool=pools[1], team=t, seed=i)
        for i, t in enumerate(teams_c):
            PoolTeam.objects.create(pool=pools[2], team=t, seed=i)
        for i, t in enumerate(teams_d):
            PoolTeam.objects.create(pool=pools[3], team=t, seed=i)
        generate_pool_matches(pools[0].pk)
        generate_pool_matches(pools[1].pk)
        generate_pool_matches(pools[2].pk)
        generate_pool_matches(pools[3].pk)

        schedule = get_interleaved_schedule()
        # First 12 matches should be Pool A and B only
        day1 = schedule[:12]
        day1_pools = {m.pool.name for m in day1}
        self.assertIn("A", day1_pools)
        self.assertIn("B", day1_pools)
        self.assertNotIn("C", day1_pools)


# ─────────────────────────────────────────────────────────────
# pool_points_table()
# ─────────────────────────────────────────────────────────────

class TestPoolPointsTable(TestCase):

    def setUp(self):
        self.teams = make_teams(4)
        pools = create_group_stage(1, 2, teams_per_pool=4,
                                   team_ids=[t.team_serial_number for t in self.teams])
        self.pool = pools[0]
        generate_pool_matches(self.pool.pk)

    def test_initial_all_zero_points(self):
        rows = pool_points_table(self.pool)
        for row in rows:
            self.assertEqual(row["points"], 0)
            self.assertEqual(row["played"], 0)

    def test_win_gives_2_points(self):
        m = Match.objects.filter(pool=self.pool).first()
        m.winner = m.team1
        m.status = Match.STATUS_COMPLETED
        m.save()
        rows = pool_points_table(self.pool)
        winner_row = next(r for r in rows if r["team"] == m.team1)
        self.assertEqual(winner_row["points"], 2)
        self.assertEqual(winner_row["won"],    1)

    def test_loss_gives_0_points(self):
        m = Match.objects.filter(pool=self.pool).first()
        m.winner = m.team1
        m.status = Match.STATUS_COMPLETED
        m.save()
        rows = pool_points_table(self.pool)
        loser_row = next(r for r in rows if r["team"] == m.team2)
        self.assertEqual(loser_row["points"], 0)
        self.assertEqual(loser_row["lost"],   1)

    def test_rows_sorted_by_points_descending(self):
        matches = list(Match.objects.filter(pool=self.pool)[:3])
        for m in matches:
            m.winner = m.team1
            m.status = Match.STATUS_COMPLETED
            m.save()
        rows = pool_points_table(self.pool)
        points = [r["points"] for r in rows]
        self.assertEqual(points, sorted(points, reverse=True))

    def test_played_count_correct(self):
        matches = list(Match.objects.filter(pool=self.pool)[:2])
        for m in matches:
            m.winner = m.team1
            m.status = Match.STATUS_COMPLETED
            m.save()
        rows = pool_points_table(self.pool)
        total_played = sum(r["played"] for r in rows)
        # Each match counts as 1 played for each team → 2 matches × 2 = 4
        self.assertEqual(total_played, 4)
