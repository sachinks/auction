# -------------------------------------------------
# ROLE DISPLAY
# -------------------------------------------------

def role_display(role):

    roles = {
        "BAT": "Batsman",
        "BOWL": "Bowler",
        "AR": "All Rounder",
        "PLY": "Player"
    }

    return roles.get(role, role)


# -------------------------------------------------
# PLAYER LABEL
# -------------------------------------------------

def player_label(player):

    return f"{player.name} ({player.role})"