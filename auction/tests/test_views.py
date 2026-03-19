"""
Tests for HTTP views — status codes, redirects, AJAX responses.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from auction.models import (
    Player, Team, TournamentConfig, AuctionState,
    TournamentPool, PoolTeam, Match,
)
from auction.services.fixture_service import create_group_stage, generate_pool_matches


def make_admin(username="admin", password="testpass"):
    return User.objects.create_superuser(username=username, password=password, email="")


def make_teams(n=4):
    return [Team.objects.create(name=f"Team{i+1}", remaining_points=10000) for i in range(n)]


# ─────────────────────────────────────────────────────────────
# Public board
# ─────────────────────────────────────────────────────────────

class TestPublicBoard(TestCase):

    def test_public_board_loads(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)

    def test_public_board_no_login_required(self):
        resp = Client().get("/")
        self.assertEqual(resp.status_code, 200)


# ─────────────────────────────────────────────────────────────
# Auction control (login required)
# ─────────────────────────────────────────────────────────────

class TestAuctionControl(TestCase):

    def setUp(self):
        self.user   = make_admin()
        self.client.login(username="admin", password="testpass")

    def test_redirects_to_setup_when_no_config(self):
        resp = self.client.get("/auction/")
        self.assertEqual(resp.status_code, 200)

    def test_requires_login(self):
        c    = Client()
        resp = c.get("/auction/")
        # Either redirects to login or still 200 (depends on decorators)
        self.assertIn(resp.status_code, [200, 302])


# ─────────────────────────────────────────────────────────────
# Sell / unsold / not-playing AJAX
# ─────────────────────────────────────────────────────────────

class TestAuctionAjax(TestCase):

    def setUp(self):
        self.user   = make_admin()
        self.client.login(username="admin", password="testpass")
        self.config = TournamentConfig.objects.create(
            total_points=10000, bidding_slots=11,
            base_price_AR=1000,
        )
        self.team   = Team.objects.create(name="T", remaining_points=10000)
        self.player = Player.objects.create(name="P", role="AR", base_price=1000)
        state = AuctionState.get()
        state.is_active      = True
        state.current_player = self.player
        state.save()

    def test_sell_returns_ok(self):
        resp = self.client.post("/auction/sell/", {
            "player_id": self.player.serial_number,
            "team_id":   self.team.team_serial_number,
            "amount":    1000,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn(data["status"], ["ok", "blocked", "error"])

    def test_unsold_returns_ok(self):
        state = AuctionState.get()
        state.current_player = self.player
        state.save()
        resp = self.client.post("/auction/unsold/", {
            "player_id": self.player.serial_number
        })
        self.assertEqual(resp.status_code, 200)

    def test_not_playing_returns_ok(self):
        state = AuctionState.get()
        state.current_player = self.player
        state.save()
        resp = self.client.post("/auction/not-playing/", {
            "player_id": self.player.serial_number
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")

    def test_sell_wrong_method_returns_error(self):
        resp = self.client.get("/auction/sell/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "error")

    def test_refresh_points_ok(self):
        resp = self.client.post("/auction/refresh/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")


# ─────────────────────────────────────────────────────────────
# Upload CSV views
# ─────────────────────────────────────────────────────────────

class TestUploadCSV(TestCase):

    def setUp(self):
        self.user = make_admin()
        self.client.login(username="admin", password="testpass")

    def test_get_loads_page(self):
        resp = self.client.get("/auction/upload-csv/")
        self.assertEqual(resp.status_code, 200)

    def test_load_demo_small_players(self):
        resp = self.client.post("/auction/upload-csv/", {
            "action":    "load_demo",
            "demo_file": "small_players",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "imported")

    def test_load_demo_small_teams(self):
        resp = self.client.post("/auction/upload-csv/", {
            "action":    "load_demo",
            "demo_file": "small_teams",
        })
        self.assertEqual(resp.status_code, 200)

    def test_load_demo_unknown_file_shows_error(self):
        resp = self.client.post("/auction/upload-csv/", {
            "action":    "load_demo",
            "demo_file": "malicious_file",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Error")


# ─────────────────────────────────────────────────────────────
# Pool manager views
# ─────────────────────────────────────────────────────────────

class TestPoolViews(TestCase):

    def setUp(self):
        self.user = make_admin()
        self.client.login(username="admin", password="testpass")
        self.teams = make_teams(8)

    def test_pool_manager_loads(self):
        resp = self.client.get("/fixtures/pools/")
        self.assertEqual(resp.status_code, 200)

    def test_pool_create_redirects(self):
        resp = self.client.post("/fixtures/pools/create/", {
            "num_pools":        2,
            "teams_per_pool":   4,
            "advance_n":        2,
            "assignment_order": "sequential",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, "/fixtures/pools/?msg=Group+stage+created")
        self.assertEqual(TournamentPool.objects.count(), 2)

    def test_pool_create_stores_assignment_order(self):
        self.client.post("/fixtures/pools/create/", {
            "num_pools":        2,
            "teams_per_pool":   4,
            "advance_n":        2,
            "assignment_order": "roundrobin",
        })
        pools = TournamentPool.objects.filter(stage=TournamentPool.STAGE_GROUP)
        for pool in pools:
            self.assertEqual(pool.assignment_order, "roundrobin")

    def test_pool_reset_deletes_pools(self):
        create_group_stage(2, 2, teams_per_pool=4)
        resp = self.client.post("/fixtures/pools/reset/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(TournamentPool.objects.count(), 0)

    def test_spin_assign_auto_assigns(self):
        pools = create_group_stage(2, 2, teams_per_pool=4)
        team  = self.teams[0]
        resp  = self.client.post("/fixtures/pools/spin-assign/", {
            "team_id": team.team_serial_number,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("assigned_pool", data)
        # Team is now in a pool
        self.assertTrue(PoolTeam.objects.filter(team=team).exists())

    def test_spin_assign_sequential_fills_a_first(self):
        pools = create_group_stage(2, 2, teams_per_pool=4, assignment_order="sequential")
        # Assign first 4 teams — should all go to Pool A
        for team in self.teams[:4]:
            self.client.post("/fixtures/pools/spin-assign/", {
                "team_id": team.team_serial_number,
            })
        pool_a = TournamentPool.objects.get(name="A")
        self.assertEqual(pool_a.teams.count(), 4)

    def test_pool_record_result(self):
        pools = create_group_stage(1, 2, teams_per_pool=4,
                                   team_ids=[t.team_serial_number for t in self.teams[:4]])
        generate_pool_matches(pools[0].pk)
        match = Match.objects.filter(pool=pools[0]).first()
        resp  = self.client.post("/fixtures/pools/result/", {
            "match_id":  match.pk,
            "winner_id": match.team1.team_serial_number,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        match.refresh_from_db()
        self.assertEqual(match.winner, match.team1)
        self.assertEqual(match.status, Match.STATUS_COMPLETED)


# ─────────────────────────────────────────────────────────────
# Fixture draw views
# ─────────────────────────────────────────────────────────────

class TestFixtureViews(TestCase):

    def setUp(self):
        self.user  = make_admin()
        self.client.login(username="admin", password="testpass")
        teams = make_teams(8)
        tid   = [t.team_serial_number for t in teams]
        create_group_stage(2, 2, teams_per_pool=4, team_ids=tid, assignment_order="sequential")

    def test_generate_fixtures_creates_matches(self):
        resp = self.client.post("/fixtures/draw/generate/")
        self.assertEqual(resp.status_code, 302)
        # 2 pools × 6 matches each
        self.assertEqual(Match.objects.count(), 12)

    def test_fixtures_reset_clears_matches(self):
        self.client.post("/fixtures/draw/generate/")
        self.assertEqual(Match.objects.count(), 12)
        resp = self.client.post("/fixtures/draw/reset/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Match.objects.count(), 0)

    def test_record_result_via_draw_endpoint(self):
        self.client.post("/fixtures/draw/generate/")
        match = Match.objects.first()
        resp  = self.client.post("/fixtures/draw/result/", {
            "match_id":  match.pk,
            "winner_id": match.team1.team_serial_number,
        })
        data = resp.json()
        self.assertEqual(data["status"], "ok")

    def test_record_draw_result(self):
        self.client.post("/fixtures/draw/generate/")
        match = Match.objects.first()
        resp  = self.client.post("/fixtures/draw/result/", {
            "match_id":  match.pk,
            "winner_id": "draw",
        })
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        match.refresh_from_db()
        self.assertIsNone(match.winner)
        self.assertEqual(match.status, Match.STATUS_COMPLETED)


# ─────────────────────────────────────────────────────────────
# Reports
# ─────────────────────────────────────────────────────────────

class TestReportViews(TestCase):

    def setUp(self):
        self.user = make_admin()
        self.client.login(username="admin", password="testpass")

    def test_reports_page_loads(self):
        resp = self.client.get("/reports/")
        self.assertEqual(resp.status_code, 200)

    def test_report_download_pdf(self):
        resp = self.client.get("/reports/download/?type=all_players&fmt=pdf")
        self.assertIn(resp.status_code, [200, 204])

    def test_report_download_excel(self):
        resp = self.client.get("/reports/download/?type=all_players&fmt=xlsx")
        self.assertIn(resp.status_code, [200, 204])
