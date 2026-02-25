import pytest
from cricket.services.auction_engine import AuctionEngine
from cricket.models import Player, Team


@pytest.mark.django_db
def test_start_auction():
    control = AuctionEngine.start_auction()
    assert control.is_started is True
    assert control.current_stage == "BAT"


@pytest.mark.django_db
def test_invalid_stage_jump():
    AuctionEngine.start_auction()

    with pytest.raises(Exception):
        AuctionEngine.change_stage("AR")


@pytest.mark.django_db
def test_random_picker_selects_unsold_player():
    AuctionEngine.start_auction()

    Player.objects.create(serial_number=1, name="A", role="BAT")
    Player.objects.create(serial_number=2, name="B", role="BAT", status="NOT_PLAYING")

    player = AuctionEngine.pick_random_player()

    assert player.status == "UNSOLD"
    assert player.role == "BAT"


@pytest.mark.django_db
def test_sell_player_success():
    AuctionEngine.start_auction()

    team = Team.objects.create(name="Team1")
    Player.objects.create(serial_number=10, name="X", role="BAT")

    AuctionEngine.pick_random_player()
    sold_player = AuctionEngine.sell_current_player(team.id, 1000)

    team.refresh_from_db()
    sold_player.refresh_from_db()

    assert sold_player.status == "SOLD"
    assert sold_player.team == team
    assert team.remaining_points == 9000
    assert team.auction_slots == 10


@pytest.mark.django_db
def test_sell_player_budget_fail():
    AuctionEngine.start_auction()

    team = Team.objects.create(name="Team2", total_points=500, remaining_points=500)
    Player.objects.create(serial_number=20, name="Y", role="BAT")

    AuctionEngine.pick_random_player()

    with pytest.raises(Exception):
        AuctionEngine.sell_current_player(team.id, 1000)


@pytest.mark.django_db
def test_mark_unsold():
    AuctionEngine.start_auction()

    Player.objects.create(serial_number=30, name="Z", role="BAT")

    AuctionEngine.pick_random_player()
    player = AuctionEngine.mark_unsold()

    assert player.status == "UNSOLD"


@pytest.mark.django_db
def test_mark_not_playing():
    AuctionEngine.start_auction()

    Player.objects.create(serial_number=40, name="W", role="BAT")

    AuctionEngine.pick_random_player()
    player = AuctionEngine.mark_not_playing()

    assert player.status == "NOT_PLAYING"


@pytest.mark.django_db
def test_undo_sell():
    AuctionEngine.start_auction()

    team = Team.objects.create(name="UndoTeam")
    Player.objects.create(serial_number=50, name="UndoPlayer", role="BAT")

    AuctionEngine.pick_random_player()
    AuctionEngine.sell_current_player(team.id, 1000)

    team.refresh_from_db()
    assert team.remaining_points == 9000

    AuctionEngine.undo_last_action()

    team.refresh_from_db()
    player = Player.objects.get(serial_number=50)

    assert team.remaining_points == 10000
    assert team.auction_slots == 11
    assert player.status == "UNSOLD"
    assert player.team is None


@pytest.mark.django_db
def test_icon_first_round_enforcement():
    AuctionEngine.start_auction()

    team1 = Team.objects.create(name="T1")
    team2 = Team.objects.create(name="T2")

    Player.objects.create(serial_number=60, name="P1", role="BAT")
    Player.objects.create(serial_number=61, name="P2", role="BAT")

    AuctionEngine.pick_random_player()
    AuctionEngine.sell_current_player(team1.id, 1000)

    AuctionEngine.pick_random_player()

    with pytest.raises(Exception):
        AuctionEngine.sell_current_player(team1.id, 1000)


@pytest.mark.django_db
def test_icon_less_than_teams_no_restriction():
    AuctionEngine.start_auction()

    team1 = Team.objects.create(name="L1")
    team2 = Team.objects.create(name="L2")
    team3 = Team.objects.create(name="L3")

    Player.objects.create(serial_number=300, name="P1", role="BAT")
    Player.objects.create(serial_number=301, name="P2", role="BAT")

    AuctionEngine.pick_random_player()
    AuctionEngine.sell_current_player(team1.id, 1000)

    AuctionEngine.pick_random_player()
    AuctionEngine.sell_current_player(team1.id, 1000)

    team1.refresh_from_db()
    assert team1.auction_slots == 9


@pytest.mark.django_db
def test_icon_second_round_allowed():
    AuctionEngine.start_auction()

    team1 = Team.objects.create(name="S1")
    team2 = Team.objects.create(name="S2")

    for i in range(400, 404):
        Player.objects.create(serial_number=i, name=f"P{i}", role="BAT")

    AuctionEngine.pick_random_player()
    AuctionEngine.sell_current_player(team1.id, 1000)

    AuctionEngine.pick_random_player()
    AuctionEngine.sell_current_player(team2.id, 1000)

    AuctionEngine.pick_random_player()
    AuctionEngine.sell_current_player(team1.id, 1000)

    team1.refresh_from_db()
    assert team1.auction_slots == 9

@pytest.mark.django_db
def test_pick_without_start():
    Player.objects.create(serial_number=700, name="A", role="BAT")

    with pytest.raises(Exception):
        AuctionEngine.pick_random_player()


@pytest.mark.django_db
def test_sell_without_pick():
    AuctionEngine.start_auction()

    team = Team.objects.create(name="T")
    with pytest.raises(Exception):
        AuctionEngine.sell_current_player(team.id, 1000)


@pytest.mark.django_db
def test_negative_price():
    AuctionEngine.start_auction()

    team = Team.objects.create(name="T")
    Player.objects.create(serial_number=701, name="A", role="BAT")

    AuctionEngine.pick_random_player()

    with pytest.raises(Exception):
        AuctionEngine.sell_current_player(team.id, -100)


@pytest.mark.django_db
def test_no_slots_remaining():
    AuctionEngine.start_auction()

    team = Team.objects.create(name="T", auction_slots=0)
    Player.objects.create(serial_number=702, name="A", role="BAT")

    AuctionEngine.pick_random_player()

    with pytest.raises(Exception):
        AuctionEngine.sell_current_player(team.id, 100)


@pytest.mark.django_db
def test_invalid_stage_name():
    AuctionEngine.start_auction()

    with pytest.raises(Exception):
        AuctionEngine.change_stage("INVALID")


@pytest.mark.django_db
def test_undo_without_sale():
    AuctionEngine.start_auction()

    with pytest.raises(Exception):
        AuctionEngine.undo_last_action()


@pytest.mark.django_db
def test_disable_rebid_allows_auto_stage():
    AuctionEngine.start_auction()

    team1 = Team.objects.create(name="T1")
    team2 = Team.objects.create(name="T2")

    Player.objects.create(serial_number=703, name="P1", role="BAT")
    Player.objects.create(serial_number=704, name="P2", role="BAT")

    AuctionEngine.enable_rebid()
    AuctionEngine.disable_rebid()

    AuctionEngine.pick_random_player()
    AuctionEngine.sell_current_player(team1.id, 1000)

    AuctionEngine.pick_random_player()
    AuctionEngine.sell_current_player(team2.id, 1000)

    control = AuctionEngine.get_control()
    assert control.current_stage == "BOWL"