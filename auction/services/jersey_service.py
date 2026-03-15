from io import BytesIO

from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable
)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER

from auction.models import Jersey, ExtraJerseyMember, Team, Player, TournamentSettings


class JerseyService:

    # ----------------------------------------
    # EXPORT JERSEY LIST PDF — team-wise
    # ----------------------------------------

    def export_pdf(self):
        ts     = TournamentSettings.get()
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=15*mm, rightMargin=15*mm,
            topMargin=15*mm,  bottomMargin=15*mm,
        )

        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            "TitleStyle",
            parent=styles["Title"],
            fontSize=16,
            spaceAfter=4,
            textColor=colors.HexColor("#1a1a2e"),
            alignment=TA_CENTER,
        )
        team_style = ParagraphStyle(
            "TeamStyle",
            parent=styles["Heading2"],
            fontSize=12,
            spaceBefore=10,
            spaceAfter=4,
            textColor=colors.HexColor("#1a1a2e"),
            backColor=colors.HexColor("#f0f0f0"),
            leftIndent=4,
        )
        org_style = ParagraphStyle(
            "OrgStyle",
            parent=styles["Heading2"],
            fontSize=12,
            spaceBefore=10,
            spaceAfter=4,
            textColor=colors.HexColor("#2c3e50"),
            backColor=colors.HexColor("#e8f4f8"),
            leftIndent=4,
        )

        elements = []

        # ── Title ──────────────────────────────
        elements.append(Paragraph(ts.tournament_name, title_style))
        elements.append(Paragraph("Jersey List", ParagraphStyle(
            "Sub", parent=styles["Normal"],
            fontSize=10, textColor=colors.grey, alignment=TA_CENTER, spaceAfter=8,
        )))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
        elements.append(Spacer(1, 6*mm))

        # ── Column header style ─────────────────
        hdr_col = colors.HexColor("#2c3e50")
        hdr_bg  = colors.HexColor("#ecf0f1")
        col_widths = [8*mm, 42*mm, 32*mm, 14*mm, 14*mm, 12*mm, 28*mm]

        def make_table(rows, show_header=True):
            header = [["#", "Player", "Jersey Name", "Jsy #", "Size #", "Size", "Sponsor"]]
            data   = header + rows if show_header else rows
            t = Table(data, colWidths=col_widths, repeatRows=1 if show_header else 0)
            style = [
                # Header
                ("BACKGROUND",  (0, 0), (-1, 0), hdr_bg),
                ("TEXTCOLOR",   (0, 0), (-1, 0), hdr_col),
                ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE",    (0, 0), (-1, 0), 8),
                ("ALIGN",       (0, 0), (-1, 0), "CENTER"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                ("TOPPADDING",    (0, 0), (-1, 0), 5),
                # Body
                ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE",    (0, 1), (-1, -1), 8),
                ("ALIGN",       (0, 1), (0, -1), "CENTER"),   # # col
                ("ALIGN",       (3, 1), (5, -1), "CENTER"),   # numeric cols
                ("TOPPADDING",  (0, 1), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
                # Grid
                ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
                ("LINEBELOW",   (0, 0), (-1, 0),  1.0, hdr_col),
                # Alternating rows
            ]
            # Alternating row shading
            for i in range(1, len(data)):
                if i % 2 == 0:
                    style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f9f9f9")))
            t.setStyle(TableStyle(style))
            return t

        # ── Per-team sections ────────────────────
        teams = Team.objects.all().order_by("name")
        jersey_map = {j.player_id: j for j in Jersey.objects.select_related("player").all()}
        extras_by_team = {}
        for em in ExtraJerseyMember.objects.filter(
                member_type=ExtraJerseyMember.TYPE_TEAM).select_related("team"):
            extras_by_team.setdefault(em.team_id, []).append(em)

        grand_total = 0

        for team in teams:
            players = list(Player.objects.filter(
                team=team, status=Player.STATUS_SOLD
            ).order_by("role", "name"))
            extras  = extras_by_team.get(team.team_serial_number, [])

            if not players and not extras:
                continue

            elements.append(Paragraph(f"  {team.name}", team_style))
            if team.owners:
                elements.append(Paragraph(
                    f"<i>Owner: {team.owners}</i>",
                    ParagraphStyle("OwnerStyle", parent=styles["Normal"],
                                   fontSize=8, textColor=colors.grey, spaceAfter=3)
                ))

            rows = []
            serial = 1
            for p in players:
                j = jersey_map.get(p.serial_number)
                rows.append([
                    str(serial),
                    p.name,
                    j.jersey_name   if j and j.jersey_name   else "—",
                    str(j.jersey_number) if j and j.jersey_number else "—",
                    str(j.size_number)   if j and j.size_number   else "—",
                    j.size_text          if j and j.size_text      else "—",
                    j.sponsor            if j and j.sponsor        else "—",
                ])
                serial += 1
                grand_total += 1

            for em in extras:
                rows.append([
                    str(serial),
                    f"{em.name} ({em.role_label})" if em.role_label else em.name,
                    em.jersey_name          if em.jersey_name   else "—",
                    str(em.jersey_number)   if em.jersey_number else "—",
                    "—", "—",
                    "—",
                ])
                serial += 1
                grand_total += 1

            elements.append(make_table(rows))
            elements.append(Spacer(1, 4*mm))

        # ── Organiser sections ───────────────────
        org_groups = {}
        for em in ExtraJerseyMember.objects.filter(
                member_type=ExtraJerseyMember.TYPE_ORGANISER).order_by("group_name", "name"):
            org_groups.setdefault(em.group_name, []).append(em)

        for group_name, members in org_groups.items():
            elements.append(Paragraph(f"  {group_name}", org_style))
            rows = []
            for i, em in enumerate(members, 1):
                rows.append([
                    str(i),
                    f"{em.name} ({em.role_label})" if em.role_label else em.name,
                    em.jersey_name          if em.jersey_name   else "—",
                    str(em.jersey_number)   if em.jersey_number else "—",
                    "—", "—", "—",
                ])
                grand_total += 1
            elements.append(make_table(rows))
            elements.append(Spacer(1, 4*mm))

        # ── Footer ──────────────────────────────
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
        elements.append(Spacer(1, 2*mm))
        elements.append(Paragraph(
            f"Total jerseys: <b>{grand_total}</b>",
            ParagraphStyle("Footer", parent=styles["Normal"],
                           fontSize=9, textColor=colors.grey, alignment=TA_CENTER)
        ))

        doc.build(elements)
        buffer.seek(0)
        return buffer
