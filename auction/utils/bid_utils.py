from auction.models import TournamentConfig


def bid_increment():
    """Return the standard bid increment (1% of total points, min 100)."""
    config = TournamentConfig.objects.first()
    if not config:
        return 100
    return max(100, int(config.total_points / 100))
