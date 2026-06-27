from pathlib import Path
import csv
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OCR_DIR = PROJECT_ROOT / "outputs" / "sample_ocr"
OUTPUT_CSV = OCR_DIR / "all_ocr_items_with_boxes.csv"


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

    points = []

    if isinstance(box, list):
        if all(isinstance(x, (int, float)) for x in box) and len(box) >= 4:
            x1, y1, x2, y2 = box[:4]
            return x1, y1, x2, y2, (x1 + x2) / 2, (y1 + y2) / 2

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


def get_certificate_type(path):
    parts = path.parts

    for cert_type in ["birth", "death", "marriage"]:
        if cert_type in parts:
            return cert_type

    return "unknown"


def get_source_file(path):
    folder_name = path.parent.name

    if folder_name.startswith("Screenshot"):
        return folder_name + ".png"

    return folder_name


def main():
    rows = []

    json_files = sorted(OCR_DIR.glob("*/*/raw_ocr.json"))

    if not json_files:
        print("No raw OCR JSON files found.")
        return

    for json_path in json_files:
        cert_type = get_certificate_type(json_path)
        source_file = get_source_file(json_path)

        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Could not read {json_path}: {e}")
            continue

        texts = find_first_key(data, "rec_texts") or []
        scores = find_first_key(data, "rec_scores") or []

        boxes = (
            find_first_key(data, "rec_boxes")
            or find_first_key(data, "dt_polys")
            or find_first_key(data, "dt_boxes")
            or find_first_key(data, "boxes")
            or []
        )

        for index, text in enumerate(texts):
            score = scores[index] if isinstance(scores, list) and index < len(scores) else ""
            box = boxes[index] if isinstance(boxes, list) and index < len(boxes) else ""

            x_min, y_min, x_max, y_max, x_center, y_center = box_to_bounds(box)

            rows.append(
                {
                    "certificate_type": cert_type,
                    "source_file": source_file,
                    "item_index": index,
                    "text": str(text).strip(),
                    "confidence": score,
                    "x_min": x_min,
                    "y_min": y_min,
                    "x_max": x_max,
                    "y_max": y_max,
                    "x_center": x_center,
                    "y_center": y_center,
                    "raw_json": str(json_path.relative_to(PROJECT_ROOT)),
                }
            )

    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "certificate_type",
            "source_file",
            "item_index",
            "text",
            "confidence",
            "x_min",
            "y_min",
            "x_max",
            "y_max",
            "x_center",
            "y_center",
            "raw_json",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("OCR items with boxes complete.")
    print(f"Rows: {len(rows)}")
    print(f"Saved to: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()