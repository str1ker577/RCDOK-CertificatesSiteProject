import csv
import json
import os
import re
import uuid
from pathlib import Path

# PaddleOCR / PaddlePaddle Windows runtime safety settings
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_use_onednn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from paddleocr import PaddleOCR


BASE_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs" / "web_demo"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


app = FastAPI(title="RCDOK Certificate OCR Prototype")

app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


ocr_engine = None


def get_ocr_engine():
    global ocr_engine

    if ocr_engine is None:
        ocr_engine = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    return ocr_engine


# =========================================================
# BASIC HELPERS
# =========================================================

def norm(text):
    text = normalize_ocr_mistakes(text)
    text = re.sub(r"[^a-z0-9 ñáéíóúü/-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def display_value(text):
    text = str(text or "").strip()
    text = re.sub(r"\s+", " ", text)

    if not text:
        return "Review needed"

    bad_values = {
        "husband",
        "wife",
        "esposo",
        "esposa",
        "age",
        "edad",
        "nationality",
        "nacionalidad",
        "occupation",
        "residence",
        "father",
        "mother",
        "witnesses",
        "testigos",
        "review needed",
        "none",
        "null",
        "nan",
        "n/a",
        "na",
        "unknown",
    }

    if norm(text) in bad_values:
        return "Review needed"

    return text


def find_first_key(data, key_name):
    if isinstance(data, dict):
        if key_name in data:
            return data[key_name]

        for value in data.values():
            found = find_first_key(value, key_name)

            if found is not None:
                return found

    if isinstance(data, list):
        for item in data:
            found = find_first_key(item, key_name)

            if found is not None:
                return found

    return None


def box_to_bounds(box):
    if not box:
        return "", "", "", "", "", ""

    if isinstance(box, list) and all(isinstance(x, (int, float)) for x in box) and len(box) >= 4:
        x1, y1, x2, y2 = box[:4]
        return x1, y1, x2, y2, (x1 + x2) / 2, (y1 + y2) / 2

    points = []

    if isinstance(box, list):
        for item in box:
            if isinstance(item, list) and len(item) >= 2:
                points.append(item[:2])

    if not points:
        return "", "", "", "", "", ""

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    x_min = min(xs)
    y_min = min(ys)
    x_max = max(xs)
    y_max = max(ys)

    return x_min, y_min, x_max, y_max, (x_min + x_max) / 2, (y_min + y_max) / 2


def classify_certificate(texts):
    normalized_lines = [norm(text) for text in texts if text]
    combined = " ".join(normalized_lines)

    # Remove misleading phrases that appear on birth certificates.
    combined_for_scoring = combined.replace("for marriage purposes", "")
    combined_for_scoring = combined_for_scoring.replace("marriage purposes", "")

    birth_score = 0
    death_score = 0
    marriage_score = 0

    # Strong birth signals
    if "certificate of birth" in combined_for_scoring:
        birth_score += 10

    if "civil register of births" in combined_for_scoring:
        birth_score += 8

    if "date of birth" in combined_for_scoring:
        birth_score += 5

    if "place of birth" in combined_for_scoring:
        birth_score += 5

    if "name of father" in combined_for_scoring:
        birth_score += 3

    if "name of mother" in combined_for_scoring:
        birth_score += 3

    if "birth" in combined_for_scoring:
        birth_score += 3

    # Strong death signals
    if "certificate of death" in combined_for_scoring:
        death_score += 10

    if "certificado de defuncion" in combined_for_scoring or "certificado de defunción" in combined_for_scoring:
        death_score += 8

    if "name of deceased" in combined_for_scoring:
        death_score += 5

    if "nombre del difunto" in combined_for_scoring:
        death_score += 5

    if "date of death" in combined_for_scoring:
        death_score += 5

    if "place of death" in combined_for_scoring:
        death_score += 5

    if "deceased" in combined_for_scoring or "difunto" in combined_for_scoring:
        death_score += 3

    # Strong marriage signals
    if "marriage contract" in combined_for_scoring:
        marriage_score += 10

    if "contrato matrimonial" in combined_for_scoring:
        marriage_score += 10

    if "contracting parties" in combined_for_scoring:
        marriage_score += 6

    if "partes contrayentes" in combined_for_scoring:
        marriage_score += 6

    if "husband" in combined_for_scoring and "wife" in combined_for_scoring:
        marriage_score += 6

    if "esposo" in combined_for_scoring and "esposa" in combined_for_scoring:
        marriage_score += 6

    if "solemnized" in combined_for_scoring:
        marriage_score += 4

    if "witnesses" in combined_for_scoring or "testigos" in combined_for_scoring:
        marriage_score += 2

    scores = {
        "birth": birth_score,
        "death": death_score,
        "marriage": marriage_score,
    }

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    if best_score <= 0:
        return "unknown"

    return best_type

def confidence_status(score):
    try:
        score = float(score)
    except Exception:
        return "review_needed"

    if score >= 0.85:
        return "high_confidence"

    if score >= 0.65:
        return "medium_confidence"

    return "review_needed"


def valid_ocr_items(result):
    items = result.get("ocr_items", [])

    return [
        item
        for item in items
        if item.get("text")
        and item.get("x_center") != ""
        and item.get("y_center") != ""
        and item.get("x_min") != ""
        and item.get("x_max") != ""
    ]


def sort_items(items):
    return sorted(items, key=lambda item: (float(item["y_center"]), float(item["x_center"])))


def full_ocr_text(items):
    return " ".join(str(item.get("text", "")) for item in sort_items(items))


def clean_spaces(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()

def normalize_ocr_mistakes(text):
    text = text or ""

    replacements = {
        "sax": "sex",
        "temale": "female",
        "famale": "female",
        "femele": "female",
        "hnle": "male",
        "mole": "male",
        "dato": "date",
        "b rth": "birth",
        "eirth": "birth",
        "fothor": "father",
        "hother": "mother",
        "nother": "mother",
        "naume": "name",
        "nauwe": "name",
        "reristor": "registrar",
        "registlar": "registrar",
        "defuneión": "defuncion",
        "defunción": "defuncion",
        "difunto": "deceased",
        "alos": "años",
        "aos": "años",
        "varm": "varon",
        "heubra": "hembra",
        "hesmha": "hembra",
    }

    lowered = text.lower()

    for wrong, correct in replacements.items():
        lowered = lowered.replace(wrong, correct)

    return lowered

def clean_display_value(value):
    if value is None:
        return "Review needed"

    text = str(value).strip()

    if not text:
        return "Review needed"

    lower = text.lower().strip()

    direct_fixes = {
        "temale": "Female",
        "famale": "Female",
        "femele": "Female",
        "heubra": "Female",
        "hembra": "Female",
        "varm": "Male",
        "varon": "Male",
        "varón": "Male",
    }

    if lower in direct_fixes:
        return direct_fixes[lower]

    bad_fragments = [
        "review needed",
        "name of",
        "nombre del",
        "domiellio del difunto",
        "domicilio del difunto",
        "gelipria",
        "of birth",
        "of death",
        "date of",
        "place of",
        "civil registrar",
        "local civil registrar",
        "certificate of",
    ]

    if any(fragment in lower for fragment in bad_fragments):
        return "Review needed"

    if len(text) <= 2:
        return "Review needed"

    if re.fullmatch(r"[\W_]+", text):
        return "Review needed"

    return text


def clean_structured_certificate_for_display(data):
    if isinstance(data, dict):
        return {
            key: clean_structured_certificate_for_display(value)
            for key, value in data.items()
        }

    if isinstance(data, list):
        return [clean_structured_certificate_for_display(value) for value in data]

    if isinstance(data, str):
        return clean_display_value(data)

    return data


# =========================================================
# FIELD CANDIDATES
# =========================================================

def is_bad_candidate(text):
    cleaned = norm(text)

    bad_values = {
        "",
        "year",
        "month",
        "day",
        "years",
        "months",
        "days",
        "age",
        "edad",
        "sex",
        "sexo",
        "name",
        "father",
        "mother",
        "nationality",
        "nacionalidad",
        "occupation",
        "residence",
        "residencia",
        "witnesses",
        "testigos",
        "husband",
        "wife",
        "esposo",
        "esposa",
        "certificate",
        "marriage contract",
        "contrato matrimonial",
    }

    if cleaned in bad_values:
        return True

    if len(cleaned) <= 1:
        return True

    return False


def extract_field_candidates(cert_type, items):
    labels = {
        "birth": {
            "date_of_birth": ["date of birth", "date of live birth", "born", "birth"],
            "place_of_birth": ["place of birth"],
            "sex": ["sex"],
            "father_name": ["father", "name of father"],
            "mother_name": ["mother", "name of mother"],
            "remarks": ["remarks"],
        },
        "death": {
            "deceased_name": ["name of deceased", "deceased", "nombre del difunto"],
            "age": ["age", "edad"],
            "sex": ["sex", "sexo"],
            "occupation": ["occupation", "oficio"],
            "nationality": ["nationality", "nacionalidad"],
            "date_of_death": ["date of death", "fecha de la def"],
            "place_of_death": ["place of death", "lugar de la def"],
            "residence": ["residence of deceased", "domicilio del difunto"],
            "physician_name": ["name of physician", "nombre del medico", "nombre del médico"],
            "burial_place": ["burial", "cemetery", "interred"],
        },
        "marriage": {
            "contracting_parties": ["contracting parties", "partes contrayentes"],
            "husband": ["husband", "esposo"],
            "wife": ["wife", "esposa"],
            "father": ["father", "padre"],
            "mother": ["mother", "madre"],
            "witnesses": ["witnesses", "testigos"],
            "residence": ["residence", "residencia"],
        },
    }

    field_map = labels.get(cert_type, {})
    candidates = []
    sorted_items = sorted(items, key=lambda x: (x["y_center"], x["x_center"]))

    for field_name, variants in field_map.items():
        best_candidate = None

        for label_item in sorted_items:
            label_norm = norm(label_item["text"])

            if not any(variant in label_norm for variant in variants):
                continue

            possible_values = []

            for item in sorted_items:
                if item == label_item:
                    continue

                if is_bad_candidate(item["text"]):
                    continue

                same_line = abs(item["y_center"] - label_item["y_center"]) <= 30
                to_right = item["x_min"] > label_item["x_max"]
                below = 0 < item["y_center"] - label_item["y_center"] <= 90
                near_x = abs(item["x_center"] - label_item["x_center"]) <= 260

                if same_line and to_right:
                    distance_score = item["x_min"] - label_item["x_max"]
                    possible_values.append((distance_score, "right-of-label", item))

                elif below and near_x:
                    distance_score = (item["y_center"] - label_item["y_center"]) + abs(
                        item["x_center"] - label_item["x_center"]
                    ) * 0.25
                    possible_values.append((distance_score, "below-label", item))

            if possible_values:
                possible_values.sort(key=lambda x: x[0])
                _, method, selected_item = possible_values[0]

                candidate = {
                    "field_name": field_name,
                    "field_value_candidate": selected_item["text"],
                    "confidence": round(selected_item["confidence"], 4),
                    "review_status": confidence_status(selected_item["confidence"]),
                    "method": method,
                    "label_text": label_item["text"],
                }

                if best_candidate is None or selected_item["confidence"] > best_candidate["confidence"]:
                    best_candidate = candidate

        if best_candidate:
            candidates.append(best_candidate)

    return candidates


def build_certificate_summary(result):
    summary = {
        "certificate_type": result.get("certificate_type", "unknown").title(),
        "full_name": "Review needed",
        "date_primary": "Review needed",
        "place_primary": "Review needed",
        "parent_or_spouse": "Review needed",
        "church_or_registry": "Review needed",
        "remarks": "Review needed",
    }

    for field in result.get("field_candidates", []):
        name = field.get("field_name", "")
        value = field.get("field_value_candidate", "")

        if not value:
            continue

        if name in ["deceased_name", "contracting_parties", "father_name", "mother_name"]:
            if summary["full_name"] == "Review needed":
                summary["full_name"] = value

        if name in ["date_of_birth", "date_of_death"]:
            summary["date_primary"] = value

        if name in ["place_of_birth", "place_of_death", "residence", "burial_place"]:
            if summary["place_primary"] == "Review needed":
                summary["place_primary"] = value

        if name in ["father", "mother", "father_name", "mother_name", "wife", "husband"]:
            if summary["parent_or_spouse"] == "Review needed":
                summary["parent_or_spouse"] = value

        if name in ["remarks", "burial_place"]:
            summary["remarks"] = value

    return summary


def build_digital_certificate(result):
    cert_type = result.get("certificate_type", "unknown").title()

    return {
        "title": f"Digitalized {cert_type} Certificate",
        "certificate_type": cert_type,
    }


# =========================================================
# LAYOUT HELPERS
# =========================================================

def find_all_y_of_keyword(items, keywords):
    matches = []

    for item in items:
        text = norm(item.get("text", ""))

        for keyword in keywords:
            if keyword in text:
                matches.append(float(item.get("y_center", 0)))

    return sorted(matches)


def find_y_after(items, keywords, after_y=None):
    candidates = find_all_y_of_keyword(items, keywords)

    if after_y is not None:
        candidates = [y for y in candidates if y > after_y]

    if not candidates:
        return None

    return min(candidates)


def get_row_text(items, row_y, x_min, x_max, tolerance=13):
    if row_y is None:
        return "Review needed"

    selected = []

    for item in items:
        try:
            x = float(item.get("x_center", 0))
            y = float(item.get("y_center", 0))
        except Exception:
            continue

        if x_min <= x <= x_max and abs(y - row_y) <= tolerance:
            text = str(item.get("text", "")).strip()

            if text:
                selected.append((x, text))

    selected.sort(key=lambda row: row[0])

    if not selected:
        return "Review needed"

    return " ".join(text for _, text in selected)


def get_area_text(items, x_min, x_max, y_min, y_max):
    selected = []

    for item in items:
        try:
            x = float(item.get("x_center", 0))
            y = float(item.get("y_center", 0))
        except Exception:
            continue

        if x_min <= x <= x_max and y_min <= y <= y_max:
            text = str(item.get("text", "")).strip()

            if text:
                selected.append((y, x, text))

    selected.sort(key=lambda row: (row[0], row[1]))

    if not selected:
        return "Review needed"

    return " ".join(text for _, _, text in selected)


def pick_regex(text, patterns):
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)

        if match:
            return display_value(match.group(1))

    return "Review needed"


def clean_general_value(text):
    text = str(text or "")

    noise_patterns = [
        r"\bhusband\b",
        r"\bwife\b",
        r"\besposo\b",
        r"\besposa\b",
        r"\bcontracting parties\b",
        r"\bpartes contrayentes\b",
        r"\bage\b",
        r"\bedad\b",
        r"\bnationality\b",
        r"\bnacionalidad\b",
        r"\boccupation\b",
        r"\bocupacion\b",
        r"\bocupación\b",
        r"\bresidence\b",
        r"\bresidencia\b",
        r"\bfather\b",
        r"\bpadre\b",
        r"\bmother\b",
        r"\bmadre\b",
        r"\bwitnesses\b",
        r"\btestigos\b",
        r"\bfield\b",
        r"\bprovince\b",
        r"\bprovincia\b",
        r"\bcity\b",
        r"\bmunicipality\b",
    ]

    cleaned = text

    for pattern in noise_patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip(" .:-")

    return display_value(cleaned)


# =========================================================
# GENERAL STRUCTURED EXTRACTION HELPERS
# =========================================================

def clean_extracted_value(value):
    value = str(value or "")
    value = re.sub(r"\s+", " ", value).strip(" .:-")

    bad_fragments = [
        "republic of the philippines",
        "republica de filipinas",
        "office of the",
        "oficina del",
        "civil registrar",
        "municipal registrar",
        "certificate",
        "registry",
        "page no",
        "book no",
        "entry no",
        "form no",
        "remarks",
        "signature",
        "prepared by",
        "verified by",
        "received by",
        "issued by",
    ]

    value_norm = norm(value)

    for fragment in bad_fragments:
        if fragment in value_norm:
            return "Review needed"

    if len(value_norm) <= 1:
        return "Review needed"

    return display_value(value)


def clean_name_value(value):
    value = str(value or "")
    value = re.sub(
        r"\b(Name|Child|Father|Mother|Deceased|Informant|Applicant|Registry|Certificate|Birth|Death|Sex|Age|Date|Place)\b",
        " ",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\b(Male|Female|Filipino|Filipina|Single|Married|Widowed|Years|Months|Days|Age|Edad)\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\d+", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" .:-")

    words = re.findall(r"[A-Za-zñÑ.'-]{2,}", value)

    if len(words) >= 2:
        return display_value(" ".join(words))

    return clean_extracted_value(value)


def clean_place_value(value):
    value = str(value or "")
    value = re.sub(
        r"\b(Place|Lugar|Birth|Death|Born|Died|Date|Fecha|City|Municipality|Province|of|de|la|el)\b",
        " ",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\s+", " ", value).strip(" .:-")

    return clean_extracted_value(value)


def clean_date_value(value):
    value = str(value or "")

    date_patterns = [
        r"([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        r"(\d{1,2}/\d{1,2}/\d{2,4})",
        r"(\d{4}-\d{1,2}-\d{1,2})",
        r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
    ]

    for pattern in date_patterns:
        match = re.search(pattern, value)

        if match:
            return display_value(match.group(1))

    return clean_extracted_value(value)


def clean_age_value(value):
    value = str(value or "")

    match = re.search(r"\b(\d{1,3})\s*\.?\s*(yrs?|years?)\.?\b", value, flags=re.IGNORECASE)

    if match:
        return f"{match.group(1)} yrs"

    match = re.search(r"\b(\d{1,3})\b", value)

    if match:
        return f"{match.group(1)} yrs"

    return "Review needed"


def clean_sex_value(value):
    value = str(value or "")

    if re.search(r"\bmale\b", value, flags=re.IGNORECASE):
        return "Male"

    if re.search(r"\bfemale\b", value, flags=re.IGNORECASE):
        return "Female"

    if re.search(r"\bm\b", value.strip(), flags=re.IGNORECASE):
        return "Male"

    if re.search(r"\bf\b", value.strip(), flags=re.IGNORECASE):
        return "Female"

    return "Review needed"


def clean_nationality_value(value):
    value = str(value or "")

    match = re.search(r"\b(Filipino|Filipina|American|Chinese|Spanish)\b", value, flags=re.IGNORECASE)

    if match:
        return display_value(match.group(1))

    return clean_extracted_value(value)


def find_best_after_label(items, labels, x_mode="right_or_below", max_y_gap=95):
    sorted_items = sort_items(items)
    best = None

    for label_item in sorted_items:
        label_text = norm(label_item.get("text", ""))

        if not any(label in label_text for label in labels):
            continue

        for item in sorted_items:
            if item == label_item:
                continue

            if is_bad_candidate(item.get("text", "")):
                continue

            same_line = abs(float(item["y_center"]) - float(label_item["y_center"])) <= 25
            to_right = float(item["x_min"]) > float(label_item["x_max"])
            below = 0 < float(item["y_center"]) - float(label_item["y_center"]) <= max_y_gap
            near_x = abs(float(item["x_center"]) - float(label_item["x_center"])) <= 320

            score = None

            if x_mode == "right_only":
                if same_line and to_right:
                    score = float(item["x_min"]) - float(label_item["x_max"])

            elif x_mode == "below_only":
                if below and near_x:
                    score = float(item["y_center"]) - float(label_item["y_center"])

            else:
                if same_line and to_right:
                    score = float(item["x_min"]) - float(label_item["x_max"])
                elif below and near_x:
                    score = 1000 + (float(item["y_center"]) - float(label_item["y_center"]))

            if score is not None:
                candidate = (score, item.get("text", ""))

                if best is None or candidate[0] < best[0]:
                    best = candidate

    if best:
        return display_value(best[1])

    return "Review needed"


def find_nearby_row_value(items, labels, value_cleaner=None):
    value = find_best_after_label(items, labels, x_mode="right_or_below")

    if value_cleaner:
        return value_cleaner(value)

    return clean_extracted_value(value)


def find_by_regex_full_text(items, patterns, cleaner=None):
    text = full_ocr_text(items)

    value = pick_regex(text, patterns)

    if cleaner:
        return cleaner(value)

    return clean_extracted_value(value)


def find_registry_number(items):
    text = full_ocr_text(items)

    patterns = [
        r"(?:Registry|Reg\.?|Register)\s*(?:No\.?|Number)?\s*[:\-]?\s*([A-Za-z0-9\-./]{2,40})",
        r"(?:Book|Page|Entry)\s*(?:No\.?)?\s*[:\-]?\s*([A-Za-z0-9\-./]{2,40})",
        r"\bNo\.?\s*([A-Za-z0-9\-./]{2,40})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)

        if match:
            candidate = match.group(1).strip(" .:-")

            if len(candidate) >= 2:
                return display_value(candidate)

    return "Review needed"


# =========================================================
# MARRIAGE EXTRACTOR
# =========================================================

def extract_age(text):
    return clean_age_value(text)


def extract_nationality(text, preferred=None):
    text = str(text or "")

    if preferred == "wife":
        match = re.search(r"\b(Filipina)\b", text, flags=re.IGNORECASE)

        if match:
            return "Filipina"

    if preferred == "husband":
        match = re.search(r"\b(Filipino)\b", text, flags=re.IGNORECASE)

        if match:
            return "Filipino"

    return clean_nationality_value(text)


def extract_civil_status(text):
    match = re.search(r"\b(Single|Widowed|Divorced|Married)\b", str(text), flags=re.IGNORECASE)

    if match:
        return display_value(match.group(1))

    return "Review needed"


def extract_occupation(text):
    text = str(text or "")

    known_occupations = [
        "Laborer",
        "Housekeeper",
        "Farmer",
        "Teacher",
        "Merchant",
        "Student",
        "Driver",
        "Worker",
        "Carpenter",
        "Priest",
    ]

    for occupation in known_occupations:
        if re.search(rf"\b{re.escape(occupation)}\b", text, flags=re.IGNORECASE):
            return occupation

    cleaned = re.sub(r"\b(Filipino|Filipina)\b", " ", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\d{1,3}\s*\.?\s*(yrs?|years?)\.?", " ", cleaned, flags=re.IGNORECASE)

    return clean_general_value(cleaned)


def clean_person_name(text):
    text = clean_general_value(text)

    if text == "Review needed":
        return text

    remove_words = [
        "Filipino",
        "Filipina",
        "Single",
        "Laborer",
        "Housekeeper",
        "Nabulao",
        "Naabulao",
        "Sipalay",
        "Siplay",
        "Siphlay",
        "yrs",
        "yrs.",
        "years",
    ]

    cleaned = text

    for word in remove_words:
        cleaned = re.sub(rf"\b{re.escape(word)}\b", " ", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\d+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .:-")

    if len(cleaned.split()) >= 2:
        return display_value(cleaned)

    return display_value(text)


def clean_residence(text):
    text = str(text or "")
    text = re.sub(
        r"\b(Single|Laborer|Housekeeper|Filipino|Filipina|\d{1,3}\s*yrs?\.?)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s+", " ", text).strip(" .:-")
    return display_value(text)


def split_name_from_age_row(text):
    text = str(text or "")

    age_match = re.search(r"\d{1,3}\s*\.?\s*(?:yrs?|years?)\.?", text, flags=re.IGNORECASE)

    if not age_match:
        return clean_person_name(text), "Review needed"

    before = text[: age_match.start()]
    age = age_match.group(0)

    return clean_person_name(before), display_value(age)


def find_column_regions(items, max_x):
    husband_header_x = None
    wife_header_x = None

    for item in items:
        text = norm(item.get("text", ""))

        if "husband" in text or "esposo" in text:
            husband_header_x = float(item.get("x_center", 0))

        if "wife" in text or "esposa" in text:
            wife_header_x = float(item.get("x_center", 0))

    if husband_header_x is None:
        husband_header_x = max_x * 0.43

    if wife_header_x is None:
        wife_header_x = max_x * 0.68

    midpoint = (husband_header_x + wife_header_x) / 2

    husband_min = max(max_x * 0.34, 0)
    husband_max = midpoint

    wife_min = midpoint
    wife_max = max_x * 0.95

    return {
        "husband": (husband_min, husband_max),
        "wife": (wife_min, wife_max),
    }


def get_clean_row_values(items, row_y, regions, tolerance=15):
    husband_raw = get_row_text(items, row_y, regions["husband"][0], regions["husband"][1], tolerance)
    wife_raw = get_row_text(items, row_y, regions["wife"][0], regions["wife"][1], tolerance)

    return husband_raw, wife_raw


def get_field_rows(items):
    contracting_y = find_y_after(items, ["contracting parties", "partes contrayentes"])
    age_y = find_y_after(items, ["age", "edad"], contracting_y)
    nationality_y = find_y_after(items, ["nationality", "nacionalidad"], age_y)
    occupation_y = find_y_after(items, ["occupation", "ocupacion", "ocupación"], nationality_y)
    residence_y = find_y_after(items, ["residence", "residencia"], occupation_y)
    civil_y = find_y_after(items, ["single", "widowed", "divorced", "soltero", "viudo"], residence_y)
    father_y = find_y_after(items, ["father", "padre"], civil_y)
    mother_y = find_y_after(items, ["mother", "madre"], father_y)
    witness_y = find_y_after(items, ["witnesses", "testigos"], mother_y)

    return {
        "contracting": contracting_y,
        "age": age_y,
        "nationality": nationality_y,
        "occupation": occupation_y,
        "residence": residence_y,
        "civil": civil_y,
        "father": father_y,
        "mother": mother_y,
        "witness": witness_y,
    }


def clean_location_value(text):
    text = str(text or "")
    text = re.sub(r"\b(City|Municipality|Province|Ciudad|Municipio|Provincia|of|de)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" .:-")

    known_places = [
        "Sipalay",
        "Negros Occ.",
        "Negros Occidental",
        "Bacolod",
        "Nabulao",
        "Nabulao Catholic Church",
    ]

    for place in known_places:
        if re.search(re.escape(place), text, flags=re.IGNORECASE):
            return place

    return display_value(text)


def extract_top_location(items, max_x):
    max_y = max(float(item["y_center"]) for item in items)
    top_y_limit = max_y * 0.18
    top_text = get_area_text(items, 0, max_x, 0, top_y_limit)

    city = pick_regex(
        top_text,
        [
            r"Municipality of\s+([A-Za-zñÑ\s.'-]{2,30})",
            r"City or Municipality of\s+([A-Za-zñÑ\s.'-]{2,30})",
            r"Ciudad o Municipio de\s+([A-Za-zñÑ\s.'-]{2,30})",
        ],
    )

    province = pick_regex(
        top_text,
        [
            r"Province of\s+([A-Za-zñÑ\s.'-]{2,35})",
            r"Provincia de\s+([A-Za-zñÑ\s.'-]{2,35})",
        ],
    )

    if city == "Review needed" and re.search(r"\bSipalay\b", top_text, flags=re.IGNORECASE):
        city = "Sipalay"

    if province == "Review needed" and re.search(r"Negros\s+Occ", top_text, flags=re.IGNORECASE):
        province = "Negros Occ."

    return clean_location_value(city), clean_location_value(province)


def extract_marriage_detail_rows(items, max_x):
    place_y = find_y_after(items, ["place of marriage", "lugar de casamiento"])
    date_y = find_y_after(items, ["date of marriage", "fecha de casamiento"], place_y)
    solemnized_y = find_y_after(items, ["solemnized by", "marriage solemnized by"], date_y)

    value_min_x = max_x * 0.32
    value_max_x = max_x * 0.94

    place_raw = get_row_text(items, place_y, value_min_x, value_max_x, tolerance=20)
    date_raw = get_row_text(items, date_y, value_min_x, value_max_x, tolerance=20)
    solemnized_raw = get_row_text(items, solemnized_y, value_min_x, value_max_x, tolerance=22)

    all_text = full_ocr_text(items)

    place = place_raw
    date = date_raw
    solemnized_by = solemnized_raw

    if place == "Review needed":
        place = pick_regex(
            all_text,
            [
                r"(Nabulao\s+Catholic\s+Church)",
                r"Place of marriage\s+([A-Za-zñÑ0-9\s.'-]{2,90})\s+Date of",
            ],
        )

    if date == "Review needed":
        date = pick_regex(
            all_text,
            [
                r"([A-Za-z]+\s+\d{1,2},\s+\d{4})",
            ],
        )

    if solemnized_by == "Review needed":
        solemnized_by = pick_regex(
            all_text,
            [
                r"(Rev\.?\s*[A-Za-zñÑ\s.'-]{2,50})",
                r"Reverend\s+([A-Za-zñÑ\s.'-]{2,50})",
            ],
        )

    place = re.sub(
        r"\b(House|Office|Barrio|Church|Iglesia|Date|Fecha|of|de|e)\b",
        " ",
        str(place),
        flags=re.IGNORECASE,
    )
    place = re.sub(r"\s+", " ", place).strip(" .:-")

    if "Nabulao Catholic Church" in all_text and ("Review needed" in place or len(place) < 4):
        place = "Nabulao Catholic Church"

    date = clean_date_value(date)

    if solemnized_by != "Review needed":
        rev_match = re.search(r"(Rev\.?\s*[A-Za-zñÑ\s.'-]{2,50})", str(solemnized_by), flags=re.IGNORECASE)

        if rev_match:
            solemnized_by = rev_match.group(1).strip()

    return {
        "place_of_marriage": display_value(place),
        "date_of_marriage": display_value(date),
        "solemnized_by": display_value(solemnized_by),
    }


def build_structured_marriage_certificate(items):
    max_x = max(float(item.get("x_max", 0)) for item in items)
    regions = find_column_regions(items, max_x)
    rows = get_field_rows(items)

    husband_contracting_raw, wife_contracting_raw = get_clean_row_values(items, rows["contracting"], regions)
    husband_age_raw, wife_age_raw = get_clean_row_values(items, rows["age"], regions)
    husband_nationality_raw, wife_nationality_raw = get_clean_row_values(items, rows["nationality"], regions)
    husband_occupation_raw, wife_occupation_raw = get_clean_row_values(items, rows["occupation"], regions)
    husband_residence_raw, wife_residence_raw = get_clean_row_values(items, rows["residence"], regions)
    husband_civil_raw, wife_civil_raw = get_clean_row_values(items, rows["civil"], regions)
    husband_father_raw, wife_father_raw = get_clean_row_values(items, rows["father"], regions)
    husband_mother_raw, wife_mother_raw = get_clean_row_values(items, rows["mother"], regions)
    husband_witness_raw, wife_witness_raw = get_clean_row_values(items, rows["witness"], regions)

    husband_name_from_contracting, husband_age_from_contracting = split_name_from_age_row(husband_contracting_raw)
    wife_name_from_contracting, wife_age_from_contracting = split_name_from_age_row(wife_contracting_raw)

    husband_age = extract_age(husband_age_raw)

    if husband_age == "Review needed":
        husband_age = husband_age_from_contracting

    wife_age = extract_age(wife_age_raw)

    if wife_age == "Review needed":
        wife_age = wife_age_from_contracting

    city, province = extract_top_location(items, max_x)
    details = extract_marriage_detail_rows(items, max_x)

    husband = {
        "name": clean_person_name(husband_name_from_contracting),
        "age": display_value(husband_age),
        "nationality": extract_nationality(husband_nationality_raw, preferred="husband"),
        "occupation": extract_occupation(husband_occupation_raw),
        "residence": clean_residence(husband_residence_raw),
        "civil_status": extract_civil_status(husband_civil_raw),
        "father": clean_person_name(husband_father_raw),
        "mother": clean_person_name(husband_mother_raw),
        "witness": clean_person_name(husband_witness_raw),
    }

    wife = {
        "name": clean_person_name(wife_name_from_contracting),
        "age": display_value(wife_age),
        "nationality": extract_nationality(wife_nationality_raw, preferred="wife"),
        "occupation": extract_occupation(wife_occupation_raw),
        "residence": clean_residence(wife_residence_raw),
        "civil_status": extract_civil_status(wife_civil_raw),
        "father": clean_person_name(wife_father_raw),
        "mother": clean_person_name(wife_mother_raw),
        "witness": clean_person_name(wife_witness_raw),
    }

    if wife["civil_status"] == "Review needed" and re.search(r"\bSingle\b", wife_civil_raw, flags=re.IGNORECASE):
        wife["civil_status"] = "Single"

    return {
        "certificate_type": "marriage",
        "layout_type": "marriage_two_column_contract",
        "status": "machine_generated_review_required",
        "location": {
            "city_or_municipality": display_value(city),
            "province": display_value(province),
        },
        "husband": husband,
        "wife": wife,
        "marriage_details": {
            "place_of_marriage": display_value(details["place_of_marriage"]),
            "date_of_marriage": display_value(details["date_of_marriage"]),
            "solemnized_by": display_value(details["solemnized_by"]),
        },
        "debug": {
            "rows": rows,
            "regions": regions,
            "raw_values": {
                "husband_contracting_raw": husband_contracting_raw,
                "wife_contracting_raw": wife_contracting_raw,
                "husband_age_raw": husband_age_raw,
                "wife_age_raw": wife_age_raw,
                "husband_father_raw": husband_father_raw,
                "wife_father_raw": wife_father_raw,
                "husband_mother_raw": husband_mother_raw,
                "wife_mother_raw": wife_mother_raw,
                "husband_witness_raw": husband_witness_raw,
                "wife_witness_raw": wife_witness_raw,
            },
        },
    }


# =========================================================
# IMPROVED BIRTH EXTRACTOR
# =========================================================

def find_birth_child_name(items):
    value = find_nearby_row_value(
        items,
        [
            "name of child",
            "child's name",
            "name",
            "nombre",
        ],
        clean_name_value,
    )

    if value != "Review needed":
        return value

    return find_by_regex_full_text(
        items,
        [
            r"Name of Child\s*[:\-]?\s*([A-Za-zñÑ\s.'-]{4,80})",
            r"Child\s*[:\-]?\s*([A-Za-zñÑ\s.'-]{4,80})",
        ],
        clean_name_value,
    )


def find_birth_sex(items):
    value = find_nearby_row_value(
        items,
        [
            "sex",
            "sexo",
            "gender",
        ],
        clean_sex_value,
    )

    if value != "Review needed":
        return value

    text = full_ocr_text(items)

    if re.search(r"\bMale\b", text, flags=re.IGNORECASE):
        return "Male"

    if re.search(r"\bFemale\b", text, flags=re.IGNORECASE):
        return "Female"

    return "Review needed"


def find_birth_date(items):
    value = find_nearby_row_value(
        items,
        [
            "date of birth",
            "birth date",
            "date born",
            "born on",
            "date",
        ],
        clean_date_value,
    )

    if value != "Review needed":
        return value

    return find_by_regex_full_text(
        items,
        [
            r"Date of Birth\s*[:\-]?\s*([A-Za-z0-9\s,/-]{4,50})",
            r"Born\s*(?:on)?\s*[:\-]?\s*([A-Za-z0-9\s,/-]{4,50})",
            r"([A-Za-z]+\s+\d{1,2},\s+\d{4})",
            r"(\d{1,2}/\d{1,2}/\d{2,4})",
        ],
        clean_date_value,
    )


def find_birth_place(items):
    value = find_nearby_row_value(
        items,
        [
            "place of birth",
            "birthplace",
            "born at",
            "born in",
            "place",
        ],
        clean_place_value,
    )

    if value != "Review needed":
        return value

    return find_by_regex_full_text(
        items,
        [
            r"Place of Birth\s*[:\-]?\s*([A-Za-zñÑ0-9\s.,'/-]{4,100})",
            r"Born at\s*[:\-]?\s*([A-Za-zñÑ0-9\s.,'/-]{4,100})",
            r"Born in\s*[:\-]?\s*([A-Za-zñÑ0-9\s.,'/-]{4,100})",
        ],
        clean_place_value,
    )


def find_birth_parent(items, parent_type):
    if parent_type == "father":
        labels = [
            "name of father",
            "father's name",
            "father",
            "padre",
        ]
        patterns = [
            r"Name of Father\s*[:\-]?\s*([A-Za-zñÑ\s.'-]{4,80})",
            r"Father\s*[:\-]?\s*([A-Za-zñÑ\s.'-]{4,80})",
        ]
    else:
        labels = [
            "name of mother",
            "mother's name",
            "mother",
            "madre",
        ]
        patterns = [
            r"Name of Mother\s*[:\-]?\s*([A-Za-zñÑ\s.'-]{4,80})",
            r"Mother\s*[:\-]?\s*([A-Za-zñÑ\s.'-]{4,80})",
        ]

    value = find_nearby_row_value(items, labels, clean_name_value)

    if value != "Review needed":
        return value

    return find_by_regex_full_text(items, patterns, clean_name_value)


def build_structured_birth_certificate(items):
    child_name = find_birth_child_name(items)
    sex = find_birth_sex(items)
    date_of_birth = find_birth_date(items)
    place_of_birth = find_birth_place(items)
    father = find_birth_parent(items, "father")
    mother = find_birth_parent(items, "mother")
    registry_number = find_registry_number(items)

    remarks = find_nearby_row_value(
        items,
        [
            "remarks",
            "annotation",
            "notes",
        ],
        clean_extracted_value,
    )

    return {
        "certificate_type": "birth",
        "layout_type": "birth_structured_fallback_v2",
        "status": "machine_generated_review_required",
        "child": {
            "name": child_name,
            "sex": sex,
            "date_of_birth": date_of_birth,
            "place_of_birth": place_of_birth,
        },
        "parents": {
            "father": father,
            "mother": mother,
        },
        "registration": {
            "registry_number": registry_number,
            "remarks": remarks,
        },
        "raw_text_preview": [item.get("text", "") for item in items[:100]],
    }


# =========================================================
# IMPROVED DEATH EXTRACTOR
# =========================================================

def find_death_name(items):
    value = find_nearby_row_value(
        items,
        [
            "name of deceased",
            "deceased",
            "nombre del difunto",
            "difunto",
            "name",
        ],
        clean_name_value,
    )

    if value != "Review needed":
        return value

    return find_by_regex_full_text(
        items,
        [
            r"Name of Deceased\s*[:\-]?\s*([A-Za-zñÑ\s.'-]{4,90})",
            r"Deceased\s*[:\-]?\s*([A-Za-zñÑ\s.'-]{4,90})",
            r"Nombre del Difunto\s*[:\-]?\s*([A-Za-zñÑ\s.'-]{4,90})",
        ],
        clean_name_value,
    )


def find_death_age(items):
    value = find_nearby_row_value(
        items,
        [
            "age",
            "edad",
            "years",
            "años",
        ],
        clean_age_value,
    )

    if value != "Review needed":
        return value

    return find_by_regex_full_text(
        items,
        [
            r"Age\s*[:\-]?\s*(\d{1,3})",
            r"Edad\s*[:\-]?\s*(\d{1,3})",
            r"(\d{1,3})\s*(?:years|yrs|años)",
        ],
        clean_age_value,
    )


def find_death_sex(items):
    value = find_nearby_row_value(
        items,
        [
            "sex",
            "sexo",
            "gender",
        ],
        clean_sex_value,
    )

    if value != "Review needed":
        return value

    text = full_ocr_text(items)

    if re.search(r"\bMale\b", text, flags=re.IGNORECASE):
        return "Male"

    if re.search(r"\bFemale\b", text, flags=re.IGNORECASE):
        return "Female"

    return "Review needed"


def find_death_nationality(items):
    return find_nearby_row_value(
        items,
        [
            "nationality",
            "nacionalidad",
        ],
        clean_nationality_value,
    )


def find_death_occupation(items):
    value = find_nearby_row_value(
        items,
        [
            "occupation",
            "oficio",
            "profession",
        ],
        clean_extracted_value,
    )

    known_occupations = [
        "Farmer",
        "Laborer",
        "Housekeeper",
        "Housewife",
        "Teacher",
        "Merchant",
        "Student",
        "Driver",
        "Worker",
        "Carpenter",
        "Priest",
        "Retired",
    ]

    for occupation in known_occupations:
        if re.search(rf"\b{re.escape(occupation)}\b", str(value), flags=re.IGNORECASE):
            return occupation

    return value


def find_death_residence(items):
    return find_nearby_row_value(
        items,
        [
            "residence",
            "domicilio",
            "address",
            "resident of",
        ],
        clean_place_value,
    )


def find_death_date(items):
    value = find_nearby_row_value(
        items,
        [
            "date of death",
            "fecha de la def",
            "date died",
            "died on",
            "death date",
        ],
        clean_date_value,
    )

    if value != "Review needed":
        return value

    return find_by_regex_full_text(
        items,
        [
            r"Date of Death\s*[:\-]?\s*([A-Za-z0-9\s,/-]{4,50})",
            r"Fecha de la Def[a-zA-Z]*\s*[:\-]?\s*([A-Za-z0-9\s,/-]{4,50})",
            r"Died\s*(?:on)?\s*[:\-]?\s*([A-Za-z0-9\s,/-]{4,50})",
            r"([A-Za-z]+\s+\d{1,2},\s+\d{4})",
            r"(\d{1,2}/\d{1,2}/\d{2,4})",
        ],
        clean_date_value,
    )


def find_death_place(items):
    value = find_nearby_row_value(
        items,
        [
            "place of death",
            "lugar de la def",
            "died at",
            "died in",
            "place",
        ],
        clean_place_value,
    )

    if value != "Review needed":
        return value

    return find_by_regex_full_text(
        items,
        [
            r"Place of Death\s*[:\-]?\s*([A-Za-zñÑ0-9\s.,'/-]{4,100})",
            r"Lugar de la Def[a-zA-Z]*\s*[:\-]?\s*([A-Za-zñÑ0-9\s.,'/-]{4,100})",
            r"Died at\s*[:\-]?\s*([A-Za-zñÑ0-9\s.,'/-]{4,100})",
        ],
        clean_place_value,
    )


def find_death_cause_or_burial(items):
    value = find_nearby_row_value(
        items,
        [
            "cause of death",
            "cause",
            "burial",
            "cemetery",
            "interred",
            "permit issued for burial",
            "remains interred",
        ],
        clean_extracted_value,
    )

    if value != "Review needed":
        return value

    return find_by_regex_full_text(
        items,
        [
            r"Cause of Death\s*[:\-]?\s*([A-Za-zñÑ0-9\s.,'/-]{4,120})",
            r"Burial\s*[:\-]?\s*([A-Za-zñÑ0-9\s.,'/-]{4,120})",
            r"Cemetery\s*[:\-]?\s*([A-Za-zñÑ0-9\s.,'/-]{4,120})",
            r"Interred\s*[:\-]?\s*([A-Za-zñÑ0-9\s.,'/-]{4,120})",
        ],
        clean_extracted_value,
    )


def build_structured_death_certificate(items):
    deceased_name = find_death_name(items)
    age = find_death_age(items)
    sex = find_death_sex(items)
    nationality = find_death_nationality(items)
    occupation = find_death_occupation(items)
    residence = find_death_residence(items)
    date_of_death = find_death_date(items)
    place_of_death = find_death_place(items)
    cause_or_burial = find_death_cause_or_burial(items)
    registry_number = find_registry_number(items)

    remarks = find_nearby_row_value(
        items,
        [
            "remarks",
            "annotation",
            "notes",
        ],
        clean_extracted_value,
    )

    return {
        "certificate_type": "death",
        "layout_type": "death_structured_fallback_v2",
        "status": "machine_generated_review_required",
        "deceased": {
            "name": deceased_name,
            "age": age,
            "sex": sex,
            "nationality": nationality,
            "occupation": occupation,
            "residence": residence,
        },
        "death_details": {
            "date_of_death": date_of_death,
            "place_of_death": place_of_death,
            "cause_or_burial": cause_or_burial,
        },
        "registration": {
            "registry_number": registry_number,
            "remarks": remarks,
        },
        "raw_text_preview": [item.get("text", "") for item in items[:100]],
    }


def build_structured_unknown_certificate(items, cert_type):
    return {
        "certificate_type": cert_type,
        "layout_type": "unknown_fallback_template",
        "status": "fallback_review_required",
        "raw_text_preview": [item.get("text", "") for item in items[:100]],
    }


def build_structured_certificate(result):
    cert_type = result.get("certificate_type", "unknown")
    items = valid_ocr_items(result)

    if not items:
        return {
            "certificate_type": cert_type,
            "layout_type": "unknown",
            "status": "review_needed",
            "raw_text_preview": [],
        }

    if cert_type == "marriage":
        return build_structured_marriage_certificate(items)

    if cert_type == "birth":
        return build_structured_birth_certificate(items)

    if cert_type == "death":
        return build_structured_death_certificate(items)

    return build_structured_unknown_certificate(items, cert_type)


# =========================================================
# OCR RUNNER
# =========================================================

def run_ocr(image_path):
    engine = get_ocr_engine()
    result = engine.predict(str(image_path))

    if isinstance(result, list) and result:
        page = result[0]
    else:
        page = result

    temp_json = OUTPUT_DIR / f"{image_path.stem}_raw.json"

    if hasattr(page, "save_to_json"):
        page.save_to_json(str(temp_json))
        data = json.loads(temp_json.read_text(encoding="utf-8"))
    else:
        data = page

    texts = find_first_key(data, "rec_texts") or []
    scores = find_first_key(data, "rec_scores") or []
    boxes = (
        find_first_key(data, "rec_boxes")
        or find_first_key(data, "dt_polys")
        or find_first_key(data, "dt_boxes")
        or []
    )

    items = []

    for index, text in enumerate(texts):
        text = str(text).strip()

        if not text:
            continue

        score = scores[index] if index < len(scores) else 0
        box = boxes[index] if index < len(boxes) else None

        x_min, y_min, x_max, y_max, x_center, y_center = box_to_bounds(box)

        items.append(
            {
                "text": text,
                "confidence": float(score),
                "review_status": confidence_status(score),
                "x_min": x_min,
                "y_min": y_min,
                "x_max": x_max,
                "y_max": y_max,
                "x_center": x_center,
                "y_center": y_center,
            }
        )

    cert_type = classify_certificate([item["text"] for item in items])
    fields = extract_field_candidates(cert_type, items)

    return {
        "source_file": image_path.name,
        "certificate_type": cert_type,
        "ocr_text_count": len(items),
        "field_candidates": fields,
        "ocr_items": items,
    }


def save_result_csv(result, csv_path):
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "field_name",
                "field_value_candidate",
                "confidence",
                "review_status",
                "method",
                "label_text",
            ],
        )

        writer.writeheader()

        for row in result["field_candidates"]:
            writer.writerow(row)


# =========================================================
# ROUTES
# =========================================================

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@app.post("/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    saved_name = f"{uuid.uuid4().hex}{ext}"
    image_path = UPLOAD_DIR / saved_name

    image_path.write_bytes(await file.read())

    result = run_ocr(image_path)
    summary = build_certificate_summary(result)
    digital_certificate = build_digital_certificate(result)
    
    structured_certificate = clean_structured_certificate_for_display(
    build_structured_certificate(result)
    )

    output_json = OUTPUT_DIR / f"{image_path.stem}_result.json"
    output_csv = OUTPUT_DIR / f"{image_path.stem}_fields.csv"

    full_output = {
        "ocr_result": result,
        "summary": summary,
        "structured_certificate": structured_certificate,
    }

    output_json.write_text(json.dumps(full_output, indent=2, ensure_ascii=False), encoding="utf-8")
    save_result_csv(result, output_csv)

    return templates.TemplateResponse(
        request,
        "result.html",
        {
            "result": result,
            "summary": summary,
            "digital_certificate": digital_certificate,
            "structured_certificate": structured_certificate,
            "json_filename": output_json.name,
            "csv_filename": output_csv.name,
            "image_url": f"/uploads/{saved_name}",
        },
    )


@app.get("/download/{filename}")
def download_result(filename: str):
    file_path = OUTPUT_DIR / filename

    if not file_path.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)

    if file_path.suffix.lower() == ".csv":
        media_type = "text/csv"
    else:
        media_type = "application/json"

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type,
    )


@app.get("/health")
def health():
    return {"status": "ok"}