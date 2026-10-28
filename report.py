import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

STORAGE_DIR = os.path.join(os.path.dirname(__file__), "storage")
os.makedirs(STORAGE_DIR, exist_ok=True)


def render_workshop_report_pdf(
    job_id: str,
    period_start: datetime,
    period_end: datetime,
    totals: dict,
    summary_rows: list,
) -> str:
    """
    Renders the queried + aggregated data into a PDF and writes it to disk.
    Returns the absolute file path of the generated PDF.

    Keeping rendering pure (data in -> file path out) makes it trivial to
    unit test without touching the DB or the job/queue machinery.
    """
    filename = f"report_{job_id}.pdf"
    filepath = os.path.join(STORAGE_DIR, filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    story = []

    # --- Header ---
    story.append(Paragraph("Workshop Activity Report", styles["Title"]))
    period_str = (
        f"{period_start.strftime('%b %d, %Y')} – {period_end.strftime('%b %d, %Y')}"
    )
    story.append(Paragraph(period_str, styles["Normal"]))
    story.append(Spacer(1, 0.25 * inch))

    # --- Headline totals ---
    story.append(Paragraph("Summary", styles["Heading2"]))
    totals_table_data = [
        ["Total Events", str(totals["total_events"])],
        ["Distinct Attendees", str(totals["distinct_attendees"])],
    ]
    totals_table = Table(totals_table_data, colWidths=[2.5 * inch, 2.5 * inch])
    totals_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(totals_table)
    story.append(Spacer(1, 0.3 * inch))

    # --- Detail table (the aggregated SQL rows) ---
    story.append(Paragraph("Breakdown by Workshop", styles["Heading2"]))
    if summary_rows:
        table_data = [["Workshop", "Event Type", "Count", "Avg Rating"]]
        for row in summary_rows:
            table_data.append(
                [
                    row["workshop_name"],
                    row["event_type"],
                    str(row["count"]),
                    str(row["avg_rating"]) if row["avg_rating"] is not None else "—",
                ]
            )
        detail_table = Table(table_data, colWidths=[2.2 * inch, 1.5 * inch, 1 * inch, 1.3 * inch])
        detail_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("PADDING", (0, 0), (-1, -1), 6),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.whitesmoke]),
                ]
            )
        )
        story.append(detail_table)
    else:
        story.append(Paragraph("No events found for this period.", styles["Normal"]))

    story.append(Spacer(1, 0.4 * inch))
    story.append(
        Paragraph(
            f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} · Job {job_id}",
            styles["Normal"],
        )
    )

    doc.build(story)
    return filepath