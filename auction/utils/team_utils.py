def short_name(team_name):
    """Return initials for a team name: 'Mumbai Indians' → 'MI'."""
    words = team_name.split()
    if not words:
        return "?"
    return "".join(w[0].upper() for w in words if w)
