"""Generate the final project PDF report."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
DEMAND_REPORT = ROOT / "data/processed/demand_evidence_public_report.json"
OPEN_DATA_SUMMARY = ROOT / "data/processed/taipei_rent_summary_by_district.csv"
OUTPUT_PDF = ROOT / "r14921059.pdf"

# Repository and demo links for the submission cover page.
GITHUB_URL = "https://github.com/FettHsiao/bdfinal"
GITHUB_CLONE_URL = "https://github.com/FettHsiao/bdfinal.git"
TAIPEI_OPEN_DATA_URL = (
    "https://data.taipei/api/frontstage/tpeod/dataset/resource.download"
    "?rid=2979c431-7a32-4067-9af2-e716cd825c4b"
)
VERCEL_API_URL = os.getenv("VERCEL_API_URL", "https://bdfinal.vercel.app").strip()
LIVE_DEMO_NOTE = (
    f"Live API: {VERCEL_API_URL} (Swagger docs at {VERCEL_API_URL}/docs). "
    "Local dashboard: run `make api` and `make dashboard`."
)

REPORT_FONT = "Helvetica"
REPORT_FONT_BOLD = "Helvetica-Bold"


def register_report_fonts() -> None:
    """Register Unicode regular/bold fonts for correct Chinese rendering."""
    global REPORT_FONT, REPORT_FONT_BOLD

    regular_candidates = [
        ROOT / "report/fonts/NotoSansTC-Regular.otf",
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
    ]
    bold_candidates = [
        ROOT / "report/fonts/NotoSansTC-Bold.otf",
        Path("/System/Library/Fonts/STHeiti Medium.ttc"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        Path("/Library/Fonts/Arial Bold.ttf"),
    ]

    regular_path: Path | None = None
    for path in regular_candidates:
        if not path.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont("ReportFont", str(path)))
            regular_path = path
            break
        except Exception:
            continue

    if regular_path is None:
        REPORT_FONT = "Helvetica"
        REPORT_FONT_BOLD = "Helvetica-Bold"
        return

    bold_registered = False
    for path in bold_candidates:
        if not path.exists():
            continue
        try:
            if path.suffix.lower() == ".ttc":
                pdfmetrics.registerFont(TTFont("ReportFont-Bold", str(path), subfontIndex=0))
            else:
                pdfmetrics.registerFont(TTFont("ReportFont-Bold", str(path)))
            bold_registered = True
            break
        except Exception:
            continue

    if not bold_registered:
        pdfmetrics.registerFont(TTFont("ReportFont-Bold", str(regular_path)))

    addMapping("ReportFont", 0, 0, "ReportFont")
    addMapping("ReportFont", 1, 0, "ReportFont-Bold")
    pdfmetrics.registerFontFamily("ReportFont", normal="ReportFont", bold="ReportFont-Bold")
    REPORT_FONT = "ReportFont"
    REPORT_FONT_BOLD = "ReportFont-Bold"


def esc(text) -> str:
    """Escape dynamic text for ReportLab Paragraph markup."""
    return escape(str(text))


def mono(text: str, size: int = 8) -> str:
    """Monospace inline text for ASCII commands, paths, and URLs."""
    return f"<font name='Courier' size='{size}'>{esc(text)}</font>"


def data_val(text, size: int = 9) -> str:
    """Emphasized inline value; safe for Chinese / mixed Unicode content."""
    return f"<font name='{REPORT_FONT_BOLD}' size='{size}'>{esc(text)}</font>"


def table_style(extra: list) -> TableStyle:
    base = [
        ("FONT", (0, 0), (-1, -1), REPORT_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]
    return TableStyle(base + extra)


def load_open_data_stats() -> dict:
    if not OPEN_DATA_SUMMARY.exists():
        raise FileNotFoundError(
            "Open-data summary not found. Run `make ingest` or `make run` first."
        )

    import pandas as pd

    summary = pd.read_csv(OPEN_DATA_SUMMARY)
    ingest_csv = ROOT / "data/processed/transactions_ingest.csv"
    row_count = len(pd.read_csv(ingest_csv)) if ingest_csv.exists() else int(summary["sample_size"].sum())
    top = summary.sort_values("median_rent_total_ntd", ascending=False).head(3)
    return {
        "rental_rows": row_count,
        "districts": int(summary["district"].nunique()),
        "top_districts": [
            (row["district"], int(row["median_rent_total_ntd"]))
            for _, row in top.iterrows()
        ],
    }


def load_demand_data() -> dict:
    if not DEMAND_REPORT.exists():
        raise FileNotFoundError(
            "Public demand evidence report not found. Run `make public-evidence` or `make run` first."
        )

    with DEMAND_REPORT.open(encoding="utf-8") as handle:
        return json.load(handle)


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TitleCenter",
            parent=styles["Title"],
            alignment=TA_CENTER,
            spaceAfter=18,
            fontName=REPORT_FONT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SubCenter",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontSize=11,
            textColor=colors.HexColor("#333333"),
            spaceAfter=8,
            fontName=REPORT_FONT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Heading1"],
            fontSize=15,
            spaceBefore=10,
            spaceAfter=6,
            textColor=colors.HexColor("#1f4e79"),
            fontName=REPORT_FONT_BOLD,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SubSection",
            parent=styles["Heading2"],
            fontSize=12,
            spaceBefore=8,
            spaceAfter=5,
            textColor=colors.HexColor("#1f4e79"),
            fontName=REPORT_FONT_BOLD,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            alignment=TA_JUSTIFY,
            leading=15,
            spaceAfter=8,
            fontName=REPORT_FONT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyLeft",
            parent=styles["BodyText"],
            alignment=TA_LEFT,
            leading=15,
            spaceAfter=8,
            fontName=REPORT_FONT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableCell",
            parent=styles["Normal"],
            fontName=REPORT_FONT,
            fontSize=8,
            leading=10,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="LPBullet",
            parent=styles["BodyText"],
            leftIndent=16,
            bulletIndent=6,
            leading=14,
            spaceAfter=5,
            fontName=REPORT_FONT,
        )
    )
    return styles


def subsection(title: str, styles) -> Paragraph:
    return Paragraph(esc(title), styles["SubSection"])


def table_cell(text: str, styles) -> Paragraph:
    return Paragraph(esc(text), styles["TableCell"])


def architecture_table() -> Table:
    diagram = Table(
        [
            ["Data Sources", "→", "Taipei open data", "→", "PostgreSQL", "→", "Pandas + HW2 K-Means"],
            ["", "", "", "", "↓", "", ""],
            ["", "", "FastAPI", "←", "Aggregates", "→", "Streamlit Dashboard"],
        ],
        colWidths=[3.2 * cm, 0.6 * cm, 3.2 * cm, 0.6 * cm, 3.2 * cm, 0.6 * cm, 3.8 * cm],
    )
    diagram.setStyle(
        table_style(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#1f4e79")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#eef4fb")),
                ("BACKGROUND", (2, 0), (2, 0), colors.HexColor("#eef4fb")),
                ("BACKGROUND", (4, 0), (4, 0), colors.HexColor("#eef4fb")),
                ("BACKGROUND", (6, 0), (6, 0), colors.HexColor("#eef4fb")),
                ("BACKGROUND", (2, 2), (2, 2), colors.HexColor("#eef4fb")),
                ("BACKGROUND", (4, 2), (4, 2), colors.HexColor("#eef4fb")),
                ("BACKGROUND", (6, 2), (6, 2), colors.HexColor("#eef4fb")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    return diagram


def build_report(output_path: Path) -> None:
    register_report_fonts()
    styles = build_styles()
    demand = load_demand_data()
    open_data = load_open_data_stats()
    forum = demand["forum_summary"]
    trends = demand.get("search_trends_summary", {})
    app_reviews = demand.get("app_review_summary", {})
    competitors = demand.get("competitor_pricing_summary", {})

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    story = []

    story.append(Paragraph("LeasePulse Taipei", styles["TitleCenter"]))
    story.append(
        Paragraph(
            "A Data Monetization System for Greater Taipei Rental Pricing Intelligence",
            styles["SubCenter"],
        )
    )
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(f"<b>Student ID:</b> r14921059", styles["SubCenter"]))
    story.append(Paragraph("Big Data Systems — Final Project — Spring 2026", styles["SubCenter"]))
    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph(f"<b>GitHub Repository:</b> {GITHUB_URL}", styles["SubCenter"]))
    story.append(Paragraph(f"<b>Clone URL:</b> {GITHUB_CLONE_URL}", styles["SubCenter"]))
    story.append(Paragraph(f"<b>Live Demo:</b> {LIVE_DEMO_NOTE}", styles["SubCenter"]))
    story.append(Spacer(1, 0.8 * cm))
    story.append(
        Paragraph(
            f"Report generated on {datetime.utcnow().strftime('%Y-%m-%d')} UTC",
            styles["SubCenter"],
        )
    )
    story.append(PageBreak())

    story.append(Paragraph("1. Executive Summary", styles["Section"]))
    story.append(
        Paragraph(
            "LeasePulse Taipei is a B2B data product that transforms Taipei City open-data rental "
            "transactions into actionable pricing bands for a narrowly defined customer segment: "
            "independent landlords managing 2–15 units in Greater Taipei. The system downloads the "
            f"official weekly real-price CSV ({open_data['rental_rows']} rental rows across "
            f"{open_data['districts']} districts in our latest pull), computes district-level rent "
            "statistics in batch, and delivers recommendations through a Streamlit dashboard and "
            "FastAPI. Revenue comes from tiered subscriptions (NT$499/month Pro, NT$999/month API) "
            "justified by time saved on manual comparable-rent research and reduced vacancy risk.",
            styles["Body"],
        )
    )

    story.append(Paragraph("2. Target Customer (Required Component 1)", styles["Section"]))
    story.append(
        Paragraph(
            "<b>Primary segment:</b> Independent landlords in Taipei City and New Taipei City who "
            "self-manage 2–15 residential units and price vacancies without a dedicated analyst team.",
            styles["Body"],
        )
    )
    story.append(Paragraph("<b>Persona — Mr. Lin, 42:</b>", styles["Body"]))
    bullets = [
        "Owns 6 units across 大安區 and 板橋; works full-time in finance.",
        "Current workflow: browse 591 listings, ask agent friends, maintain an Excel sheet.",
        "Job-to-be-done: set a defensible listing rent within 48 hours of a tenant move-out.",
        "Why LeasePulse wins: district-level bands from Taipei open-data transactions, enriched "
        "quote breakdown (P25/median/P75), and exportable justification for tenants or co-owners.",
    ]
    for item in bullets:
        story.append(Paragraph(f"• {esc(item)}", styles["LPBullet"]))

    story.append(
        Paragraph(
            "<b>Secondary segment:</b> Micro property-management firms (5–20 employees) serving "
            "dozens of units; they would use the API tier to embed quotes in internal tools.",
            styles["Body"],
        )
    )

    customer_table = Table(
        [
            ["Attribute", "Detail"],
            ["Customer type", "B2B — small business / prosumer landlord"],
            ["Industry", "Residential property management"],
            ["Company size", "1–15 units (primary); 50–200 units under management (secondary)"],
            ["Status quo", "Manual listing search, agent PDFs, spreadsheets"],
            ["Wedge", "Self-serve pricing confidence without enterprise contracts"],
        ],
        colWidths=[4.5 * cm, 12 * cm],
    )
    customer_table.setStyle(
        table_style(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ]
        )
    )
    story.append(Spacer(1, 0.2 * cm))
    story.append(customer_table)

    story.append(Paragraph("3. Evidence of Demand (Required Component 2)", styles["Section"]))
    story.append(
        Paragraph(
            "We validated demand using reproducible public evidence only — no private interviews. "
            f"All collector logic lives under the {mono('data/')} package; "
            f"{mono('make run')} executes every crawler, builds the public "
            "evidence report, ingests Taipei open data, and runs batch processing.",
            styles["BodyLeft"],
        )
    )

    reliability_table = Table(
        [
            [
                table_cell("Data source", styles),
                table_cell("Reliability", styles),
                table_cell("Limitations", styles),
            ],
            [
                table_cell("Taipei City weekly real-price CSV (official open data)", styles),
                table_cell("High — government dataset with documented schema and weekly refresh", styles),
                table_cell("Delayed vs. listing platforms; addresses not stored in product DB", styles),
            ],
            [
                table_cell("PTT rental-board crawl (last 2 years)", styles),
                table_cell("Medium — live public posts with source URLs and PII redaction", styles),
                table_cell("Forum sampling bias; not a formal market survey", styles),
            ],
            [
                table_cell("Google Trends (24 months)", styles),
                table_cell("Medium — relative search-interest index from Google", styles),
                table_cell("0–100 index only; not absolute search volume", styles),
            ],
            [
                table_cell("App Store RSS reviews (last 2 years)", styles),
                table_cell("Medium — public user reviews from Apple RSS feed", styles),
                table_cell("App-specific pain points; not landlord interviews", styles),
            ],
            [
                table_cell("Competitor pricing pages (591 listing fees + analog benchmark)", styles),
                table_cell("Medium — public pages with manually verified prices and source URLs", styles),
                table_cell("Listing fees vary by plan; verify against cited pages", styles),
            ],
        ],
        colWidths=[4.8 * cm, 5.2 * cm, 5.5 * cm],
    )
    reliability_table.setStyle(
        table_style(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )
    story.append(subsection("3.0 Data sources and reliability", styles))
    story.append(reliability_table)
    story.append(subsection("3.1 Google Trends search-interest signals (24 months)", styles))
    if trends.get("available", True) and trends.get("top_keyword_by_mean_interest"):
        story.append(
            Paragraph(
                "We collected Google Trends interest scores for rent-pricing keywords over "
                f"{mono(trends.get('timeframe', 'today 24-m'))} in "
                f"{mono(trends.get('geo', 'TW'))}. "
                "The strongest keyword by mean interest was "
                f"{data_val(trends['top_keyword_by_mean_interest'])}. "
                "Trends values are relative scores (0–100), not absolute search volume, but they "
                "show sustained attention to rent-pricing topics.",
                styles["BodyLeft"],
            )
        )
    else:
        story.append(
            Paragraph(
                "Google Trends output was not available when this report was generated. "
                f"Run {mono('make search-trends')} before {mono('make report')}.",
                styles["BodyLeft"],
            )
        )

    story.append(subsection("3.2 App Store review signals (last 2 years)", styles))
    if app_reviews.get("available", True) and app_reviews.get("reviews_collected"):
        story.append(
            Paragraph(
                f"We analyzed {app_reviews['reviews_collected']} public App Store reviews from "
                f"rental/housing apps since {mono(app_reviews.get('since_date', 'N/A'))}. "
                f"Average rating: {app_reviews.get('average_rating', 'N/A')}. "
                "Top pain keywords: "
                + ", ".join(esc(keyword) for keyword, _ in app_reviews.get("top_pain_keywords", [])[:5])
                + ". These reviews provide qualitative demand and UX pain-point evidence without "
                "private interviews.",
                styles["BodyLeft"],
            )
        )
    else:
        story.append(
            Paragraph(
                f"App Store review output was not available. Run {mono('make app-reviews')} before reporting.",
                styles["BodyLeft"],
            )
        )
    story.append(subsection("3.3 Public forum signal analysis (PTT crawl)", styles))
    forum_boards = ", ".join(
        board for board, _ in forum.get("boards", [])[:4]
    ) or "Rent_apart, rent_tao, Rent_ya, home-sale"
    pricing_ratio = forum.get("pricing_question_ratio") or 0
    forum_detail = (
        f"We crawled {forum['threads_analyzed']} public PTT rental threads using "
        f"{mono('data/collect_ptt_forum_signals.py')}. "
        f"Posts were limited to the last two years, filtered to Greater Taipei relevance, and "
        f"redacted for common PII before analysis. "
        f"{pricing_ratio:.0%} matched a pricing-question heuristic. "
        f"Boards covered include {esc(forum_boards)}. Recurring keywords include "
        + ", ".join(esc(keyword) for keyword, _ in forum.get("top_keywords", [])[:5])
        + ". "
    )
    if forum.get("median_extracted_rent_ntd"):
        forum_detail += (
            f"The median rent figure mentioned in forum posts was approximately "
            f"NT${forum['median_extracted_rent_ntd']:,.0f}/month. "
        )
    if forum.get("top_districts"):
        forum_detail += "Most discussed districts: " + ", ".join(
            esc(name) for name, _ in forum["top_districts"][:5]
        ) + ". "
    forum_detail += (
        "PTT posts are treated as qualitative demand signals, not formal market statistics."
    )
    story.append(Paragraph(forum_detail, styles["BodyLeft"]))

    story.append(subsection("3.4 Competitor and analog pricing (live crawl)", styles))
    if competitors.get("available") and competitors.get("pages_checked"):
        median_price = competitors.get("median_monthly_like_price_ntd")
        benchmarks = competitors.get("manual_verified_benchmarks") or []
        benchmark_text = ""
        if benchmarks:
            benchmark_text = " Manually verified benchmarks: " + "; ".join(
                f"{esc(item.get('product'))} ({esc(item.get('pricing_plan_name'))}) "
                f"NT${item.get('manual_verified_price_ntd'):,}"
                for item in benchmarks[:4]
            ) + "."
        price_note = (
            f"Median monthly-like benchmark: NT${median_price:,}."
            if median_price
            else "See manually verified benchmarks below."
        )
        story.append(
            Paragraph(
                f"We checked {competitors['pages_checked']} public competitor/analog pricing pages "
                f"via {mono('data/collect_competitor_pricing.py')} using sources listed in "
                f"{mono('data/sources/competitor_pricing_sources.json')}. "
                f"Products/pages: {esc(', '.join(competitors.get('products') or []))}. "
                f"{price_note}{benchmark_text} Each record stores source URL, checked time, "
                "manual verified price when available, and extracted pricing snippets.",
                styles["BodyLeft"],
            )
        )
    else:
        story.append(
            Paragraph(
                f"Competitor pricing crawl output was not available. Run {mono('make competitors')} before reporting.",
                styles["BodyLeft"],
            )
        )

    story.append(subsection("3.5 Live open-data acquisition process", styles))
    story.append(
        Paragraph(
            "Beyond qualitative validation, the product pipeline ingests real rental transactions from "
            "the Taipei City Data Platform weekly real-price report "
            f"({mono('data.taipei')}). The acquisition script "
            f"{mono('data/taipei_open_data.py')} performs: (1) HTTPS download with "
            "curl/SSL fallback; (2) rental-row filtering on CASE_T/CASE_F; (3) unit normalization "
            "(TPRICE in 萬元, UPRICE in NTD/ping, SDATE ROC-date parsing); (4) export to "
            f"{mono('data/processed/transactions_ingest.csv')}. Our latest run "
            f"produced {open_data['rental_rows']} cleaned rental records across "
            f"{open_data['districts']} Taipei districts. Highest median-rent districts: "
            + ", ".join(
                f"{esc(name)} (NT${rent:,}/mo)" for name, rent in open_data["top_districts"]
            )
            + ".",
            styles["Body"],
        )
    )

    story.append(subsection("3.6 Willingness to invest (time, effort, money)", styles))
    invest_table = Table(
        [
            ["Investment type", "Observed value", "LeasePulse value proposition"],
            ["Money", "Listing / tool fees on incumbent platforms", "Pro tier at NT$499; API at NT$999"],
            ["Time", "Manual listing search + spreadsheet work", "Quote in < 30 seconds"],
            ["Effort", "Multi-tab listing search + Excel", "Single dashboard + export"],
            ["Risk cost", "3+ weeks vacancy if overpriced", "P25–P75 band reduces tail risk"],
        ],
        colWidths=[3.5 * cm, 5.5 * cm, 7.5 * cm],
    )
    invest_table.setStyle(
        table_style(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )
    story.append(invest_table)

    story.append(Paragraph("4. Technical System Design", styles["Section"]))

    story.append(subsection("4.1 Data sources and ingestion", styles))
    story.append(
        Paragraph(
            "The system downloads the official Taipei City weekly real-price CSV through "
            f"{mono('data/taipei_open_data.py')} and loads it via "
            f"{mono('data/ingest.py --fetch')}. The open-data endpoint is "
            "hosted on the Taipei Data Platform. Each record includes district (行政區), building type "
            "(建物型態), area in ping, monthly rent (NTD), and transaction date parsed from ROC-format "
            f"SDATE. Raw files are archived under {mono('data/raw/')}; cleaned ingest "
            f"files under {mono('data/processed/')}. "
            f"{mono('make run')} from the repository root runs public demand evidence "
            "(PTT, Google Trends, App Store reviews, competitor pages), open-data ingest, and batch processing.",
            styles["Body"],
        )
    )

    story.append(subsection("4.2 Storage and processing", styles))
    story.append(
        Paragraph(
            "Structured facts land in PostgreSQL (SQLite locally) via SQLAlchemy models. A batch "
            f"processor ({mono('pipeline/processor.py')}) computes per-district "
            "medians and 25th/75th percentile rent-per-ping bands using Pandas. "
            "We also reuse Homework 2's MapReduce K-Means implementation "
            f"({mono('pipeline/mapreduce_kmeans.py')}, adapted from "
            f"{mono('hw2/hw_r14921059/mapper.py')} and "
            f"{mono('reducer.py')}) to segment the market into budget/value/premium/luxury "
            "clusters on features (area_ping, rent_per_ping). At 100× scale, Pandas and K-Means map to "
            "Spark batch jobs over parquet files in object storage.",
            styles["Body"],
        )
    )

    story.append(subsection("4.3 Delivery", styles))
    story.append(
        Paragraph(
            "Customers consume the product through two layers:",
            styles["Body"],
        )
    )
    delivery_points = [
        f"<b>Streamlit dashboard</b> ({mono('dashboard/app.py')}): district rent "
        "charts, HW2 K-Means segments, and an interactive quote form. After submission, the quote "
        "view shows conservative/market/aggressive monthly rent, rent-per-ping, annual rent, a bar "
        "chart, sample-size/confidence metadata, and strategy notes.",
        f"<b>FastAPI REST layer</b> ({mono('app/main.py')}): typed endpoints including "
        f"{mono('/health')}, {mono('/metrics/districts')}, "
        f"{mono('/quote')}, {mono('/clusters')}, and "
        f"{mono('/docs')}. The root path {mono('/')} renders an "
        "HTML navigation page with clickable links to each endpoint so graders can explore the API "
        "without memorizing URLs.",
        f"<b>Enriched quote API:</b> {mono('/quote')} returns P25/median/P75 monthly "
        "rent, rent-per-ping bands, annual rent estimates, pricing guidance labels, sample size, and "
        "last-updated timestamp — not just a single number.",
    ]
    for point in delivery_points:
        story.append(Paragraph(f"• {point}", styles["LPBullet"]))

    story.append(subsection("4.4 Architecture diagram", styles))
    story.append(architecture_table())

    tech_table = Table(
        [
            [
                table_cell("Layer", styles),
                table_cell("Technology", styles),
                table_cell("Rationale", styles),
            ],
            [
                table_cell("Ingestion", styles),
                table_cell("Python + requests/curl", styles),
                table_cell("Official Taipei CSV download", styles),
            ],
            [
                table_cell("Storage", styles),
                table_cell("PostgreSQL / SQLite", styles),
                table_cell("Relational aggregates, indexed lookups", styles),
            ],
            [
                table_cell("Processing", styles),
                table_cell("Pandas + HW2<br/>MapReduce K-Means", styles),
                table_cell("District stats + market segments", styles),
            ],
            [
                table_cell("API", styles),
                table_cell("FastAPI + Uvicorn", styles),
                table_cell("Typed REST delivery, easy deployment", styles),
            ],
            [
                table_cell("UI", styles),
                table_cell("Streamlit + Plotly", styles),
                table_cell("Rapid SMB dashboard, demo-friendly", styles),
            ],
            [
                table_cell("Ops", styles),
                table_cell("Docker Compose", styles),
                table_cell("Reproducible local and cloud deploy", styles),
            ],
        ],
        colWidths=[2.8 * cm, 5.2 * cm, 8.5 * cm],
    )
    tech_table.setStyle(
        table_style(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )
    story.append(tech_table)

    story.append(subsection("4.5 Implementation snapshot", styles))
    impl_table = Table(
        [
            [table_cell("Artifact", styles), table_cell("Location", styles), table_cell("Purpose", styles)],
            [table_cell("Open-data fetch", styles), table_cell("data/taipei_open_data.py", styles), table_cell("Download & clean Taipei CSV", styles)],
            [table_cell("PTT forum crawl", styles), table_cell("data/collect_ptt_forum_signals.py", styles), table_cell("Public demand-evidence collection", styles)],
            [table_cell("Evidence report", styles), table_cell("data/collect_public_demand_evidence.py", styles), table_cell("Public demand evidence summary", styles)],
            [table_cell("Ingestion CLI", styles), table_cell("data/ingest.py --fetch", styles), table_cell("Load live data into DB", styles)],
            [table_cell("Batch pipeline", styles), table_cell("pipeline/processor.py", styles), table_cell("District metrics + K-Means", styles)],
            [table_cell("API home", styles), table_cell("GET /", styles), table_cell("Clickable endpoint navigation", styles)],
            [table_cell("Quote UI", styles), table_cell("dashboard/app.py", styles), table_cell("Expanded rent-band breakdown", styles)],
            [table_cell("Report generator", styles), table_cell("report/generate_report.py", styles), table_cell("Regenerate r14921059.pdf", styles)],
        ],
        colWidths=[3.2 * cm, 5.8 * cm, 7.5 * cm],
    )
    impl_table.setStyle(
        table_style(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )
    story.append(impl_table)

    story.append(subsection("4.6 Scalability and unit economics (optional)", styles))
    story.append(
        Paragraph(
            f"At MVP (~{open_data['rental_rows']} live transactions, 50 paying users), estimated "
            "infra cost is under USD 25/month on a small VM plus managed Postgres. Gross margin at "
            "NT$499 × 50 ≈ NT$25k/month exceeds infra by an order of magnitude. At 100× data volume, "
            "batch processing shifts to Spark; API read load is served from precomputed aggregates, "
            "keeping query latency stable.",
            styles["Body"],
        )
    )

    story.append(
        Paragraph("5. Go-to-Market Difficulties (Bonus Component 3)", styles["Section"])
    )

    gtm_points = [
        (
            "<b>Trust and adoption:</b> Landlords may trust agent relationships over an unknown SaaS "
            "dashboard. Mitigation: show transaction sample sizes, confidence scores, and side-by-side "
            "comparisons with their current manual method."
        ),
        (
            "<b>Data acquisition cost:</b> Government open data is free but delayed; listing platforms "
            "are fresher but license-bound. Over-reliance on scraped listings creates ToS and PDPA "
            "exposure."
        ),
        (
            "<b>Legal / privacy:</b> Even aggregate rental products must avoid exposing identifiable "
            "tenant or landlord records. Production requires PDPA review and clear retention policies."
        ),
        (
            "<b>Cold start:</b> Sparse districts yield wide bands and low confidence — early users in "
            "Neihu vs. Da'an may get uneven value. We surface confidence explicitly to set expectations."
        ),
        (
            "<b>Competition:</b> 591, HousePlus, or banks could bundle similar analytics. Our moat is "
            "narrow focus on micro-landlords, faster self-serve UX, and pricing aligned to their "
            "willingness to pay — not enterprise sales cycles."
        ),
        (
            "<b>Unit economics:</b> CAC via Facebook landlord groups is low, but churn rises if vacancies "
            "are rare (users pause subscriptions). Annual plans and vacancy-triggered alerts improve "
            "retention."
        ),
    ]
    for point in gtm_points:
        story.append(Paragraph(f"• {point}", styles["LPBullet"]))

    story.append(Paragraph("6. Business Model Summary", styles["Section"]))
    story.append(
        Paragraph(
            "Free tier: read-only district snapshot. Pro (NT$499/mo): custom quotes, exports, email "
            "support. API (NT$999/mo): programmatic access for micro property managers. Optional "
            "one-off vacancy report (NT$299) acts as conversion hook. Primary acquisition: PTT/LINE "
            "landlord communities, NTU alumni networks, and agent referral rebates.",
            styles["Body"],
        )
    )

    story.append(Paragraph("7. Repository and Reproducibility", styles["Section"]))
    story.append(
        Paragraph(
            "Source code, configuration, and documentation are published at:<br/>"
            f"{mono(GITHUB_URL)}<br/><br/>"
            "Clone with:<br/>"
            f"{mono(GITHUB_CLONE_URL)}<br/><br/>"
            "The repository includes ingestion scripts, batch pipeline, API, dashboard, "
            "Docker configuration, HW2 reference code, and demand-evidence reproduction "
            "steps in README.md.",
            styles["BodyLeft"],
        )
    )
    repro_steps = [
        "git clone https://github.com/FettHsiao/bdfinal.git && cd bdfinal",
        "python3 -m venv .venv && source .venv/bin/activate && pip install -e .",
        "make run   # ptt + trends + reviews + competitors + evidence + ingest + process",
        "make api   # terminal 1 → http://localhost:8000/",
        "make dashboard   # terminal 2 → http://localhost:8501/",
        "make report   # regenerate r14921059.pdf",
    ]
    story.append(Paragraph("<b>Quick reproduction steps:</b>", styles["Body"]))
    for step in repro_steps:
        story.append(Paragraph(f"• {mono(step)}", styles["LPBullet"]))

    story.append(Paragraph("8. Conclusion", styles["Section"]))
    story.append(
        Paragraph(
            "LeasePulse Taipei demonstrates that course-scale big-data tooling — live open-data "
            "ingestion, SQL storage, batch analytics, MapReduce-style segmentation, and API/dashboard "
            "delivery — can support a credible data monetization story when paired with rigorous "
            "customer definition and demand evidence. The defensible claim is not 'big data magic,' "
            "but a focused product grounded in verifiable Taipei City transactions that saves "
            "measurable landlord research time and reduces costly vacancy mistakes.",
            styles["Body"],
        )
    )

    doc.build(story)


def main() -> None:
    build_report(OUTPUT_PDF)
    print(f"Wrote {OUTPUT_PDF}")


if __name__ == "__main__":
    main()
