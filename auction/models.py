from django.db import models


# =========================
# TEAM
# =========================

class Team(models.Model):

    team_serial_number = models.AutoField(primary_key=True)
    name               = models.CharField(max_length=100)
    short_name         = models.CharField(max_length=20, blank=True, help_text="Abbreviation shown on auction buttons e.g. MI, RCB")
    owners             = models.CharField(max_length=200, blank=True)
    payment_info       = models.IntegerField(default=0)
    notes              = models.TextField(blank=True)
    remaining_points   = models.IntegerField(default=0)

    def get_short(self):
        """Return short_name if set, else auto-generate from name."""
        if self.short_name:
            return self.short_name.upper()
        words = self.name.strip().split()
        if not words:
            return "??"
        if len(words) == 1:
            return words[0][:3].upper()
        return "".join(w[0].upper() for w in words)

    def __str__(self):
        return self.name


# =========================
# PLAYER
# =========================

class Player(models.Model):

    ROLE_CHOICES = [
        ("BAT",  "BAT"),
        ("BOWL", "BOWL"),
        ("AR",   "AR"),
        ("PLY",  "PLY"),
    ]

    STATUS_AVAILABLE   = "AVAILABLE"
    STATUS_SOLD        = "SOLD"
    STATUS_UNSOLD      = "UNSOLD"
    STATUS_NOT_PLAYING = "NOT_PLAYING"

    STATUS_CHOICES = [
        (STATUS_AVAILABLE,   "Available"),
        (STATUS_SOLD,        "Sold"),
        (STATUS_UNSOLD,      "Unsold"),
        (STATUS_NOT_PLAYING, "Not Playing"),
    ]

    serial_number = models.AutoField(primary_key=True)
    name          = models.CharField(max_length=100)
    place         = models.CharField(max_length=100, blank=True)
    phone         = models.CharField(max_length=12, blank=True)
    role          = models.CharField(max_length=10, choices=ROLE_CHOICES)
    base_price    = models.IntegerField(default=0)
    sold_price    = models.IntegerField(null=True, blank=True)

    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    status      = models.CharField(max_length=20, default=STATUS_AVAILABLE, choices=STATUS_CHOICES)
    rebid_count = models.IntegerField(default=0)
    notes       = models.TextField(blank=True)
    photo       = models.ImageField(upload_to="players/", null=True, blank=True)

    def save(self, *args, **kwargs):
        """Auto-adjust team remaining_points whenever sold status/price/team changes."""
        if self.pk:
            try:
                prev        = Player.objects.get(pk=self.pk)
                prev_status = prev.status
                prev_team   = prev.team
                prev_price  = prev.sold_price or 0
            except Player.DoesNotExist:
                prev_status = None
                prev_team   = None
                prev_price  = 0
        else:
            prev_status = None
            prev_team   = None
            prev_price  = 0

        super().save(*args, **kwargs)

        new_status = self.status
        new_team   = self.team
        new_price  = self.sold_price or 0

        already_same = (
            prev_status == self.STATUS_SOLD
            and prev_team  == new_team
            and prev_price == new_price
            and new_status == self.STATUS_SOLD
        )

        if already_same:
            return  # Nothing changed financially

        # Always refund previous team if was SOLD
        if prev_status == self.STATUS_SOLD and prev_team and prev_price:
            prev_team.remaining_points += prev_price
            prev_team.save()

        # Deduct from new team if now SOLD
        if new_status == self.STATUS_SOLD and new_team and new_price:
            # If prev_team and new_team are the same DB row, refresh so we
            # don't overwrite the refund just applied above.
            if prev_team and prev_team.pk == new_team.pk:
                new_team.refresh_from_db()
            new_team.remaining_points -= new_price
            new_team.save()

    def __str__(self):
        return self.name


# =========================
# TOURNAMENT SETTINGS (singleton — exists before auction starts)
# =========================

class TournamentSettings(models.Model):
    """
    Singleton (pk=1). Stores display info configurable before auction starts:
    tournament name, banner, auction date, match date.
    Independent of TournamentConfig which is only created on auction start.
    """
    tournament_name = models.CharField(
        max_length=100, default="Sachin Kolige Premier League",
        help_text="Shown on public board and all pages"
    )
    auction_date = models.DateTimeField(null=True, blank=True)
    match_date   = models.DateTimeField(null=True, blank=True)
    banner_path  = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Tournament Settings"

    def __str__(self):
        return self.tournament_name

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={"tournament_name": "Sachin Kolige Premier League"})
        return obj


# =========================
# TOURNAMENT CONFIG
# =========================

