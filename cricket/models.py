from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator

class Team(models.Model):
    name = models.CharField(max_length=100)
    total_points = models.IntegerField(default=10000)
    remaining_points = models.IntegerField(default=10000)
    players_needed = models.IntegerField(default=11)

    def __str__(self):
        return self.name


class Player(models.Model):
    ROLE_CHOICES = [
        ('BAT', 'BAT'),
        ('BOWL', 'BOWL'),
        ('AR', 'AR'),
        ('PLY', 'PLY'),
    ]

    mobile_validator = RegexValidator(
        regex=r'^\d{10}$',
        message="Mobile number must be exactly 10 digits."
    )

    name = models.CharField(max_length=100)
    place = models.CharField(max_length=100)
    mobile_number = models.CharField(
        max_length=10,
        validators=[mobile_validator]
    )

    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    base_price = models.IntegerField(validators=[MinValueValidator(0)])
    sold_price = models.IntegerField(null=True,
                                     blank=True,
                                     validators=[MinValueValidator(0)]
                                     )
    team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.SET_NULL)

    def save(self, *args, **kwargs):

        self.full_clean()  # run clean()

        if self.pk:
            old_player = Player.objects.get(pk=self.pk)
        else:
            old_player = None

        # Refund old team if editing
        if old_player and old_player.team:
            old_team = old_player.team
            old_team.remaining_points += old_player.sold_price
            old_team.players_needed += 1
            old_team.save()

        # Deduct from new team
        if self.team and self.sold_price:
            new_team = self.team
            new_team.remaining_points -= self.sold_price
            new_team.players_needed -= 1
            new_team.save()

        super().save(*args, **kwargs)

    from django.core.exceptions import ValidationError

    def clean(self):

        # Prevent sold price less than base price
        if self.sold_price is not None and self.sold_price < self.base_price:
            raise ValidationError("Sold price cannot be less than base price.")

        # Only validate if selling
        if not self.team or not self.sold_price:
            return

        if self.pk:
            old_player = Player.objects.get(pk=self.pk)
        else:
            old_player = None

        team = self.team

        # If editing existing sold player
        if old_player and old_player.team:
            team_remaining = team.remaining_points + old_player.sold_price
            players_needed = team.players_needed + 1
        else:
            team_remaining = team.remaining_points
            players_needed = team.players_needed

        if team_remaining < self.sold_price:
            raise ValidationError("Not enough points remaining for this team.")

        if players_needed <= 0:
            raise ValidationError("Team already completed required players.")

    def __str__(self):
        return f"{self.name} - {self.role}"