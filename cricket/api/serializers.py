from rest_framework import serializers
from cricket.models import Team, Player, AuctionControl


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = [
            "id",
            "name",
            "remaining_points",
            "auction_slots",
        ]


class PlayerSerializer(serializers.ModelSerializer):
    team = serializers.StringRelatedField()

    class Meta:
        model = Player
        fields = [
            "id",
            "serial_number",
            "name",
            "role",
            "status",
            "sold_price",
            "team",
        ]


class AuctionStatusSerializer(serializers.ModelSerializer):
    current_player = PlayerSerializer()

    class Meta:
        model = AuctionControl
        fields = [
            "is_started",
            "current_stage",
            "is_rebid",
            "current_player",
        ]