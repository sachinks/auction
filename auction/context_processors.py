from .models import TournamentSettings
from django.conf import settings as django_settings


def tournament_settings(request):
    """
    Injects `ts` (TournamentSettings singleton) and `banner_url`
    into every template context automatically.
    """
    ts = TournamentSettings.get()

    banner_url = None
    if ts.banner_path:
        banner_url = django_settings.MEDIA_URL + "banners/" + ts.banner_path

    return {
        "ts":         ts,
        "banner_url": banner_url,
    }
