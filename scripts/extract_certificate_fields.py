from pathlib import Path
import csv
import json
import re
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OCR_ITEMS_CSV = PROJECT_ROOT / "outputs" / "sample_ocr" / "all_ocr_items.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "extracted_fields"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FIELDS_CSV = OUTPUT_DIR / "certificate_field_candidates.csv"
FIELDS_JSON = OUTPUT_DIR / "certificate_field_candidates.json"


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def normalize(text):
    text = clean_text(text).lower()
    text = text.replace(":", "")
    text = text.replace(".", "")
    return text


def safe_float(value):
    try:
        return float(value)
    except Exception:
        return None


def read_items():
    grouped = defaultdict(list)

    with OCR_ITEMS_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            key = (row["certificate_type"], row["source_file"])
            grouped[key].append(
                {
                    "text": clean_text(row["text"]),
                    "confidence": safe_float(row.get("confidence")),
                    "bucket": row.get("bucket", ""),
                }
            )

    return grouped


def next_useful_text(items, start_index, max_window=4):
    for offset in range(1, max_window + 1):
        index = start_index + offset

        if index >= len(items):
            break

        text = clean_text(items[index]["text"])

        if len(text) >= 2:
            return text, items[index].get("confidence")

    return "", None


def find_after_label(items, patterns, max_window=4):
    for index, item in enumerate(items):
        text = item["text"]
        norm = normalize(text)

        for pattern in patterns:
            match = re.search(pattern, norm, flags=re.IGNORECASE)

            if match:
                # If OCR captured value after the label on the same line, use it.
                original_match = re.search(pattern, normalize(text), flags=re.IGNORECASE)
                if original_match:
                    label_words = re.sub(r"[^a-z ]", " ", pattern).split()
                    if label_words:
                        last_label_word = label_words[-1]
                        pos = norm.find(last_label_word)
                        if pos >= 0:
                            remaining = text[pos + len(last_label_word):].strip(" :-.,")
                            if len(remaining) >= 2:
                                return remaining, item.get("confidence")

                return next_useful_text(items, index, max_window=max_window)

    return "", None


def find_two_after_label(items, patterns, max_window=8):
    for index, item in enumerate(items):
        norm = normalize(item["text"])

        for pattern in patterns:
            if re.search(pattern, norm, flags=re.IGNORECASE):
                values = []

                for offset in range(1, max_window + 1):
                    target = index + offset

                    if target >= len(items):
                        break

                    text = clean_text(items[target]["text"])

                    if len(text) >= 2:
                        values.append((text, items[target].get("confidence")))

                    if len(values) >= 2:
                        return values

    return []


def detect_title(cert_type, items):
    combined = " ".join(normalize(item["text"]) for item in items[:20])

    if "birth" in combined:
        return "Certificate of Birth"

    if "death" in combined or "defuncion" in combined or "defunción" in combined:
        return "Certificate of Death"

    if "marriage" in combined or "matrimonial" in combined or "matrimonio" in combined:
        return "Marriage Contract"

    return cert_type.title() + " Certificate"


def add_field(rows, cert_type, source_file, field_name, value, confidence, method):
    value = clean_text(value)

    if not value:
        return

    review_status = "review_needed"

    if confidence is not None:
        if confidence >= 0.85:
            review_status = "high_confidence"
        elif confidence >= 0.65:
            review_status = "medium_confidence"

    rows.append(
        {
            "certificate_type": cert_type,
            "source_file": source_file,
            "field_name": field_name,
            "field_value_candidate": value,
            "confidence": "" if confidence is None else round(confidence, 4),
            "review_status": review_status,
            "extraction_method": method,
        }
    )


def extract_birth(cert_type, source_file, items):
    rows = []

    add_field(rows, cert_type, source_file, "document_title", detect_title(cert_type, items), None, "keyword/title detection")

    field_patterns = {
        "date_of_birth": [r"date of b[a-z]*rth", r"dato of b[a-z]*rth"],
        "place_of_birth": [r"place of [be]irth", r"place of birth"],
        "sex": [r"sex", r"sax"],
        "father_name": [r"name of father", r"name or fothor", r"name of fothor"],
        "mother_name": [r"name of mother", r"name of hother", r"n[a-z]* of nother"],
        "remarks": [r"remarks", r"remark"],
        "local_civil_registrar": [r"local civil registrar", r"lopal civil registrar"],
    }

    for field_name, patterns in field_patterns.items():
        value, confidence = find_after_label(items, patterns)
        add_field(rows, cert_type, source_file, field_name, value, confidence, "label-following-text")

    return rows


def extract_death(cert_type, source_file, items):
    rows = []

    add_field(rows, cert_type, source_file, "document_title", detect_title(cert_type, items), None, "keyword/title detection")

    field_patterns = {
        "deceased_name": [r"name of deceased", r"nombre del difunto"],
        "age": [r"age", r"edad"],
        "sex": [r"sex", r"sexo"],
        "occupation": [r"occupation", r"oficio"],
        "nationality": [r"nationality", r"nacionalidad"],
        "marital_status": [r"married single widowed", r"casado soltero"],
        "date_of_death": [r"date of death", r"fecha de la def"],
        "place_of_death": [r"place of death", r"lugar de la def"],
        "duration_of_illness": [r"duration of illness", r"duraci"],
        "residence": [r"residence of deceased", r"domi"],
        "physician_name": [r"name of physician", r"nombre del m"],
        "burial_place": [r"permit issued for burial at", r"burial at"],
    }

    for field_name, patterns in field_patterns.items():
        value, confidence = find_after_label(items, patterns)
        add_field(rows, cert_type, source_file, field_name, value, confidence, "label-following-text")

    return rows


def extract_marriage(cert_type, source_file, items):
    rows = []

    add_field(rows, cert_type, source_file, "document_title", detect_title(cert_type, items), None, "keyword/title detection")

    pairs = {
        "contracting_parties": [r"contracting parties", r"parties contract"],
        "ages": [r"age", r"edad"],
        "nationalities": [r"nationality", r"nacionalidad"],
        "residences": [r"residence", r"besidencia"],
        "fathers": [r"father", r"padre"],
        "mothers": [r"mother", r"madre"],
        "witnesses": [r"witnesses", r"testigos"],
    }

    for field_name, patterns in pairs.items():
        values = find_two_after_label(items, patterns)

        if len(values) >= 1:
            add_field(rows, cert_type, source_file, field_name + "_value_1", values[0][0], values[0][1], "two-column-label-following-text")

        if len(values) >= 2:
            add_field(rows, cert_type, source_file, field_name + "_value_2", values[1][0], values[1][1], "two-column-label-following-text")

    return rows


def main():
    grouped = read_items()
    all_rows = []

    for (cert_type, source_file), items in sorted(grouped.items()):
        if cert_type == "birth":
            extracted = extract_birth(cert_type, source_file, items)
        elif cert_type == "death":
            extracted = extract_death(cert_type, source_file, items)
        elif cert_type == "marriage":
            extracted = extract_marriage(cert_type, source_file, items)
        else:
            extracted = []

        all_rows.extend(extracted)

    with FIELDS_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "certificate_type",
            "source_file",
            "field_name",
            "field_value_candidate",
            "confidence",
            "review_status",
            "extraction_method",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    FIELDS_JSON.write_text(json.dumps(all_rows, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Field extraction complete.")
    print(f"Field candidates: {len(all_rows)}")
    print(f"CSV saved to: {FIELDS_CSV}")
    print(f"JSON saved to: {FIELDS_JSON}")


if __name__ == "__main__":
    main()