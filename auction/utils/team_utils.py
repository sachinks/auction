# -------------------------------------------------
# TEAM SHORT NAME
# Takes first letter of each word, joined without spaces
# e.g. "Mumbai Indians" → "MI"
#      "Royal Challengers Bangalore" → "RCB"
#      "Chennai" → "CHE" (first 3 letters if single word)
# -------------------------------------------------

def short_name(team_name):

    words = team_name.strip().split()

    if not words:
        return "??"

    if len(words) == 1:
        # Single word — use first 3 letters
        return words[0][:3].upper()

    # Multiple words — initials joined
    return "".join(w[0].upper() for w in words)
