---

title: RCDOK Certificates Site Project
sdk: docker
app_port: 7860
pinned: false
-------------

# RCDOK Certificates Site Project

## Project Title

**OCR-Assisted Digitization Prototype for Historical Philippine Certificates**

## Project Overview

This project is a web-based OCR prototype designed to help digitize scanned historical Philippine certificate records, including birth, death, and marriage certificates.

The system allows a user to upload a scanned certificate image. The backend performs OCR, detects the certificate type, extracts structured fields where possible, and displays a digitalized certificate document for review.

This project is intended as an **OCR-assisted archival digitization tool**, not a fully automatic replacement for human verification. Historical certificates often contain faded text, handwritten entries, cursive handwriting, old formatting, and mixed English/Spanish labels. Because of this, uncertain or unreliable fields are marked as **Review needed**.

## Main Objective

The main objective of this project is to create a working prototype that can:

1. Accept scanned certificate images through a web interface.
2. Run OCR on uploaded certificate images.
3. Detect whether the uploaded file is a birth, death, or marriage certificate.
4. Extract structured certificate fields where possible.
5. Generate a reviewable digital certificate document.
6. Export OCR and structured extraction results as CSV, JSON, and PDF.
7. Provide a baseline for further OCR and field-extraction improvement.

## Supported Certificate Types

The current prototype supports:

* Birth certificates
* Death certificates
* Marriage certificates

The strongest current extraction support is for clearer marriage certificates, especially those following a two-column contract format.

Birth and death certificates are supported, but their extraction quality is more limited because many samples contain faded scans and cursive handwritten values.

## Current Features

* Web upload interface
* FastAPI backend
* PaddleOCR integration
* OCR text recognition
* OCR bounding box extraction
* Certificate type detection
* Layout-aware extraction for marriage certificates
* Basic structured fallback extraction for birth and death certificates
* Digitalized certificate document display
* Uploaded certificate image preview
* JSON export
* CSV export
* PDF export through browser print/download
* Hugging Face Spaces deployment using Docker
* OCR warmup and health-check endpoints
* Human-review marking for uncertain fields

## Project Workflow

```text
Certificate image upload
        ↓
PaddleOCR detection and recognition
        ↓
OCR text, confidence scores, and bounding boxes
        ↓
Certificate type detection
        ↓
Structured field extraction
        ↓
Digital certificate reconstruction
        ↓
CSV / JSON / PDF output
        ↓
Human review
```

## Technology Stack

| Component         | Technology                      |
| ----------------- | ------------------------------- |
| Backend framework | FastAPI                         |
| OCR engine        | PaddleOCR                       |
| OCR runtime       | PaddlePaddle                    |
| Frontend          | HTML, CSS, JavaScript           |
| Template engine   | Jinja2                          |
| Data output       | CSV, JSON, PDF                  |
| Language          | Python                          |
| Server            | Uvicorn                         |
| Deployment        | Hugging Face Spaces with Docker |

## Folder Structure

```text
RCDOK-CertificatesSiteProject/
├── app/
│   ├── main.py
│   ├── static/
│   │   ├── styles.css
│   │   └── app.js
│   └── templates/
│       ├── index.html
│       └── result.html
├── docs/
│   ├── 08_BACKEND_EXTRACTION_EVALUATION.md
│   ├── 09_FINAL_PROJECT_STATUS.md
│   └── 10_HANDOVER_NOTES.md
├── outputs/
│   ├── sample_ocr/
│   ├── backend_evaluation/
│   └── web_demo/
├── samples/
│   ├── birth/
│   ├── death/
│   └── marriage/
├── scripts/
│   ├── run_sample_ocr.py
│   ├── build_ocr_review_report.py
│   ├── build_ocr_items_with_boxes.py
│   └── evaluate_backend_extraction.py
├── uploads/
├── Dockerfile
├── requirements.txt
└── README.md
```

