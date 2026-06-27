# Progress Update: Certificate OCR Project

## Current Status

The certificate OCR project has progressed from setup to working OCR batch processing.

The repository now contains a working sample-processing pipeline for Philippine birth, death, and marriage certificates.

## Completed Work

- Created the initial project folder structure.
- Added sample folders for birth, death, and marriage certificates.
- Installed and tested PaddleOCR locally.
- Fixed a PaddlePaddle Windows runtime issue by disabling the problematic PIR/oneDNN path.
- Processed 81 certificate images successfully.
- Generated raw OCR text outputs.
- Generated OCR summary reports.
- Extracted OCR text box coordinates.
- Built first-pass field extraction.
- Built position-aware field extraction using OCR bounding boxes.

## OCR Batch Summary

| Certificate Type | Files Processed | OCR Text Items |
|---|---:|---:|
| Birth | 17 | 919 |
| Death | 32 | 2,550 |
| Marriage | 32 | 4,030 |
| **Total** | **81** | **7,499** |

## Current Technical Pipeline

```text
certificate image
→ PaddleOCR detection and recognition
→ raw OCR text output
→ OCR confidence scores
→ OCR bounding box coordinates
→ first-pass field extraction
→ position-aware field extraction
→ CSV/JSON output for review