# Project Handover Notes

## Project Name

**RCDOK Certificates Site Project**

## Project Title

**OCR-Assisted Digitization Prototype for Historical Philippine Certificates**

## Handover Purpose

This document summarizes the current status of the project, what has already been completed, what is currently working, known limitations, and recommended next steps for future development.

The project is being handed over as a working baseline prototype. It is not yet a fully production-ready certificate digitization system.

## Current Project Status

The project currently has a working web-based prototype that can:

1. Accept uploaded certificate images.
2. Run OCR using PaddleOCR.
3. Detect the certificate type.
4. Generate an organized digital certificate output.
5. Export results as JSON, CSV, and PDF.
6. Run locally through FastAPI.
7. Run online through Hugging Face Spaces using Docker.

The main workflow is already operational from upload to result generation.

## Deployment Status

The project was first tested on Render. The frontend was able to load successfully, but the backend OCR processing exceeded Render's free-tier memory limit because PaddleOCR requires more RAM during inference.

The project was then moved to Hugging Face Spaces using Docker. Hugging Face Spaces currently supports the frontend and backend workflow more reliably because it provides more suitable free CPU memory for this OCR prototype.

## Live Links

Demo site:

```text
https://huggingface.co/spaces/str1ker577/RCDOK-CertificatesSiteProject
```

Demo video:

```text
https://drive.google.com/file/d/1R4UzDlstdKVyC9JNAdCdTycsh1XM-Xxz/view?usp=sharing
```

## Main Files and Folders

```text
app/main.py
```

Contains the FastAPI backend, OCR initialization, upload route, certificate type detection, field extraction logic, export generation, health check, and OCR warmup endpoints.

```text
app/templates/index.html
```

Main upload page.

```text
app/templates/result.html
```

Result page showing the uploaded certificate, extracted fields, digital certificate view, and export buttons.

```text
app/static/styles.css
```

Frontend styling for the upload page, result page, certificate layout, and print/PDF formatting.

```text
app/static/app.js
```

Frontend upload behavior, file selection display, and processing state.

```text
requirements.txt
```

Python dependencies.

```text
Dockerfile
```

Docker configuration used by Hugging Face Spaces.

```text
README.md
```

Main project overview, setup instructions, deployment notes, features, and limitations.

```text
docs/
```

Contains project documentation, evaluation notes, final status, and handover information.

```text
samples/
```

Contains sample certificate images used for testing.

```text
outputs/
```

Contains generated output files, OCR results, and evaluation outputs.

```text
uploads/
```

Temporary upload folder used by the web application.

## How to Run Locally

From the project root:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000
```

## Hugging Face Deployment Notes

The Hugging Face Space uses Docker.

Important endpoints:

```text
/health
/warmup
/warmup-status
```

Recommended use:

1. Open the Space.
2. Visit `/health` to confirm the service is running.
3. Visit `/warmup` to initialize PaddleOCR.
4. Visit `/warmup-status` until the OCR status is `ready`.
5. Return to the main page and upload a certificate.

## What Works

The following features are working:

1. Certificate image upload.
2. OCR text extraction using PaddleOCR.
3. Certificate type detection for birth, death, and marriage certificates.
4. Structured digital output display.
5. Uploaded image preview.
6. JSON export.
7. CSV export.
8. PDF export through browser print/download.
9. Hugging Face deployment.
10. OCR warmup and health-check routes.

## Current OCR and Extraction Performance

The prototype performs best on clearer printed or typewritten certificates.

Marriage certificates currently produce the strongest results, especially when the document follows a clearer two-column layout.

Birth and death certificates are more challenging because many of the available samples contain cursive handwriting, faded scans, old formatting, and handwritten values mixed with printed labels.

## Known Limitations

1. Cursive handwriting is still difficult for PaddleOCR to recognize accurately.
2. Birth and death certificate extraction is weaker than marriage certificate extraction.
3. Some handwritten names, places, and dates may be missed or incorrectly recognized.
4. OCR confidence scores do not always guarantee that the extracted value belongs to the correct field.
5. Some fields are intentionally marked as `Review needed` to avoid displaying unreliable data.
6. Human review is still required before using exported records.
7. Hosted processing may take time because OCR runs on CPU.
8. The project is not yet suitable for official or production archival use without further validation.

## Recommended Next Improvements

The next developer should focus on the following:

1. Add editable extracted fields before export.
2. Improve image preprocessing before OCR.
3. Add stricter validation for names, dates, age, sex, nationality, and places.
4. Improve birth and death certificate layout extraction.
5. Expand the dataset with more representative public certificate samples.
6. Add a handwriting-specific OCR model for cursive entries.
7. Add better loading indicators and user-friendly error messages.
8. Add document reliability labels such as printed, mixed handwriting, or handwriting-heavy.
9. Improve CSV and JSON formats for easier archival use.
10. Add more systematic evaluation of extraction accuracy.

## Suggested Future OCR Direction

For future work, the project may benefit from a second OCR path specifically for handwritten or cursive text. PaddleOCR works well for printed labels, but cursive handwriting may require models such as TrOCR or another handwriting-recognition model.

This should be treated as a future enhancement because it requires additional labeled samples, cropped handwritten fields, training or fine-tuning, and separate evaluation.

## Final Handover Summary

The project successfully establishes a working baseline for OCR-assisted certificate digitization. It demonstrates the full workflow from image upload to OCR processing, certificate type detection, structured output generation, and file export.

The main limitation is not the web workflow itself, but the difficulty of accurately recognizing cursive handwriting in older birth and death certificates.

The project is ready for handover as a functional prototype and foundation for continued improvement.
