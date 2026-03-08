from auction.models import TournamentConfig


# -------------------------------------------------
# BID INCREMENT
# -------------------------------------------------

def bid_increment():

    config = TournamentConfig.objects.first()

    if not config:
        return 100

    return int(config.total_points / 100)


# -------------------------------------------------
# WALLET COLOR
# -------------------------------------------------

def wallet_color(team):

    config = TournamentConfig.objects.first()

    if not config:
        return "green"

    if team.remaining_points <= 0:
        return "red"

    if team.remaining_points < config.total_points * 0.1:
        return "orange"

    return "green"