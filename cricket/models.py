from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from .image_utils import resize_image

# ----------------------------
# TEAM MODEL
# ----------------------------
class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)

    logo = models.ImageField(
        upload_to="team_logos/",
        blank=True,
        null=True
    )

    total_points = models.IntegerField(default=10000)
    remaining_points = models.IntegerField(default=10000)

    max_players = models.IntegerField(default=15)
    auction_slots = models.IntegerField(default=11)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.logo:
            resize_image(self.logo)


    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            models.Index(fields=["name"]),
        ]


# ----------------------------
# PLAYER MODEL
# ----------------------------
class Player(models.Model):

    ROLE_CHOICES = [
        ("BAT", "Batting Icon"),
        ("BOWL", "Bowling Icon"),
        ("AR", "All Rounder Icon"),
        ("PLY", "Player"),
    ]

    STATUS_CHOICES = [
        ("UNSOLD", "Unsold"),
        ("SOLD", "Sold"),
        ("NOT_PLAYING", "Not Playing"),
        ("FREE", "Free Addition"),
    ]

    serial_number = models.IntegerField(unique=True)

    name = models.CharField(max_length=200)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    base_price = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )

    sold_price = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )

    team = models.ForeignKey(
        Team,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="UNSOLD"
    )

    notes = models.TextField(blank=True, null=True)

    photo = models.ImageField(
        upload_to="player_photos/",
        blank=True,
        null=True
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.photo:
            resize_image(self.photo)

    def __str__(self):
        return f"{self.serial_number} - {self.name}"

    class Meta:
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["status"]),
            models.Index(fields=["serial_number"]),
        ]


# ----------------------------
# JERSEY PROFILE (Simple)
# ----------------------------
class JerseyProfile(models.Model):
    player = models.OneToOneField(
        Player,
        on_delete=models.CASCADE
    )

    name_on_jersey = models.CharField(max_length=200)

    jersey_number = models.IntegerField(
        null=True,
        blank=True
    )

    size_number = models.IntegerField(
        null=True,
        blank=True
    )

    size_text = models.CharField(
        max_length=10,
        blank=True,
        null=True
    )

    sponsor_name = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    def __str__(self):
        return f"Jersey - {self.player.name}"


# ----------------------------
# AUCTION CONTROL
# ----------------------------
class AuctionControl(models.Model):

    STAGE_CHOICES = [
        ("NOT_STARTED", "Not Started"),
        ("BAT", "Batting Icons"),
        ("BOWL", "Bowling Icons"),
        ("AR", "All Rounder Icons"),
        ("OPEN", "Open Auction"),
        ("COMPLETED", "Completed"),
    ]

    is_started = models.BooleanField(default=False)

    current_stage = models.CharField(
        max_length=20,
        choices=STAGE_CHOICES,
        default="NOT_STARTED"
    )

    current_player = models.ForeignKey(
        Player,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    is_rebid = models.BooleanField(default=False)
    is_parked = models.BooleanField(default=False)

    # Simple global size mapping for jerseys
    size_mapping = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return "Auction Control"


# ----------------------------
# AUCTION LOG
# ----------------------------
class AuctionLog(models.Model):

    ACTION_CHOICES = [
        ("SOLD", "Sold"),
        ("UNSOLD", "Unsold"),
        ("NOT_PLAYING", "Not Playing"),
        ("STAGE_CHANGE", "Stage Change"),
        ("UNDO", "Undo"),
        ("MANUAL_EDIT", "Manual Edit"),
    ]

    timestamp = models.DateTimeField(auto_now_add=True)

    action_type = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES
    )

    player = models.ForeignKey(
        Player,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    team = models.ForeignKey(
        Team,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    sold_price = models.IntegerField(null=True, blank=True)

    stage = models.CharField(max_length=20, null=True, blank=True)

    admin_user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.action_type} - {self.timestamp}"

    class Meta:
        ordering = ["-timestamp"]