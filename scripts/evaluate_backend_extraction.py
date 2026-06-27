import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_CSV = BASE_DIR / "outputs" / "sample_ocr" / "all_ocr_items_with_boxes.csv"
OUTPUT_DIR = BASE_DIR / "outputs" / "backend_evaluation"
DOCS_DIR = BASE_DIR / "docs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)

SUMMARY_CSV = OUTPUT_DIR / "backend_extraction_summary.csv"
DETAIL_JSON = OUTPUT_DIR / "backend_extraction_details.json"
QUALITY_CSV = OUTPUT_DIR / "backend_field_quality_summary.csv"
REPORT_MD = DOCS_DIR / "08_BACKEND_EXTRACTION_EVALUATION.md"


sys.path.insert(0, str(BASE_DIR))

from app.main import build_structured_certificate, classify_certificate


# =========================================================
# CSV LOADING HELPERS
# =========================================================

def safe_float(value, default=""):
    try:
        if value == "" or value is None:
            return default

        return float(value)
    except Exception:
        return default


def normalize_col(row, *possible_names):
    for name in possible_names:
        if name in row and row[name] not in [None, ""]:
            return row[name]

    return ""


def load_grouped_ocr_items():
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"Missing input file: {INPUT_CSV}\n"
            "Run scripts/build_ocr_items_with_boxes.py first, or make sure "
            "outputs/sample_ocr/all_ocr_items_with_boxes.csv exists."
        )

    grouped = defaultdict(list)

    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            source_file = normalize_col(
                row,
                "source_file",
                "file_name",
                "filename",
                "image_file",
                "image_path",
            )

            certificate_type = normalize_col(
                row,
                "certificate_type",
                "cert_type",
                "type",
                "category",
            )

            if not source_file:
                source_file = "unknown_file"

            key = (certificate_type, source_file)

            text = normalize_col(row, "text", "ocr_text", "rec_text")
            confidence = safe_float(normalize_col(row, "confidence", "score", "rec_score"), 0)

            x_min = safe_float(normalize_col(row, "x_min", "xmin"), "")
            y_min = safe_float(normalize_col(row, "y_min", "ymin"), "")
            x_max = safe_float(normalize_col(row, "x_max", "xmax"), "")
            y_max = safe_float(normalize_col(row, "y_max", "ymax"), "")
            x_center = safe_float(normalize_col(row, "x_center", "xcenter"), "")
            y_center = safe_float(normalize_col(row, "y_center", "ycenter"), "")

            if not text:
                continue

            grouped[key].append(
                {
                    "text": text,
                    "confidence": confidence,
                    "review_status": "high_confidence" if confidence >= 0.85 else "review_needed",
                    "x_min": x_min,
                    "y_min": y_min,
                    "x_max": x_max,
                    "y_max": y_max,
                    "x_center": x_center,
                    "y_center": y_center,
                }
            )

    return grouped


# =========================================================
# FIELD QUALITY VALIDATION
# =========================================================

