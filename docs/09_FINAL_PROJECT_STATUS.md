# Final Project Status

## Project Name

**RCDOK Certificates Site Project**

## Project Title

**OCR-Assisted Digitization Prototype for Historical Philippine Certificates**

## Final Status Summary

The project has reached a working baseline prototype stage.

The system can upload scanned certificate images, run OCR, detect the certificate type, generate a structured digital certificate output, and export the results as JSON, CSV, and PDF.

The application is also deployed through Hugging Face Spaces using Docker. The hosted version is operational, although OCR processing may take time because PaddleOCR runs on CPU.

## Current Completion Status

The project is not yet a fully production-ready system, but the main end-to-end workflow is complete and functional.

Estimated completion status:

```text
Overall prototype completion: around 80% to 85%
```

Breakdown:

```text
Web upload workflow: Complete
OCR integration: Complete
Certificate type detection: Working baseline
Marriage certificate extraction: Strongest current support
Birth certificate extraction: Basic support, needs further tuning
Death certificate extraction: Basic support, needs further tuning
Export features: Working
Deployment: Working through Hugging Face Spaces
Documentation: Prepared for handover
```

## What Has Been Completed

The following parts have been completed:

1. FastAPI backend setup.
2. Web upload interface.
3. PaddleOCR integration.
4. Certificate type detection for birth, death, and marriage certificates.
5. Structured digital certificate display.
6. Uploaded certificate preview.
7. CSV export.
8. JSON export.
9. PDF export through browser print/download.
10. Hugging Face Spaces deployment using Docker.
11. OCR warmup endpoint.
12. Health-check endpoint.
13. Basic project documentation.
14. Handover notes.

## Deployment Summary

The project was first tested using Render. The frontend loaded successfully, but the backend OCR process exceeded Render's free-tier memory limit.

The project was then deployed through Hugging Face Spaces using Docker. This deployment is currently more suitable for the project because the free CPU environment provides more memory for PaddleOCR.

## Current Performance Observations

The prototype performs best on clearer printed or typewritten certificates.

Marriage certificates currently produce the strongest results, especially when they follow a clear two-column format.

Birth and death certificates are more difficult because many samples contain faded scans, cursive handwriting, and handwritten values mixed with printed labels.

Because of this, some fields are marked as **Review needed** instead of being filled with unreliable values.

## Main Limitation

The main limitation is cursive handwriting recognition.

PaddleOCR is able to detect many printed labels and clearer text, but it struggles with cursive handwritten entries in older birth and death certificates. This affects names, dates, places, causes of death, and other handwritten field values.

This limitation is related to the OCR model and the quality of the source documents, not only the web application logic.

## Current System Position

The current system should be considered a:

```text
Machine-assisted OCR baseline prototype
```

It should not be treated as a fully automatic official archival system yet.

Human review is still required before using exported certificate records.

## Recommended Next Steps

Recommended improvements for the next development phase:

1. Add editable extracted fields before export.
2. Improve image preprocessing before OCR.
3. Add stricter validation for field values.
4. Improve layout rules for birth and death certificates.
5. Expand the sample dataset.
6. Test more certificate variations.
7. Add confidence and reliability labels for each uploaded document.
8. Explore handwriting-specific OCR models for cursive entries.
9. Improve loading indicators and frontend error messages.
10. Continue evaluating extraction quality using additional samples.

## Final Note

The project successfully demonstrates the full certificate digitization workflow from upload to OCR, structured reconstruction, and export.

The current version provides a strong foundation for future development, with further tuning needed mainly for cursive handwriting, degraded scans, and more complex birth and death certificate layouts.
