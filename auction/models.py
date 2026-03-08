from django.db import models


# =========================
# TEAM
# =========================

class Team(models.Model):

    team_serial_number = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    owners = models.CharField(max_length=200, blank=True)
    payment_info = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    remaining_points = models.IntegerField(default=0)

    def __str__(self):
        return self.name


# =========================
# PLAYER
# =========================

class Player(models.Model):

    ROLE_CHOICES = [
        ("BAT", "BAT"),
        ("BOWL", "BOWL"),
        ("AR", "AR"),
        ("PLY", "PLY"),
    ]

    serial_number = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    place = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=12, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    base_price = models.IntegerField(default=0)
    sold_price = models.IntegerField(null=True, blank=True)

    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    status = models.CharField(max_length=20, default="AVAILABLE")
    notes = models.TextField(blank=True)

    photo = models.ImageField(
        upload_to="players/",
        null=True,
        blank=True
    )

    def __str__(self):
        return self.name


# =========================
# TOURNAMENT CONFIG
# =========================

class TournamentConfig(models.Model):

    total_points = models.IntegerField()
    bidding_slots = models.IntegerField()
    max_squad_size = models.IntegerField()

    base_price_AR = models.IntegerField()
    base_price_BAT = models.IntegerField()
    base_price_BOWL = models.IntegerField()
    base_price_PLY = models.IntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "Tournament Config"


# =========================
# AUCTION ACTION
# =========================

class AuctionAction(models.Model):

    ACTION_CHOICES = [
        ("SELL", "SELL"),
        ("UNSOLD", "UNSOLD"),
        ("NOT_PLAYING", "NOT_PLAYING"),
        ("UNDO", "UNDO"),
    ]

    player = models.ForeignKey(Player, on_delete=models.CASCADE)

    team = models.ForeignKey(
        Team,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    action = models.CharField(max_length=20, choices=ACTION_CHOICES)

    amount = models.IntegerField(null=True, blank=True)

    round = models.IntegerField(default=1)

    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.player.name} - {self.action}"


# =========================
# JERSEY
# =========================

class Jersey(models.Model):

    player = models.ForeignKey(Player, on_delete=models.CASCADE)

    jersey_name = models.CharField(max_length=100)

    jersey_number = models.IntegerField()

    size_number = models.IntegerField()

    size_text = models.CharField(max_length=10)

    sponsor = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.player.name} #{self.jersey_number}"