def normalize_text(value):
    value = str(value or "").lower()
    value = re.sub(r"[^a-z0-9 ñáéíóúü.'/-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def is_review_needed(value):
    value_norm = normalize_text(value)

    return value_norm in {
        "",
        "review needed",
        "none",
        "null",
        "n/a",
        "na",
        "unknown",
    }


def is_label_only(value):
    value_norm = normalize_text(value)

    label_only_values = {
        "name",
        "age",
        "edad",
        "sex",
        "sexo",
        "date",
        "place",
        "birth",
        "death",
        "marriage",
        "father",
        "mother",
        "witness",
        "witnesses",
        "testigos",
        "husband",
        "wife",
        "esposo",
        "esposa",
        "nationality",
        "nacionalidad",
        "occupation",
        "residence",
        "residencia",
        "registry",
        "certificate",
        "remarks",
        "field",
        "province",
        "provincia",
        "city",
        "municipality",
        "years",
        "months",
        "days",
        "year",
        "month",
        "day",
    }

    if value_norm in label_only_values:
        return True

    return False


def has_label_noise(value):
    value_norm = normalize_text(value)

    noisy_phrases = [
        "years edad",
        "months meses",
        "days dias",
        "lugar de la defunci",
        "se expidi",
        "se expid",
        "registry no",
        "book no",
        "page no",
        "city or municipality",
        "ciudad o municipio",
        "province of",
        "provincia de",
        "contracting parties",
        "partes contrayentes",
        "marriage contract",
        "contrato matrimonial",
        "republic of the philippines",
        "republica de filipinas",
        "office of the",
        "oficina del",
        "relation to minor",
        "persona que dio",
        "solemnizing this",
        "certificate",
    ]

    for phrase in noisy_phrases:
        if phrase in value_norm:
            return True

    return False


def is_too_short_or_symbolic(value):
    value_norm = normalize_text(value)

    if len(value_norm) <= 1:
        return True

    if not re.search(r"[a-zA-Z0-9]", value_norm):
        return True

    return False


def looks_like_valid_name(value):
    value = str(value or "").strip()

    if is_review_needed(value):
        return False

    if has_label_noise(value):
        return False

    words = re.findall(r"[A-Za-zñÑ.'-]{2,}", value)

    if len(words) >= 2:
        return True

    return False


def looks_like_valid_age(value):
    value = str(value or "").strip()

    if is_review_needed(value):
        return False

    if re.search(r"\b\d{1,3}\s*\.?\s*(yrs?|years?)\.?\b", value, flags=re.IGNORECASE):
        return True

    if re.fullmatch(r"\d{1,3}", value.strip()):
        return True

    return False


def looks_like_valid_date(value):
    value = str(value or "").strip()

    if is_review_needed(value):
        return False

    date_patterns = [
        r"\b[A-Za-z]+\s+\d{1,2},\s+\d{4}\b",
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        r"\b\d{4}-\d{1,2}-\d{1,2}\b",
    ]

    for pattern in date_patterns:
        if re.search(pattern, value):
            return True

    return False


def looks_like_valid_place(value):
    value = str(value or "").strip()

    if is_review_needed(value):
        return False

    if has_label_noise(value):
        return False

    words = re.findall(r"[A-Za-zñÑ.'-]{2,}", value)

    if len(words) >= 1 and len(value) >= 4:
        return True

    return False


def looks_like_valid_general_value(value):
    value = str(value or "").strip()

    if is_review_needed(value):
        return False

    if is_label_only(value):
        return False

    if has_label_noise(value):
        return False

    if is_too_short_or_symbolic(value):
        return False

    return True


def field_quality_status(field_name, value):
    """
    Returns:
    - useful
    - review_needed
    - questionable
    """

    if is_review_needed(value):
        return "review_needed"

    if is_label_only(value) or has_label_noise(value) or is_too_short_or_symbolic(value):
        return "questionable"

    name_fields = {
        "husband_name",
        "wife_name",
        "husband_father",
        "wife_father",
        "husband_mother",
        "wife_mother",
        "husband_witness",
        "wife_witness",
        "child_name",
        "father",
        "mother",
        "deceased_name",
    }

    age_fields = {
        "husband_age",
        "wife_age",
        "age",
    }

    date_fields = {
        "date_of_marriage",
        "date_of_birth",
        "date_of_death",
    }

    place_fields = {
        "place_of_marriage",
        "place_of_birth",
        "place_of_death",
        "residence",
        "husband_residence",
        "wife_residence",
        "cause_or_burial",
    }

    if field_name in name_fields:
        return "useful" if looks_like_valid_name(value) else "questionable"

    if field_name in age_fields:
        return "useful" if looks_like_valid_age(value) else "questionable"

    if field_name in date_fields:
        return "useful" if looks_like_valid_date(value) else "questionable"

    if field_name in place_fields:
        return "useful" if looks_like_valid_place(value) else "questionable"

    return "useful" if looks_like_valid_general_value(value) else "questionable"


# =========================================================
# STRUCTURED OUTPUT ANALYSIS
# =========================================================

def flatten_key_fields(structured):
    cert_type = structured.get("certificate_type", "unknown")

    flattened = {}

    if cert_type == "marriage":
        flattened = {
            "husband_name": structured.get("husband", {}).get("name", ""),
            "wife_name": structured.get("wife", {}).get("name", ""),
            "husband_age": structured.get("husband", {}).get("age", ""),
            "wife_age": structured.get("wife", {}).get("age", ""),
            "husband_nationality": structured.get("husband", {}).get("nationality", ""),
            "wife_nationality": structured.get("wife", {}).get("nationality", ""),
            "husband_occupation": structured.get("husband", {}).get("occupation", ""),
            "wife_occupation": structured.get("wife", {}).get("occupation", ""),
            "husband_residence": structured.get("husband", {}).get("residence", ""),
            "wife_residence": structured.get("wife", {}).get("residence", ""),
            "husband_civil_status": structured.get("husband", {}).get("civil_status", ""),
            "wife_civil_status": structured.get("wife", {}).get("civil_status", ""),
            "husband_father": structured.get("husband", {}).get("father", ""),
            "wife_father": structured.get("wife", {}).get("father", ""),
            "husband_mother": structured.get("husband", {}).get("mother", ""),
            "wife_mother": structured.get("wife", {}).get("mother", ""),
            "husband_witness": structured.get("husband", {}).get("witness", ""),
            "wife_witness": structured.get("wife", {}).get("witness", ""),
            "date_of_marriage": structured.get("marriage_details", {}).get("date_of_marriage", ""),
            "place_of_marriage": structured.get("marriage_details", {}).get("place_of_marriage", ""),
            "solemnized_by": structured.get("marriage_details", {}).get("solemnized_by", ""),
            "city_or_municipality": structured.get("location", {}).get("city_or_municipality", ""),
            "province": structured.get("location", {}).get("province", ""),
        }

    elif cert_type == "birth":
        flattened = {
            "child_name": structured.get("child", {}).get("name", ""),
            "sex": structured.get("child", {}).get("sex", ""),
            "date_of_birth": structured.get("child", {}).get("date_of_birth", ""),
            "place_of_birth": structured.get("child", {}).get("place_of_birth", ""),
            "father": structured.get("parents", {}).get("father", ""),
            "mother": structured.get("parents", {}).get("mother", ""),
            "registry_number": structured.get("registration", {}).get("registry_number", ""),
            "remarks": structured.get("registration", {}).get("remarks", ""),
        }

    elif cert_type == "death":
        flattened = {
            "deceased_name": structured.get("deceased", {}).get("name", ""),
            "age": structured.get("deceased", {}).get("age", ""),
            "sex": structured.get("deceased", {}).get("sex", ""),
            "nationality": structured.get("deceased", {}).get("nationality", ""),
            "occupation": structured.get("deceased", {}).get("occupation", ""),
            "residence": structured.get("deceased", {}).get("residence", ""),
            "date_of_death": structured.get("death_details", {}).get("date_of_death", ""),
            "place_of_death": structured.get("death_details", {}).get("place_of_death", ""),
            "cause_or_burial": structured.get("death_details", {}).get("cause_or_burial", ""),
            "registry_number": structured.get("registration", {}).get("registry_number", ""),
            "remarks": structured.get("registration", {}).get("remarks", ""),
        }

    return flattened


def evaluate_flattened_fields(flattened):
    useful = 0
    review_needed = 0
    questionable = 0
    field_statuses = {}

    for field_name, value in flattened.items():
        status = field_quality_status(field_name, value)
        field_statuses[f"{field_name}_quality"] = status

        if status == "useful":
            useful += 1
        elif status == "review_needed":
            review_needed += 1
        else:
            questionable += 1

    return {
        "useful_fields": useful,
        "review_needed_fields": review_needed,
        "questionable_fields": questionable,
        "field_statuses": field_statuses,
    }


# =========================================================
# MAIN EVALUATION
# =========================================================

def main():
    grouped = load_grouped_ocr_items()

    summary_rows = []
    quality_rows = []
    detail_output = []

    type_totals = defaultdict(
        lambda: {
            "files": 0,
            "ocr_items": 0,
            "useful_fields": 0,
            "review_needed_fields": 0,
            "questionable_fields": 0,
            "total_key_fields": 0,
        }
    )

    for (certificate_type_from_csv, source_file), items in grouped.items():
        detected_type = certificate_type_from_csv

        if not detected_type:
            detected_type = classify_certificate([item["text"] for item in items])

        result = {
            "source_file": source_file,
            "certificate_type": detected_type,
            "ocr_text_count": len(items),
            "field_candidates": [],
            "ocr_items": items,
        }

        structured = build_structured_certificate(result)
        flattened = flatten_key_fields(structured)
        quality = evaluate_flattened_fields(flattened)

        total_key_fields = len(flattened)

        extraction_rate = 0

        if total_key_fields > 0:
            extraction_rate = round((quality["useful_fields"] / total_key_fields) * 100, 2)

        summary_row = {
            "source_file": source_file,
            "certificate_type": structured.get("certificate_type", detected_type),
            "layout_type": structured.get("layout_type", "unknown"),
            "ocr_items": len(items),
            "total_key_fields": total_key_fields,
            "useful_fields": quality["useful_fields"],
            "questionable_fields": quality["questionable_fields"],
            "review_needed_fields": quality["review_needed_fields"],
            "useful_extraction_rate_percent": extraction_rate,
        }

        summary_row.update(flattened)
        summary_rows.append(summary_row)

        quality_row = {
            "source_file": source_file,
            "certificate_type": structured.get("certificate_type", detected_type),
            "layout_type": structured.get("layout_type", "unknown"),
        }
        quality_row.update(quality["field_statuses"])
        quality_rows.append(quality_row)

        cert_type = structured.get("certificate_type", detected_type)
        type_totals[cert_type]["files"] += 1
        type_totals[cert_type]["ocr_items"] += len(items)
        type_totals[cert_type]["useful_fields"] += quality["useful_fields"]
        type_totals[cert_type]["review_needed_fields"] += quality["review_needed_fields"]
        type_totals[cert_type]["questionable_fields"] += quality["questionable_fields"]
        type_totals[cert_type]["total_key_fields"] += total_key_fields

        detail_output.append(
            {
                "source_file": source_file,
                "structured_certificate": structured,
                "flattened_fields": flattened,
                "quality": quality,
            }
        )

    summary_fieldnames = sorted(
        {
            key
            for row in summary_rows
            for key in row.keys()
        }
    )

    ordered_first = [
        "source_file",
        "certificate_type",
        "layout_type",
        "ocr_items",
        "total_key_fields",
        "useful_fields",
        "questionable_fields",
        "review_needed_fields",
        "useful_extraction_rate_percent",
    ]

    summary_fieldnames = ordered_first + [
        key for key in summary_fieldnames if key not in ordered_first
    ]

    with SUMMARY_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fieldnames, extrasaction="ignore")
        writer.writeheader()

        for row in summary_rows:
            writer.writerow(row)

    quality_fieldnames = sorted(
        {
            key
            for row in quality_rows
            for key in row.keys()
        }
    )

    ordered_quality_first = [
        "source_file",
        "certificate_type",
        "layout_type",
    ]

    quality_fieldnames = ordered_quality_first + [
        key for key in quality_fieldnames if key not in ordered_quality_first
    ]

    with QUALITY_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=quality_fieldnames, extrasaction="ignore")
        writer.writeheader()

        for row in quality_rows:
            writer.writerow(row)

    DETAIL_JSON.write_text(json.dumps(detail_output, indent=2, ensure_ascii=False), encoding="utf-8")

    total_files = len(summary_rows)
    total_ocr_items = sum(row["ocr_items"] for row in summary_rows)
    total_key_fields = sum(row["total_key_fields"] for row in summary_rows)
    total_useful = sum(row["useful_fields"] for row in summary_rows)
    total_questionable = sum(row["questionable_fields"] for row in summary_rows)
    total_review_needed = sum(row["review_needed_fields"] for row in summary_rows)

    overall_rate = 0

    if total_key_fields > 0:
        overall_rate = round((total_useful / total_key_fields) * 100, 2)

    report_lines = []
    report_lines.append("# Backend Extraction Evaluation")
    report_lines.append("")
    report_lines.append("## Purpose")
    report_lines.append("")
    report_lines.append(
        "This report summarizes backend structured extraction results for the collected certificate samples. "
        "The system uses OCR text, OCR confidence scores, and bounding box coordinates to produce structured, "
        "reviewable digital certificate data."
    )
    report_lines.append("")
    report_lines.append("This version includes a field-quality check so that label-only, noisy, or weak OCR fragments are not automatically counted as successful extraction.")
    report_lines.append("")
    report_lines.append("## Overall Summary")
    report_lines.append("")
    report_lines.append("| Metric | Value |")
    report_lines.append("|---|---:|")
    report_lines.append(f"| Files evaluated | {total_files} |")
    report_lines.append(f"| OCR text items processed | {total_ocr_items} |")
    report_lines.append(f"| Total key fields checked | {total_key_fields} |")
    report_lines.append(f"| Useful structured fields | {total_useful} |")
    report_lines.append(f"| Questionable structured fields | {total_questionable} |")
    report_lines.append(f"| Review-needed fields | {total_review_needed} |")
    report_lines.append(f"| Useful extraction rate | {overall_rate}% |")
    report_lines.append("")
    report_lines.append("## Summary by Certificate Type")
    report_lines.append("")
    report_lines.append("| Certificate Type | Files | OCR Items | Key Fields | Useful | Questionable | Review Needed | Useful Rate |")
    report_lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")

    for cert_type, totals in sorted(type_totals.items()):
        rate = 0

        if totals["total_key_fields"] > 0:
            rate = round((totals["useful_fields"] / totals["total_key_fields"]) * 100, 2)

        report_lines.append(
            f"| {cert_type} | {totals['files']} | {totals['ocr_items']} | "
            f"{totals['total_key_fields']} | {totals['useful_fields']} | "
            f"{totals['questionable_fields']} | {totals['review_needed_fields']} | {rate}% |"
        )

    report_lines.append("")
    report_lines.append("## Quality Categories")
    report_lines.append("")
    report_lines.append("- `useful`: The value appears usable as a structured field.")
    report_lines.append("- `questionable`: The value is present but may be noisy, label-only, incomplete, or suspicious.")
    report_lines.append("- `review_needed`: The field was missing or explicitly marked for human review.")
    report_lines.append("")
    report_lines.append("## Current Backend Capabilities")
    report_lines.append("")
    report_lines.append("- Detects certificate type as birth, death, marriage, or unknown.")
    report_lines.append("- Performs layout-aware structured extraction for the marriage two-column contract format.")
    report_lines.append("- Provides basic structured fallback extraction for birth and death certificates.")
    report_lines.append("- Preserves raw OCR text for review and auditing.")
    report_lines.append("- Marks missing or uncertain values as `Review needed` instead of inventing values.")
    report_lines.append("- Evaluates extracted fields using quality rules to avoid overcounting weak OCR fragments.")
    report_lines.append("")
    report_lines.append("## Current Limitations")
    report_lines.append("")
    report_lines.append("- Extraction quality depends heavily on OCR quality and scan clarity.")
    report_lines.append("- Handwritten and cursive portions may not be reliably transcribed.")
    report_lines.append("- Birth and death templates currently use basic fallback extraction.")
    report_lines.append("- Multiple historical certificate formats require additional layout-specific extractors.")
    report_lines.append("- Field-quality rules are heuristic and should be manually reviewed during validation.")
    report_lines.append("")
    report_lines.append("## Generated Files")
    report_lines.append("")
    report_lines.append(f"- `{SUMMARY_CSV.relative_to(BASE_DIR)}`")
    report_lines.append(f"- `{QUALITY_CSV.relative_to(BASE_DIR)}`")
    report_lines.append(f"- `{DETAIL_JSON.relative_to(BASE_DIR)}`")
    report_lines.append("")

    REPORT_MD.write_text("\n".join(report_lines), encoding="utf-8")

    print("Backend extraction evaluation complete.")
    print(f"Summary CSV: {SUMMARY_CSV}")
    print(f"Quality CSV: {QUALITY_CSV}")
    print(f"Detail JSON: {DETAIL_JSON}")
    print(f"Markdown report: {REPORT_MD}")


if __name__ == "__main__":
    main()