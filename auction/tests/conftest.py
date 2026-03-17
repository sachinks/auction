"""
Shared fixtures for all Sachin Kolige Premier League tests.
"""
import pytest
from auction.models import (
    Player, Team, TournamentConfig, AuctionState,
    TournamentPool, PoolTeam, Match,
)


@pytest.fixture
def config(db):
    return TournamentConfig.objects.create(
        total_points=10000,
        bidding_slots=11,
        base_price_AR=1000,
        base_price_BAT=400,
        base_price_BOWL=400,
        base_price_PLY=100,
        max_rebid_attempts=3,
    )


@pytest.fixture
def four_teams(db):
    teams = []
    for name in ["Alpha Kings", "Beta Bulls", "Gamma Giants", "Delta Destroyers"]:
        teams.append(Team.objects.create(name=name, remaining_points=10000))
    return teams


@pytest.fixture
def two_teams(db):
    return [
        Team.objects.create(name="Team A", remaining_points=10000),
        Team.objects.create(name="Team B", remaining_points=10000),
    ]


@pytest.fixture
def state(db):
    return AuctionState.get()


@pytest.fixture
def ar_player(db):
    return Player.objects.create(
        name="Jadeja", role="AR", base_price=1000, status=Player.STATUS_AVAILABLE
    )


@pytest.fixture
def bat_player(db):
    return Player.objects.create(
        name="Virat", role="BAT", base_price=400, status=Player.STATUS_AVAILABLE
    )


@pytest.fixture
def pool_a(db, four_teams):
    pool = TournamentPool.objects.create(
        stage=TournamentPool.STAGE_GROUP,
        name="A", order=0, advance_n=2,
        teams_per_pool=4, assignment_order="sequential",
    )
    for i, team in enumerate(four_teams):
        PoolTeam.objects.create(pool=pool, team=team, seed=i)
    return pool


@pytest.fixture
def pool_b(db, four_teams):
    pool = TournamentPool.objects.create(
        stage=TournamentPool.STAGE_GROUP,
        name="B", order=1, advance_n=2,
        teams_per_pool=4, assignment_order="sequential",
    )
    for i, team in enumerate(four_teams[2:] + four_teams[:2]):
        PoolTeam.objects.create(pool=pool, team=team, seed=i)
    return pool