## Local Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/str1ker577/RCDOK-CertificatesSiteProject.git
cd RCDOK-CertificatesSiteProject
```

### 2. Create and activate a virtual environment

For Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

For macOS or Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the web application locally

```bash
uvicorn app.main:app --reload
```

Open the application in a browser:

```text
http://127.0.0.1:8000
```

## Hugging Face Deployment

The project is deployed through Hugging Face Spaces using Docker.

Live demo site:

```text
https://huggingface.co/spaces/str1ker577/RCDOK-CertificatesSiteProject
```

Important endpoints:

```text
/health
/warmup
/warmup-status
```

Recommended hosted workflow:

1. Open the Hugging Face Space.
2. Visit `/health` to confirm that the service is active.
3. Visit `/warmup` to initialize PaddleOCR.
4. Check `/warmup-status` until the status is `ready`.
5. Upload a certificate image through the main page.

## Render Deployment Note

Render was tested as an initial deployment option. The frontend loaded successfully, but PaddleOCR exceeded Render's free-tier memory limit during backend processing. Because of this, the project was moved to Hugging Face Spaces, which provides more suitable free CPU memory for this OCR prototype.

## Current Project Status

The main workflow is operational:

* Certificate upload works.
* OCR processing works.
* Certificate type detection works.
* Structured output generation works.
* JSON, CSV, and PDF exports are available.
* The application is deployed through Hugging Face Spaces.

The project should be treated as a **working baseline prototype**. It is not yet production-ready.

## Current Extraction Quality

The strongest results are seen in clearer marriage certificates, especially printed or typewritten documents with consistent two-column formatting.

Birth and death certificates are more difficult because many samples contain:

* Faded text
* Cursive handwriting
* Handwritten values mixed with printed labels
* Old document layouts
* English and Spanish labels
* Uneven scan quality

Because of these limitations, some fields are marked as **Review needed** instead of displaying unreliable extracted values.

## Known Limitations

1. The system works best on clear printed or typewritten certificates.
2. Cursive handwriting remains difficult for PaddleOCR.
3. Birth and death certificates generally produce weaker structured extraction results than marriage certificates.
4. Some handwritten names, dates, and places may be missed or incorrectly recognized.
5. OCR confidence does not always guarantee that a field value is semantically correct.
6. Human review is required before using exported certificate records.
7. Hosted OCR processing may take time because PaddleOCR is loaded and executed on CPU.
8. The current system is not yet suitable for production or official archival use without further validation.

## Recommended Future Improvements

Recommended next development tasks include:

1. Add editable extracted fields before export.
2. Improve image preprocessing, including contrast enhancement, sharpening, resizing, and deskewing.
3. Add stricter validation for names, dates, ages, sex, nationality, and locations.
4. Expand the sample dataset for birth, death, and marriage certificates.
5. Perform a larger evaluation using more representative historical records.
6. Improve layout detection for birth and death certificates.
7. Explore handwriting-specific OCR models for cursive handwritten entries.
8. Add confidence-based warnings and document reliability labels.
9. Add better loading indicators and error messages in the frontend.
10. Improve CSV and JSON formatting for downstream archival use.

## Demo Materials

Demo site:

```text
https://huggingface.co/spaces/str1ker577/RCDOK-CertificatesSiteProject
```

Demo video:

```text
https://drive.google.com/file/d/1R4UzDlstdKVyC9JNAdCdTycsh1XM-Xxz/view?usp=sharing
```

GitHub repository:

```text
https://github.com/str1ker577/RCDOK-CertificatesSiteProject
```

## Final Notes

This project successfully establishes a functional baseline for OCR-assisted certificate digitization. The system demonstrates the complete workflow from upload to OCR processing, structured reconstruction, and export.

Further tuning is still required, especially for cursive handwritten records and degraded birth and death certificates. The current version is best viewed as a foundation for continued improvement rather than a finished production system.
