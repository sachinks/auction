from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser, AllowAny

from cricket.services.auction_engine import AuctionEngine
from cricket.exceptions import AuctionBaseException
from cricket.models import Team
from .serializers import (
    TeamSerializer,
    PlayerSerializer,
    AuctionStatusSerializer,
)


class BaseAuctionView(APIView):
    permission_classes = [IsAdminUser]

    def handle_exception(self, exc):
        if isinstance(exc, AuctionBaseException):
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().handle_exception(exc)


class StartAuctionView(BaseAuctionView):
    def post(self, request):
        control = AuctionEngine.start_auction()
        return Response({"stage": control.current_stage})


class PickPlayerView(BaseAuctionView):
    def post(self, request):
        player = AuctionEngine.pick_random_player()
        return Response(PlayerSerializer(player).data)


class SellPlayerView(BaseAuctionView):
    def post(self, request):
        team_id = request.data.get("team_id")
        price = request.data.get("price")

        player = AuctionEngine.sell_current_player(
            team_id=int(team_id),
            price=int(price),
        )

        return Response(PlayerSerializer(player).data)


class MarkUnsoldView(BaseAuctionView):
    def post(self, request):
        player = AuctionEngine.mark_unsold()
        return Response(PlayerSerializer(player).data)


class MarkNotPlayingView(BaseAuctionView):
    def post(self, request):
        player = AuctionEngine.mark_not_playing()
        return Response(PlayerSerializer(player).data)


class UndoView(BaseAuctionView):
    def post(self, request):
        player = AuctionEngine.undo_last_action()
        return Response(PlayerSerializer(player).data)


class EnableRebidView(BaseAuctionView):
    def post(self, request):
        AuctionEngine.enable_rebid()
        return Response({"rebid": True})


class DisableRebidView(BaseAuctionView):
    def post(self, request):
        AuctionEngine.disable_rebid()
        return Response({"rebid": False})


class AuctionStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        control = AuctionEngine.get_control()
        return Response(AuctionStatusSerializer(control).data)


class TeamListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        teams = Team.objects.all()
        return Response(TeamSerializer(teams, many=True).data)