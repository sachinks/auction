"""
jersey_service.py
─────────────────
Jersey size conversion and PDF export.

Size mapping is read dynamically from TournamentConfig.size_mapping (JSON).
Falls back to a safe default map if config is absent.
"""
import json
import logging
from io import BytesIO

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

from auction.models import Jersey

logger = logging.getLogger("system")

# Fallback map — mirrors the TournamentConfig default JSON
_DEFAULT_SIZE_MAP = {
    "36": "XS",
    "38": "S",
    "40": "M",
    "42": "L",
    "44": "XL",
    "46": "XXL",
}


def _load_size_map():
    """
    Load size mapping from TournamentConfig.size_mapping.
    Keys are stored as strings in JSON, so we normalise to int → str.
    Falls back to _DEFAULT_SIZE_MAP if config is absent or invalid.
    """
    try:
        from auction.models import TournamentConfig
        config = TournamentConfig.objects.first()
        if config and config.size_mapping:
            raw = json.loads(config.size_mapping)
            # Normalise: keys may be "38" or 38, values are size labels
            return {str(k): str(v) for k, v in raw.items()}
    except Exception as e:
        logger.warning(f"_load_size_map: could not read config size_mapping — {e}")
    return dict(_DEFAULT_SIZE_MAP)


class JerseyService:

    # ----------------------------------------
    # CONVERT SIZE NUMBER TO TEXT
    # Reads from TournamentConfig each call so admin changes take effect immediately.
    # ----------------------------------------

    def convert_size(self, size_number):
        size_map = _load_size_map()
        return size_map.get(str(size_number), "UNKNOWN")

    # ----------------------------------------
    # CREATE JERSEY RECORD
    # ----------------------------------------

    def create_jersey(self, player, jersey_name, jersey_number, size_number, sponsor):
        size_text = self.convert_size(size_number)
        Jersey.objects.create(
            player=player,
            jersey_name=jersey_name,
            jersey_number=jersey_number,
            size_number=size_number,
            size_text=size_text,
            sponsor=sponsor,
        )

    # ----------------------------------------
    # EXPORT JERSEY LIST PDF
    # ----------------------------------------

    def export_pdf(self):
        jerseys = Jersey.objects.select_related("player").all()

        buffer = BytesIO()
        doc    = SimpleDocTemplate(buffer, pagesize=A4)

        data = [["Player", "Jersey Name", "Number", "Size", "Sponsor"]]
        for j in jerseys:
            data.append([
                j.player.name,
                j.jersey_name,
                str(j.jersey_number),
                j.size_text,
                j.sponsor or "",
            ])

        table = Table(data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID",       (0, 0), (-1, -1), 0.5, colors.black),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ]))

        doc.build([table])
        buffer.seek(0)
        return buffer
