from pathlib import Path
import csv
import json
import re
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = PROJECT_ROOT / "outputs" / "sample_ocr" / "all_ocr_items_with_boxes.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "position_extracted_fields"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV = OUTPUT_DIR / "position_field_candidates.csv"
OUTPUT_JSON = OUTPUT_DIR / "position_field_candidates.json"


FIELD_LABELS = {
    "birth": {
        "date_of_birth": ["date of birth", "dato of birth", "date of b rth"],
        "place_of_birth": ["place of birth", "place of eirth"],
        "sex": ["sex", "sax"],
        "father_name": ["name of father", "name or father", "name of fothor"],
        "mother_name": ["name of mother", "name of hother", "name of nother"],
        "remarks": ["remarks"],
    },
    "death": {
        "deceased_name": ["name of deceased", "nombre del difunto"],
        "age": ["age", "edad"],
        "sex": ["sex", "sexo"],
        "occupation": ["occupation", "oficio"],
        "nationality": ["nationality", "nacionalidad"],
        "date_of_death": ["date of death", "fecha de la def"],
        "place_of_death": ["place of death", "lugar de la def"],
        "residence": ["residence of deceased", "domicilio del difunto"],
        "physician_name": ["name of physician", "nombre del medico", "nombre del médico"],
        "burial_place": ["burial at", "remains interred", "permit issued for burial"],
    },
    "marriage": {
        "husband_name": ["husband", "esposo"],
        "wife_name": ["wife", "esposa"],
        "contracting_parties": ["contracting parties", "partes contrayentes"],
        "age": ["age", "edad"],
        "nationality": ["nationality", "nacionalidad"],
        "residence": ["residence", "residencia"],
        "father": ["father", "padre"],
        "mother": ["mother", "madre"],
        "witnesses": ["witnesses", "testigos"],
    },
}


BAD_VALUE_WORDS = {
    "year", "month", "day", "years", "months", "days",
    "edad", "sexo", "nationality", "nacionalidad",
    "occupation", "oficio", "residence", "residencia",
    "lugar de la defunción", "domicilio del difunto",
    "date", "place", "name", "father", "mother",
}


def norm(text):
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9 ñáéíóúü/-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def read_rows():
    grouped = defaultdict(list)

    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            text = (row.get("text") or "").strip()
            if not text:
                continue

            item = {
                "certificate_type": row["certificate_type"],
                "source_file": row["source_file"],
                "item_index": int(row["item_index"]),
                "text": text,
                "norm": norm(text),
                "confidence": safe_float(row.get("confidence")),
                "x_min": safe_float(row.get("x_min")),
                "y_min": safe_float(row.get("y_min")),
                "x_max": safe_float(row.get("x_max")),
                "y_max": safe_float(row.get("y_max")),
                "x_center": safe_float(row.get("x_center")),
                "y_center": safe_float(row.get("y_center")),
            }

            grouped[(row["certificate_type"], row["source_file"])].append(item)

    for key in grouped:
        grouped[key].sort(key=lambda x: (x["y_center"], x["x_center"]))

    return grouped


def is_bad_value(text):
    n = norm(text)

    if len(n) <= 1:
        return True

    if n in BAD_VALUE_WORDS:
        return True

    if any(n == bad for bad in BAD_VALUE_WORDS):
        return True

    if "certificate" in n and len(n.split()) <= 4:
        return True

    return False


def label_matches(item, label_variants):
    n = item["norm"]
    return any(label in n for label in label_variants)


def find_right_candidate(label_item, items):
    candidates = []

    for item in items:
        if item is label_item:
            continue

        same_line = abs(item["y_center"] - label_item["y_center"]) <= 25
        to_right = item["x_min"] > label_item["x_max"]

        if same_line and to_right and not is_bad_value(item["text"]):
            distance = item["x_min"] - label_item["x_max"]
            candidates.append((distance, item))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def find_below_candidate(label_item, items):
    candidates = []

    for item in items:
        if item is label_item:
            continue

        below = 0 < (item["y_center"] - label_item["y_center"]) <= 80
        horizontally_near = abs(item["x_center"] - label_item["x_center"]) <= 220

        if below and horizontally_near and not is_bad_value(item["text"]):
            distance = abs(item["y_center"] - label_item["y_center"]) + abs(item["x_center"] - label_item["x_center"]) * 0.25
            candidates.append((distance, item))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def extract_for_file(cert_type, source_file, items):
    results = []

    labels = FIELD_LABELS.get(cert_type, {})

    for field_name, variants in labels.items():
        best = None

        for item in items:
            if not label_matches(item, variants):
                continue

            candidate = find_right_candidate(item, items)

            method = "right-of-label"

            if candidate is None:
                candidate = find_below_candidate(item, items)
                method = "below-label"

            if candidate is None:
                continue

            if best is None or candidate["confidence"] > best["confidence"]:
                best = {
                    "certificate_type": cert_type,
                    "source_file": source_file,
                    "field_name": field_name,
                    "field_value_candidate": candidate["text"],
                    "confidence": round(candidate["confidence"], 4),
                    "review_status": confidence_status(candidate["confidence"]),
                    "extraction_method": method,
                    "label_text": item["text"],
                    "candidate_x": candidate["x_center"],
                    "candidate_y": candidate["y_center"],
                }

        if best:
            results.append(best)

    return results


def confidence_status(score):
    if score >= 0.85:
        return "high_confidence"
    if score >= 0.65:
        return "medium_confidence"
    return "review_needed"


def main():
    grouped = read_rows()
    all_results = []

    for (cert_type, source_file), items in sorted(grouped.items()):
        all_results.extend(extract_for_file(cert_type, source_file, items))

    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "certificate_type",
            "source_file",
            "field_name",
            "field_value_candidate",
            "confidence",
            "review_status",
            "extraction_method",
            "label_text",
            "candidate_x",
            "candidate_y",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)

    OUTPUT_JSON.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Position-aware extraction complete.")
    print(f"Rows: {len(all_results)}")
    print(f"CSV: {OUTPUT_CSV}")
    print(f"JSON: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()