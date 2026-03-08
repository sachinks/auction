# -------------------------------------------------
# TEAM SHORT NAME
# -------------------------------------------------

def short_name(team_name):

    words = team_name.split()

    letters = []

    for word in words:

        letters.append(word[0].upper())

    short = " ".join(letters)

    return short