class TournamentConfig(models.Model):

    total_points    = models.IntegerField(default=10000)
    bidding_slots   = models.IntegerField(default=11)
    max_squad_size  = models.IntegerField(default=13)

    base_price_AR   = models.IntegerField(default=1000)
    base_price_BAT  = models.IntegerField(default=400)
    base_price_BOWL = models.IntegerField(default=400)
    base_price_PLY  = models.IntegerField(default=100)

    category_order     = models.CharField(max_length=50, default="AR,BAT,BOWL,PLY")
    max_rebid_attempts = models.IntegerField(default=3)

    size_mapping = models.TextField(
        default='{"36":"XS","38":"S","40":"M","42":"L","44":"XL","46":"XXL"}',
        help_text="JSON mapping of size number to size label e.g. {\"38\":\"M\"}"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def get_category_order(self):
        """Parse category_order — handles both 'AR,BAT,BOWL,PLY' and '["AR","BAT"]' formats."""
        import json
        val = (self.category_order or "AR,BAT,BOWL,PLY").strip()
        # Try JSON array format first
        if val.startswith("["):
            try:
                return [c.strip().upper() for c in json.loads(val) if c.strip()]
            except (json.JSONDecodeError, TypeError):
                pass
        # Fall back to comma-separated
        return [c.strip().strip('"').upper() for c in val.split(",") if c.strip().strip('"')]

    def base_price_for_role(self, role):
        return {"AR": self.base_price_AR, "BAT": self.base_price_BAT,
                "BOWL": self.base_price_BOWL, "PLY": self.base_price_PLY}.get(role, 0)

    def __str__(self):
        return "Tournament Config"


# =========================
# AUCTION ACTION
# =========================

class AuctionAction(models.Model):

    ACTION_CHOICES = [
        ("SELL",        "SELL"),
        ("UNSOLD",      "UNSOLD"),
        ("NOT_PLAYING", "NOT_PLAYING"),
        ("UNDO",        "UNDO"),
    ]

    player    = models.ForeignKey(Player, on_delete=models.CASCADE)
    team      = models.ForeignKey(Team, null=True, blank=True, on_delete=models.SET_NULL)
    action    = models.CharField(max_length=20, choices=ACTION_CHOICES)
    amount    = models.IntegerField(null=True, blank=True)
    round     = models.IntegerField(default=1)
    category  = models.CharField(max_length=10, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.player.name} - {self.action}"


# =========================
# AUCTION STATE
# =========================

class AuctionState(models.Model):

    PHASE_MAIN   = "MAIN"
    PHASE_REBID  = "REBID"
    PHASE_FREBID = "FREBID"   # Final global rebid — all unsold across all roles
    PHASE_DONE   = "DONE"

    PHASE_CHOICES = [
        (PHASE_MAIN,   "Main Round"),
        (PHASE_REBID,  "Rebid Round"),
        (PHASE_FREBID, "Final Rebid"),
        (PHASE_DONE,   "Auction Complete"),
    ]

    current_player   = models.ForeignKey(
        Player, null=True, blank=True, on_delete=models.SET_NULL, related_name="active_in_state"
    )
    phase            = models.CharField(max_length=10, default=PHASE_MAIN, choices=PHASE_CHOICES)
    current_category = models.CharField(max_length=10, default="AR")
    category_pass    = models.IntegerField(default=1)
    auction_round    = models.IntegerField(default=1)
    is_active        = models.BooleanField(default=False)
    updated_at       = models.DateTimeField(auto_now=True)

    # Transition pause mechanism (item 4, 10)
    awaiting_transition = models.BooleanField(default=False)
    transition_message  = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Auction State"

    def __str__(self):
        return f"{self.phase} | {self.current_category} Pass{self.category_pass}"

    @classmethod
    def get(cls):
        state, _ = cls.objects.get_or_create(pk=1)
        return state


# =========================
# JERSEY
# =========================

class Jersey(models.Model):

    player        = models.ForeignKey(Player, on_delete=models.CASCADE)
    jersey_name   = models.CharField(max_length=100)
    jersey_number = models.IntegerField(null=True, blank=True)
    size_number   = models.IntegerField(null=True, blank=True)
    size_text     = models.CharField(max_length=10, blank=True)
    sponsor       = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.player.name} #{self.jersey_number}"


# =========================
# EXTRA JERSEY MEMBER
# =========================

