ROLE_DISPLAY = {
    "BAT":  "Batsman",
    "BOWL": "Bowler",
    "AR":   "All Rounder",
    "PLY":  "Player",
}


def role_display(role):
    """Return human-readable role name."""
    return ROLE_DISPLAY.get(role, role)


def player_label(player):
    """Return display label for a player."""
    return f"{player.name} ({role_display(player.role)})"
