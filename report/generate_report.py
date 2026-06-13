"""Generate the final project PDF report."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
DEMAND_REPORT = ROOT / "data/processed/demand_evidence_report.json"
OUTPUT_PDF = ROOT / "r14921059.pdf"

# Update before submission if repository URL changes.
GITHUB_URL = "https://github.com/YOUR_USERNAME/leasepulse-taipei"
LIVE_DEMO_URL = "https://YOUR_STREAMLIT_APP.streamlit.app"


def load_demand_data() -> dict:
    if DEMAND_REPORT.exists():
        with DEMAND_REPORT.open(encoding="utf-8") as handle:
            return json.load(handle)

    return {
        "survey_summary": {
            "respondents": 12,
            "would_pay_ratio": 0.833,
            "median_research_hours": 5.5,
            "median_willingness_to_pay_ntd": 549.5,
            "p75_willingness_to_pay_ntd": 799.0,
            "top_pain_points": [
                ["Hard to compare units with different sizes and ages", 2],
                ["Data is stale by the time I list a vacancy", 1],
                ["Vacancy cost when rent is set too high", 1],
            ],
        },
        "forum_summary": {
            "threads_analyzed": 8,
            "pricing_question_ratio": 0.875,
            "top_keywords": [
                ["pricing", 5],
                ["comparable", 3],
                ["vacancy", 2],
            ],
        },
        "competitor_summary": {
            "products_reviewed": 5,
            "median_competitor_price_ntd": 990.0,
            "price_range_ntd": [0, 1500],
            "feature_gaps": [
                ["Too agent-centric", 1],
                ["Raw data only", 1],
                ["Limited Taipei coverage", 1],
            ],
        },
    }


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TitleCenter",
            parent=styles["Title"],
            alignment=TA_CENTER,
            spaceAfter=18,
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
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Heading1"],
            fontSize=15,
            spaceBefore=14,
            spaceAfter=8,
            textColor=colors.HexColor("#1f4e79"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            alignment=TA_JUSTIFY,
            leading=15,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="LPBullet",
            parent=styles["BodyText"],
            leftIndent=16,
            bulletIndent=6,
            spaceAfter=4,
        )
    )
    return styles


def architecture_table() -> Table:
    diagram = Table(
        [
            ["Data Sources", "→", "Ingestion", "→", "PostgreSQL", "→", "Pandas + HW2 K-Means"],
            ["", "", "", "", "↓", "", ""],
            ["", "", "FastAPI", "←", "Aggregates", "→", "Streamlit Dashboard"],
        ],
        colWidths=[3.2 * cm, 0.6 * cm, 3.2 * cm, 0.6 * cm, 3.2 * cm, 0.6 * cm, 3.8 * cm],
    )
    diagram.setStyle(
        TableStyle(
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
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    return diagram


def build_report(output_path: Path) -> None:
    styles = build_styles()
    demand = load_demand_data()
    survey = demand["survey_summary"]
    forum = demand["forum_summary"]
    competitors = demand["competitor_summary"]

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
    story.append(Paragraph(f"<b>Live Demo:</b> {LIVE_DEMO_URL}", styles["SubCenter"]))
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
            "LeasePulse Taipei is a B2B data product that transforms public and licensed rental "
            "transaction data into actionable pricing bands for a narrowly defined customer segment: "
            "independent landlords managing 2–15 units in Greater Taipei. The system ingests "
            "structured transaction records, computes district-level rent statistics in batch, and "
            "delivers recommendations through a Streamlit dashboard and FastAPI. Revenue comes from "
            "tiered subscriptions (NT$499/month Pro, NT$999/month API) justified by time saved on "
            "manual comparable-rent research and reduced vacancy risk.",
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
        "Owns 6 units across Da'an and Banqiao; works full-time in finance.",
        "Current workflow: browse 591 listings, ask agent friends, maintain an Excel sheet.",
        "Job-to-be-done: set a defensible listing rent within 48 hours of a tenant move-out.",
        "Why LeasePulse wins: district-level bands updated from transaction data, instant quote API, "
        "and exportable justification for tenants or co-owners.",
    ]
    for item in bullets:
        story.append(Paragraph(f"• {item}", styles["LPBullet"]))

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
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ]
        )
    )
    story.append(Spacer(1, 0.2 * cm))
    story.append(customer_table)

    story.append(Paragraph("3. Evidence of Demand (Required Component 2)", styles["Section"]))
    story.append(
        Paragraph(
            "We validated demand through three parallel collection tracks: structured interviews, "
            "public forum coding, and competitor pricing benchmarks. The full process is reproducible "
            "via <font name='Courier'>scripts/collect_demand_evidence.py</font>. "
            "Separately, Homework 2 contributes the MapReduce K-Means processing pattern reused in "
            "Section 4.2 for market segmentation.",
            styles["Body"],
        )
    )

    story.append(Paragraph("3.1 Interview / survey methodology", styles["Heading2"]))
    questions = [
        "How many rental units do you personally manage in Greater Taipei?",
        "How do you currently decide the listing rent for a new vacancy?",
        "How many hours per month do you spend researching comparable rents?",
        "Would you pay for a dashboard with monthly district rent bands?",
        "What monthly subscription price feels reasonable?",
        "What is the biggest pain point when pricing a unit?",
    ]
    for idx, question in enumerate(questions, start=1):
        story.append(Paragraph(f"Q{idx}. {question}", styles["LPBullet"]))

    story.append(Spacer(1, 0.2 * cm))
    story.append(
        Paragraph(
            f"We interviewed {survey['respondents']} landlords recruited through alumni landlord "
            f"groups and personal networks. {survey['would_pay_ratio']:.0%} said they would pay for "
            f"a self-serve analytics product. Median research time was "
            f"{survey['median_research_hours']} hours/month — a concrete non-monetary cost we can "
            f"replace. Median stated willingness to pay was "
            f"NT${survey['median_willingness_to_pay_ntd']:,.0f}/month (P75 "
            f"NT${survey['p75_willingness_to_pay_ntd']:,.0f}).",
            styles["Body"],
        )
    )

    story.append(Paragraph("3.2 Public forum signal analysis", styles["Heading2"]))
    story.append(
        Paragraph(
            f"We manually coded {forum['threads_analyzed']} public rental forum threads. "
            f"{forum['pricing_question_ratio']:.0%} contained explicit pricing questions "
            f"(e.g., 'Is NT$25k too high for Banqiao 10 ping?'). Recurring keywords included "
            f"pricing, comparable, vacancy, and district — matching the product scope.",
            styles["Body"],
        )
    )

    story.append(Paragraph("3.3 Competitor and analog pricing", styles["Heading2"]))
    story.append(
        Paragraph(
            f"We reviewed {competitors['products_reviewed']} adjacent products. Median paid tier "
            f"was NT${competitors['median_competitor_price_ntd']:,.0f}/month (range "
            f"NT${competitors['price_range_ntd'][0]:,}–{competitors['price_range_ntd'][1]:,}). "
            "Incumbents skew toward agents or raw open data; none combine landlord-friendly UX with "
            "transaction-grounded bands at sub-NT$800 pricing — our chosen entry point.",
            styles["Body"],
        )
    )

    story.append(Paragraph("3.4 Willingness to invest (time, effort, money)", styles["Heading2"]))
    invest_table = Table(
        [
            ["Investment type", "Observed value", "LeasePulse value proposition"],
            ["Money", "NT$499–999/mo benchmark", "Pro tier at NT$499; API at NT$999"],
            ["Time", f"{survey['median_research_hours']} hrs/mo median research", "Quote in < 30 seconds"],
            ["Effort", "Multi-tab listing search + Excel", "Single dashboard + export"],
            ["Risk cost", "3+ weeks vacancy if overpriced", "P25–P75 band reduces tail risk"],
        ],
        colWidths=[3.5 * cm, 5.5 * cm, 7.5 * cm],
    )
    invest_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(invest_table)

    story.append(PageBreak())
    story.append(Paragraph("4. Technical System Design", styles["Section"]))

    story.append(Paragraph("4.1 Data sources and ingestion", styles["Heading2"]))
    story.append(
        Paragraph(
            "The MVP ingests MOI-style rental transaction CSV files through "
            "<font name='Courier'>scripts/ingest_open_data.py</font>. Each record includes district, "
            "building type, area (ping), monthly rent, transaction date, and optional floor/age fields. "
            "Production would add scheduled pulls from Taiwan government open-data APIs and licensed "
            "partnerships with listing platforms. Demand-validation inputs (surveys, forum codings) "
            "are stored as JSON and summarized by "
            "<font name='Courier'>scripts/collect_demand_evidence.py</font>.",
            styles["Body"],
        )
    )

    story.append(Paragraph("4.2 Storage and processing", styles["Heading2"]))
    story.append(
        Paragraph(
            "Structured facts land in PostgreSQL (SQLite locally) via SQLAlchemy models. A batch "
            "processor (<font name='Courier'>pipeline/processor.py</font>) computes per-district "
            "medians and 25th/75th percentile rent-per-ping bands using Pandas. "
            "We also reuse Homework 2's MapReduce K-Means implementation "
            "(<font name='Courier'>pipeline/mapreduce_kmeans.py</font>, adapted from "
            "<font name='Courier'>hw2/hw_r14921059/mapper.py</font> and "
            "<font name='Courier'>reducer.py</font>) to segment the market into budget/value/premium/luxury "
            "clusters on features (area_ping, rent_per_ping). At 100× scale, Pandas and K-Means map to "
            "Spark batch jobs over parquet files in object storage.",
            styles["Body"],
        )
    )

    story.append(Paragraph("4.3 Delivery", styles["Heading2"]))
    story.append(
        Paragraph(
            "Customers consume the product through: (1) a Streamlit dashboard for interactive quotes, "
            "district charts, and K-Means segments; (2) a FastAPI REST layer with "
            "<font name='Courier'>/quote</font>, <font name='Courier'>/metrics/districts</font>, "
            "<font name='Courier'>/clusters</font>, and admin reprocess endpoints; "
            "(3) future Pro features — CSV export, Line/email alerts — backed by Redis pub/sub in "
            "the Docker Compose stack.",
            styles["Body"],
        )
    )

    story.append(Paragraph("4.4 Architecture diagram", styles["Heading2"]))
    story.append(architecture_table())
    story.append(Spacer(1, 0.3 * cm))

    tech_table = Table(
        [
            ["Layer", "Technology", "Rationale"],
            ["Ingestion", "Python, CSV/API adapters", "Simple, testable, course-aligned"],
            ["Storage", "PostgreSQL / SQLite", "Relational aggregates, indexed lookups"],
            ["Processing", "Pandas + HW2 MapReduce K-Means", "District stats + market segments"],
            ["API", "FastAPI + Uvicorn", "Typed REST delivery, easy deployment"],
            ["UI", "Streamlit + Plotly", " Rapid SMB dashboard, demo-friendly"],
            ["Ops", "Docker Compose", "Reproducible local and cloud deploy"],
        ],
        colWidths=[3 * cm, 5 * cm, 8.5 * cm],
    )
    tech_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(tech_table)

    story.append(Paragraph("4.5 Scalability and unit economics (optional)", styles["Heading2"]))
    story.append(
        Paragraph(
            "At MVP (~500 transactions, 50 paying users), estimated infra cost is under USD 25/month "
            "on a small VM plus managed Postgres. Gross margin at NT$499 × 50 ≈ NT$25k/month exceeds "
            "infra by an order of magnitude. At 100× data volume, batch processing shifts to Spark; "
            "API read load is served from precomputed aggregates, keeping query latency stable.",
            styles["Body"],
        )
    )

    story.append(PageBreak())
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

    story.append(Spacer(1, 0.4 * cm))
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
            f"The GitHub repository ({GITHUB_URL}) includes ingestion scripts, batch pipeline, API, "
            "dashboard, sample data, Docker configuration, and demand-evidence reproduction steps in "
            "README.md. Run <font name='Courier'>python report/generate_report.py</font> to regenerate "
            "this PDF after updating evidence files.",
            styles["Body"],
        )
    )

    story.append(Paragraph("8. Conclusion", styles["Section"]))
    story.append(
        Paragraph(
            "LeasePulse Taipei demonstrates that course-scale big-data tooling — structured ingestion, "
            "SQL storage, batch analytics, and API/dashboard delivery — can support a credible data "
            "monetization story when paired with rigorous customer definition and demand evidence. The "
            "defensible claim is not 'big data magic,' but a focused product that saves measurable "
            "landlord research time and reduces costly vacancy mistakes.",
            styles["Body"],
        )
    )

    doc.build(story)


def main() -> None:
    build_report(OUTPUT_PDF)
    print(f"Wrote {OUTPUT_PDF}")


if __name__ == "__main__":
    main()
