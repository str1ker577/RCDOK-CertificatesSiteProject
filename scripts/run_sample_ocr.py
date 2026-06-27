from pathlib import Path
import csv
import json
import time

import os

os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_use_onednn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

from paddleocr import PaddleOCR


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = PROJECT_ROOT / "samples"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "sample_ocr"

CERTIFICATE_TYPES = ["birth", "death", "marriage"]
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".pdf"}


def create_ocr_engine():
    try:
        return PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    except TypeError:
        return PaddleOCR(
            lang="en",
            use_angle_cls=False,
        )


def find_sample_files():
    files = []

    for cert_type in CERTIFICATE_TYPES:
        cert_dir = SAMPLES_DIR / cert_type

        if not cert_dir.exists():
            print(f"Missing folder: {cert_dir}")
            continue

        for path in sorted(cert_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append((cert_type, path))

    return files


def save_raw_result(result, json_path):
    json_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if hasattr(result, "save_to_json"):
            result.save_to_json(str(json_path))
            return
    except Exception:
        pass

    try:
        data = result.json if hasattr(result, "json") else result
        json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        json_path.write_text(str(result), encoding="utf-8")


def load_json_if_possible(json_path):
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return None


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


def extract_text_items_from_json(data):
    texts = find_first_key(data, "rec_texts") or []
    scores = find_first_key(data, "rec_scores") or []

    items = []

    if isinstance(texts, list):
        for index, text in enumerate(texts):
            score = None

            if isinstance(scores, list) and index < len(scores):
                score = scores[index]

            items.append(
                {
                    "text": str(text).strip(),
                    "confidence": score,
                }
            )

    return items


def extract_text_items_legacy(result):
    items = []

    try:
        pages = result if isinstance(result, list) else [result]

        for page in pages:
            if not page:
                continue

            for line in page:
                if not isinstance(line, (list, tuple)) or len(line) < 2:
                    continue

                text_part = line[1]

                if isinstance(text_part, (list, tuple)) and len(text_part) >= 2:
                    text = str(text_part[0]).strip()
                    score = text_part[1]
                    items.append({"text": text, "confidence": score})
    except Exception:
        pass

    return items


def run_prediction(ocr, image_path):
    if hasattr(ocr, "predict"):
        return ocr.predict(str(image_path))

    return ocr.ocr(str(image_path), cls=True)


def confidence_bucket(score):
    if score is None:
        return "unknown"

    try:
        score = float(score)
    except Exception:
        return "unknown"

    if score >= 0.85:
        return "high"
    if score >= 0.65:
        return "medium"
    return "low"


def main():
    sample_files = find_sample_files()

    if not sample_files:
        print("No sample files found.")
        print(f"Expected folders under: {SAMPLES_DIR}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Found {len(sample_files)} sample files.")
    print("Initializing PaddleOCR...")
    ocr = create_ocr_engine()
    print("PaddleOCR initialized.")
    print()

    summary_rows = []
    start_all = time.time()

    for index, (cert_type, image_path) in enumerate(sample_files, start=1):
        relative_name = image_path.stem
        cert_output_dir = OUTPUT_DIR / cert_type / relative_name
        cert_output_dir.mkdir(parents=True, exist_ok=True)

        json_path = cert_output_dir / "raw_ocr.json"
        txt_path = cert_output_dir / "raw_ocr.txt"
        csv_path = cert_output_dir / "raw_ocr_items.csv"

        print(f"[{index}/{len(sample_files)}] OCR: {cert_type} / {image_path.name}")
        start_one = time.time()

        try:
            result = run_prediction(ocr, image_path)

            if isinstance(result, list):
                for page_index, page_result in enumerate(result):
                    page_json_path = cert_output_dir / f"raw_ocr_page_{page_index + 1}.json"
                    save_raw_result(page_result, page_json_path)

                if len(result) == 1:
                    save_raw_result(result[0], json_path)
                else:
                    json_path.write_text(
                        json.dumps(
                            {
                                "source_file": str(image_path),
                                "pages": [f"raw_ocr_page_{i + 1}.json" for i in range(len(result))],
                            },
                            indent=2,
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
            else:
                save_raw_result(result, json_path)

            data = load_json_if_possible(json_path)
            items = extract_text_items_from_json(data) if data is not None else []

            if not items:
                items = extract_text_items_legacy(result)

            clean_items = [item for item in items if item["text"]]

            txt_lines = []
            for item in clean_items:
                score = item.get("confidence")
                bucket = confidence_bucket(score)
                txt_lines.append(f"[{bucket}] {score} | {item['text']}")

            txt_path.write_text("\n".join(txt_lines), encoding="utf-8")

            with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=["certificate_type", "source_file", "text", "confidence", "bucket"])
                writer.writeheader()

                for item in clean_items:
                    writer.writerow(
                        {
                            "certificate_type": cert_type,
                            "source_file": image_path.name,
                            "text": item["text"],
                            "confidence": item.get("confidence"),
                            "bucket": confidence_bucket(item.get("confidence")),
                        }
                    )

            elapsed = round(time.time() - start_one, 2)

            summary_rows.append(
                {
                    "certificate_type": cert_type,
                    "source_file": image_path.name,
                    "text_items_detected": len(clean_items),
                    "output_folder": str(cert_output_dir.relative_to(PROJECT_ROOT)),
                    "status": "success",
                    "seconds": elapsed,
                }
            )

            print(f"  Done. Text items: {len(clean_items)}. Time: {elapsed}s")

        except Exception as e:
            elapsed = round(time.time() - start_one, 2)

            error_path = cert_output_dir / "error.txt"
            error_path.write_text(str(e), encoding="utf-8")

            summary_rows.append(
                {
                    "certificate_type": cert_type,
                    "source_file": image_path.name,
                    "text_items_detected": 0,
                    "output_folder": str(cert_output_dir.relative_to(PROJECT_ROOT)),
                    "status": f"error: {e}",
                    "seconds": elapsed,
                }
            )

            print(f"  ERROR: {e}")

    summary_path = OUTPUT_DIR / "ocr_summary.csv"

    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "certificate_type",
                "source_file",
                "text_items_detected",
                "output_folder",
                "status",
                "seconds",
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    total_elapsed = round(time.time() - start_all, 2)

    print()
    print("OCR batch complete.")
    print(f"Total files processed: {len(summary_rows)}")
    print(f"Summary saved to: {summary_path}")
    print(f"Total time: {total_elapsed}s")


if __name__ == "__main__":
    main()