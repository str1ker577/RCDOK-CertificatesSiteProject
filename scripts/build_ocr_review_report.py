from pathlib import Path
import csv
from collections import defaultdict, Counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OCR_DIR = PROJECT_ROOT / "outputs" / "sample_ocr"
DOCS_DIR = PROJECT_ROOT / "docs"
DOCS_DIR.mkdir(exist_ok=True)

ALL_ITEMS_CSV = OCR_DIR / "all_ocr_items.csv"
KEYWORD_CSV = OCR_DIR / "keyword_hits_by_file.csv"
REPORT_MD = DOCS_DIR / "05_INITIAL_OCR_SAMPLE_REVIEW.md"

KEYWORDS = {
    "birth": ["birth", "born", "child", "father", "mother", "date", "place", "registry", "certificate"],
    "death": ["death", "died", "burial", "cause", "age", "cemetery", "date", "place", "registry", "certificate"],
    "marriage": ["marriage", "groom", "bride", "husband", "wife", "witness", "sponsor", "priest", "date", "registry"],
}


def read_ocr_items():
    rows = []

    for csv_path in OCR_DIR.glob("*/*/raw_ocr_items.csv"):
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)

    return rows


def safe_float(value):
    try:
        return float(value)
    except Exception:
        return None


def main():
    rows = read_ocr_items()

    if not rows:
        print("No OCR item files found.")
        return

    by_type = defaultdict(list)
    by_file = defaultdict(list)

    for row in rows:
        cert_type = row["certificate_type"]
        source_file = row["source_file"]
        by_type[cert_type].append(row)
        by_file[(cert_type, source_file)].append(row)

    with ALL_ITEMS_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = ["certificate_type", "source_file", "text", "confidence", "bucket"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    keyword_rows = []

    for (cert_type, source_file), file_rows in sorted(by_file.items()):
        combined_text = " ".join(row["text"].lower() for row in file_rows)
        keyword_list = KEYWORDS.get(cert_type, [])

        hits = [keyword for keyword in keyword_list if keyword in combined_text]
        scores = [safe_float(row.get("confidence")) for row in file_rows]
        scores = [score for score in scores if score is not None]

        avg_confidence = round(sum(scores) / len(scores), 4) if scores else ""

        keyword_rows.append(
            {
                "certificate_type": cert_type,
                "source_file": source_file,
                "text_items": len(file_rows),
                "keyword_hits": len(hits),
                "matched_keywords": ", ".join(hits),
                "average_confidence": avg_confidence,
            }
        )

    with KEYWORD_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "certificate_type",
            "source_file",
            "text_items",
            "keyword_hits",
            "matched_keywords",
            "average_confidence",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(keyword_rows)

    report_lines = [
        "# Initial OCR Sample Review",
        "",
        "## Purpose",
        "",
        "This document summarizes the first OCR batch test for the certificate digitization project.",
        "",
        "## OCR Scope",
        "",
        "The current MVP focuses on printed and typed certificate text. Handwritten or cursive text will be treated as review-needed unless OCR confidence is clearly acceptable.",
        "",
        "## Batch Summary",
        "",
        f"- Total OCR text items detected: {len(rows)}",
        f"- Total files processed: {len(by_file)}",
        "",
        "## Results by Certificate Type",
        "",
        "| Certificate Type | Files | OCR Text Items | Average Items Per File |",
        "|---|---:|---:|---:|",
    ]

    for cert_type in sorted(by_type.keys()):
        file_count = len([key for key in by_file if key[0] == cert_type])
        item_count = len(by_type[cert_type])
        avg_items = round(item_count / file_count, 2) if file_count else 0
        report_lines.append(f"| {cert_type} | {file_count} | {item_count} | {avg_items} |")

    report_lines.extend(
        [
            "",
            "## Early Interpretation",
            "",
            "- PaddleOCR successfully processed all available sample certificate images after disabling the problematic PaddlePaddle PIR/oneDNN runtime path.",
            "- Marriage certificates produced the most OCR text items on average, suggesting they may contain denser layouts or more printed fields.",
            "- Birth certificates produced fewer OCR text items, suggesting simpler layouts or fewer visible fields.",
            "- Death certificates produced a moderate number of OCR text items and appear suitable for structured field extraction testing.",
            "",
            "## MVP Decision",
            "",
            "The project should proceed as a certificate digitization assistant, not a fully automatic cursive handwriting translator.",
            "",
            "The system will:",
            "",
            "- extract printed and typed text automatically;",
            "- attempt to read handwritten text when possible;",
            "- mark low-confidence or cursive fields for human review;",
            "- export structured CSV/JSON/TXT outputs.",
            "",
            "## Generated Output Files",
            "",
            f"- `{ALL_ITEMS_CSV.relative_to(PROJECT_ROOT)}`",
            f"- `{KEYWORD_CSV.relative_to(PROJECT_ROOT)}`",
            f"- `{OCR_DIR.relative_to(PROJECT_ROOT) / 'ocr_summary.csv'}`",
            "",
            "## Next Step",
            "",
            "Build the first field extraction rules for repeated labels in birth, death, and marriage certificates.",
            "",
        ]
    )

    REPORT_MD.write_text("\n".join(report_lines), encoding="utf-8")

    print("Review report created.")
    print(f"Combined OCR CSV: {ALL_ITEMS_CSV}")
    print(f"Keyword CSV: {KEYWORD_CSV}")
    print(f"Markdown report: {REPORT_MD}")


if __name__ == "__main__":
    main()