class ExtraJerseyMember(models.Model):
    """
    Non-player jersey entries:
    - Team extras: manager, coach, supporter etc. (team FK set)
    - Organisers: volunteers, officials etc. (team FK null, group_name set)
    """

    TYPE_TEAM     = "TEAM"
    TYPE_ORGANISER = "ORGANISER"

    TYPE_CHOICES = [
        (TYPE_TEAM,      "Team Extra"),
        (TYPE_ORGANISER, "Organiser"),
    ]

    name          = models.CharField(max_length=100)
    role_label    = models.CharField(max_length=50, blank=True, help_text="e.g. Manager, Coach, Volunteer")
    jersey_name   = models.CharField(max_length=100, blank=True)
    jersey_number = models.IntegerField(null=True, blank=True)
    size_number   = models.IntegerField(null=True, blank=True)
    size_text     = models.CharField(max_length=10, blank=True)
    sponsor       = models.CharField(max_length=100, blank=True)

    member_type   = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_TEAM)

    # For team extras — which team
    team          = models.ForeignKey(
        Team, null=True, blank=True, on_delete=models.SET_NULL, related_name="extra_members"
    )

    # For organisers — group label (e.g. "Sachin Kolige Premier League Organising Committee")
    group_name    = models.CharField(max_length=100, blank=True, default="Organisers")

    def __str__(self):
        if self.team:
            return f"{self.name} ({self.team.name})"
        return f"{self.name} ({self.group_name})"


# =========================
# MATCH / FIXTURE
# =========================

class Match(models.Model):

    STATUS_SCHEDULED = "SCHEDULED"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    match_number   = models.IntegerField()
    round_label    = models.CharField(max_length=50, default="League",
                                      help_text="e.g. League, Quarter-Final, Semi-Final, Final")

    team1          = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="home_matches")
    team2          = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="away_matches")

    scheduled_date = models.DateTimeField(null=True, blank=True)
    venue          = models.CharField(max_length=100, blank=True)

    winner         = models.ForeignKey(Team, null=True, blank=True,
                                       on_delete=models.SET_NULL, related_name="won_matches")
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                      default=STATUS_SCHEDULED)
    notes          = models.TextField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    # Pool / stage link (nullable for legacy matches)
    pool = models.ForeignKey(
        "TournamentPool",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="matches"
    )

    class Meta:
        ordering = ["match_number"]

    def __str__(self):
        return f"M{self.match_number}: {self.team1.name} vs {self.team2.name}"

    def loser(self):
        if self.winner == self.team1:
            return self.team2
        if self.winner == self.team2:
            return self.team1
        return None


# =========================
# TOURNAMENT STAGE / POOL
# =========================

class TournamentPool(models.Model):
    """
    A pool/group in a tournament stage.
    e.g. Group Stage Pool A, Super 8 Group 1, etc.
    """
    STAGE_GROUP   = "GROUP"
    STAGE_SUPER8  = "SUPER8"
    STAGE_QF      = "QF"
    STAGE_SF      = "SF"
    STAGE_FINAL   = "FINAL"
    STAGE_CUSTOM  = "CUSTOM"

    STAGE_CHOICES = [
        (STAGE_GROUP,  "Group Stage"),
        (STAGE_SUPER8, "Super 8"),
        (STAGE_QF,     "Quarter Final"),
        (STAGE_SF,     "Semi Final"),
        (STAGE_FINAL,  "Final"),
        (STAGE_CUSTOM, "Custom"),
    ]

    stage      = models.CharField(max_length=20, choices=STAGE_CHOICES, default=STAGE_GROUP)
    name       = models.CharField(max_length=20, help_text="e.g. A, B, Group 1")
    order      = models.IntegerField(default=0)
    teams      = models.ManyToManyField(Team, through="PoolTeam", blank=True, related_name="pools")
    # How many teams advance from this pool
    advance_n       = models.IntegerField(default=2)
    teams_per_pool    = models.IntegerField(default=4, help_text="Max teams in this pool")
    assignment_order  = models.CharField(max_length=20, default="sequential", help_text="sequential or roundrobin")
    is_locked       = models.BooleanField(default=False, help_text="Lock advancement — no more changes")
    fixtures_locked = models.BooleanField(default=False, help_text="Fixtures drawn for this pool")

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.get_stage_display()} — Pool {self.name}"


class PoolTeam(models.Model):
    """Membership of a team in a pool, with their position/advancement status."""
    pool     = models.ForeignKey(TournamentPool, on_delete=models.CASCADE)
    team     = models.ForeignKey(Team, on_delete=models.CASCADE)
    seed     = models.IntegerField(default=0, help_text="Seeding order within pool")
    advanced = models.BooleanField(default=False, help_text="Did this team advance?")
    position = models.IntegerField(null=True, blank=True, help_text="Final position in this pool (1st, 2nd...)")

    class Meta:
        unique_together = [("pool", "team")]
        ordering        = ["seed"]

    def __str__(self):
        return f"{self.team.name} in Pool {self.pool.name}"


# Extend Match with pool + stage link
# (done via a proxy — we add pool FK directly to Match migration)
