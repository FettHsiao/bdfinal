"""Reproduce demand-validation analysis for LeasePulse Taipei."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd


SURVEY_QUESTIONS = [
    "How many rental units do you personally manage in Greater Taipei?",
    "How do you currently decide the listing rent for a new vacancy?",
    "How many hours per month do you spend researching comparable rents?",
    "Would you pay for a dashboard that shows district-level rent bands updated monthly?",
    "What monthly subscription price feels reasonable for that service?",
    "What is the biggest pain point when pricing a unit?",
]


def load_json(path: Path) -> list | dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def summarize_survey(responses: list[dict]) -> dict:
    willingness_prices = [
        item["monthly_price_ntd"]
        for item in responses
        if item.get("would_pay") and item.get("monthly_price_ntd")
    ]
    hours_spent = [item["research_hours_per_month"] for item in responses]

    return {
        "respondents": len(responses),
        "would_pay_ratio": round(
            sum(1 for item in responses if item["would_pay"]) / len(responses), 3
        ),
        "median_research_hours": float(pd.Series(hours_spent).median()),
        "median_willingness_to_pay_ntd": float(pd.Series(willingness_prices).median()),
        "p75_willingness_to_pay_ntd": float(pd.Series(willingness_prices).quantile(0.75)),
        "top_pain_points": Counter(
            item["biggest_pain_point"] for item in responses
        ).most_common(3),
    }


def summarize_forum_signals(signals: list[dict]) -> dict:
    keywords = Counter()
    for item in signals:
        keywords.update(item.get("keywords", []))

    return {
        "threads_analyzed": len(signals),
        "top_keywords": keywords.most_common(8),
        "pricing_question_ratio": round(
            sum(1 for item in signals if item.get("contains_pricing_question"))
            / len(signals),
            3,
        ),
    }


def summarize_competitors(competitors: list[dict]) -> dict:
    prices = [item["monthly_price_ntd"] for item in competitors if item["monthly_price_ntd"]]
    return {
        "products_reviewed": len(competitors),
        "median_competitor_price_ntd": float(pd.Series(prices).median()),
        "price_range_ntd": [int(min(prices)), int(max(prices))],
        "feature_gaps": Counter(
            gap for item in competitors for gap in item.get("gaps_for_small_landlords", [])
        ).most_common(4),
    }


def build_report(
    survey_path: Path,
    forum_path: Path,
    competitor_path: Path,
    output_path: Path,
) -> dict:
    survey = summarize_survey(load_json(survey_path))
    forum = summarize_forum_signals(load_json(forum_path))
    competitors = summarize_competitors(load_json(competitor_path))

    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "methodology": {
            "survey_questions": SURVEY_QUESTIONS,
            "public_sources": [
                "Structured interviews with 12 independent landlords (sample data included)",
                "Manual coding of PTT Rent/board-style forum threads (sample set included)",
                "Pricing benchmark review of 5 rental analytics or listing products",
            ],
            "ethics_note": (
                "Interview participants were recruited via personal network and NTU alumni "
                "landlord groups. Forum analysis used publicly visible posts only; no private "
                "messages were collected."
            ),
        },
        "survey_summary": survey,
        "forum_summary": forum,
        "competitor_summary": competitors,
        "demand_conclusion": {
            "target_wedge": "Independent landlords managing 2-15 units in Greater Taipei",
            "evidence_strength": "Moderate — mixed qualitative and benchmark evidence",
            "recommended_price_ntd": int(survey["median_willingness_to_pay_ntd"]),
            "recommended_trial_hook": "Free district snapshot; paid alerts and custom unit sizing",
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate demand evidence report")
    parser.add_argument("--survey", default="data/sample/survey_responses.json")
    parser.add_argument("--forum", default="data/sample/forum_signals.json")
    parser.add_argument("--competitors", default="data/sample/competitor_benchmarks.json")
    parser.add_argument("--output", default="data/processed/demand_evidence_report.json")
    args = parser.parse_args()

    report = build_report(
        Path(args.survey),
        Path(args.forum),
        Path(args.competitors),
        Path(args.output),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
