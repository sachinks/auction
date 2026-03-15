from io import BytesIO

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

from django.conf import settings

from auction.models import Jersey


class JerseyService:


    SIZE_MAP = {
        36: "S",
        38: "M",
        40: "L",
        42: "XL",
        44: "XXL"
    }


    # ----------------------------------------
    # CONVERT SIZE NUMBER TO TEXT
    # ----------------------------------------

    def convert_size(self, size_number):

        return self.SIZE_MAP.get(size_number, "UNKNOWN")


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
            sponsor=sponsor
        )


    # ----------------------------------------
    # EXPORT JERSEY LIST PDF
    # ----------------------------------------

    def export_pdf(self):

        jerseys = Jersey.objects.select_related("player").all()

        buffer = BytesIO()

        doc = SimpleDocTemplate(buffer, pagesize=A4)

        data = [
            ["Player", "Jersey Name", "Number", "Size", "Sponsor"]
        ]

        for j in jerseys:

            data.append([
                j.player.name,
                j.jersey_name,
                j.jersey_number,
                j.size_text,
                j.sponsor
            ])

        table = Table(data)

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]))

        elements = [table]

        doc.build(elements)

        buffer.seek(0)

        return buffer