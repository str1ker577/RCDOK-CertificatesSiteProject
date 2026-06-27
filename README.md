---
title: RCDOK Certificates Site Project
sdk: docker
app_port: 7860
pinned: false
---

# RCDOK Certificates Site Project

## Project Title

**OCR-Assisted Digitization Prototype for Historical Philippine Certificates**

## Project Overview

This project is a web-based OCR prototype designed to help digitize scanned historical Philippine certificate records, including birth, death, and marriage certificates.

The system allows a user to upload a scanned certificate image. The backend then performs OCR, detects the certificate type, extracts structured fields where possible, and displays a digitalized certificate document for review.

The project is intended as an **OCR-assisted archival digitization tool**, not a fully automatic replacement for human verification. Historical certificates often contain faded text, handwritten entries, cursive handwriting, old formatting, and mixed English/Spanish labels. Because of this, uncertain fields are marked for human review.

## Main Objective

The main objective of this project is to create a prototype that can:

1. Accept scanned certificate images through a web interface.
2. Run OCR on uploaded certificate images.
3. Detect the certificate type.
4. Extract structured certificate fields.
5. Generate a reviewable digital certificate document.
6. Export OCR and structured extraction results as CSV and JSON.
7. Provide backend evaluation results for the collected sample certificates.

## Supported Certificate Types

The current prototype supports:

- Birth certificates
- Death certificates
- Marriage certificates

The strongest current extraction support is for the **marriage two-column contract format**, which is treated as the main layout-aware demo case.

Birth and death certificates currently use basic structured fallback extraction.

## Current Features

- Web upload interface
- FastAPI backend
- PaddleOCR integration
- OCR text recognition
- OCR bounding box extraction
- Certificate type detection
- Layout-aware extraction for marriage certificates
- Basic fallback extraction for birth and death certificates
- Digitalized certificate document display
- Uploaded certificate preview
- CSV export
- JSON export
- Backend extraction evaluation script
- Field-quality scoring
- Markdown backend evaluation report generation

## Project Workflow

The system follows this workflow:

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
CSV / JSON output
        ↓
Human review

Technology Stack
| Component         | Technology            |
| ----------------- | --------------------- |
| Backend framework | FastAPI               |
| OCR engine        | PaddleOCR             |
| OCR runtime       | PaddlePaddle          |
| Frontend          | HTML, CSS, JavaScript |
| Template engine   | Jinja2                |
| Data output       | CSV, JSON             |
| Language          | Python                |
| Server            | Uvicorn               |

Folder Structure
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
├── requirements.txt
└── README.md

Setup Instructions
1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

2. Install dependencies
pip install -r requirements.txt

3. Run the web application
uvicorn app.main:app --reload

Open the application in a browser:
http://127.0.0.1:8000