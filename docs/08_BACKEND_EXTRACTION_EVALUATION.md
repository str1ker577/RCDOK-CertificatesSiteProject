# Backend Extraction Evaluation

## Purpose

This report summarizes backend structured extraction results for the collected certificate samples. The system uses OCR text, OCR confidence scores, and bounding box coordinates to produce structured, reviewable digital certificate data.

This version includes a field-quality check so that label-only, noisy, or weak OCR fragments are not automatically counted as successful extraction.

## Overall Summary

| Metric | Value |
|---|---:|
| Files evaluated | 81 |
| OCR text items processed | 7453 |
| Total key fields checked | 1224 |
| Useful structured fields | 624 |
| Questionable structured fields | 152 |
| Review-needed fields | 448 |
| Useful extraction rate | 50.98% |

## Summary by Certificate Type

| Certificate Type | Files | OCR Items | Key Fields | Useful | Questionable | Review Needed | Useful Rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| birth | 17 | 913 | 136 | 21 | 8 | 107 | 15.44% |
| death | 32 | 2547 | 352 | 161 | 99 | 92 | 45.74% |
| marriage | 32 | 3993 | 736 | 442 | 45 | 249 | 60.05% |

## Quality Categories

- `useful`: The value appears usable as a structured field.
- `questionable`: The value is present but may be noisy, label-only, incomplete, or suspicious.
- `review_needed`: The field was missing or explicitly marked for human review.

## Current Backend Capabilities

- Detects certificate type as birth, death, marriage, or unknown.
- Performs layout-aware structured extraction for the marriage two-column contract format.
- Provides basic structured fallback extraction for birth and death certificates.
- Preserves raw OCR text for review and auditing.
- Marks missing or uncertain values as `Review needed` instead of inventing values.
- Evaluates extracted fields using quality rules to avoid overcounting weak OCR fragments.

## Current Limitations

- Extraction quality depends heavily on OCR quality and scan clarity.
- Handwritten and cursive portions may not be reliably transcribed.
- Birth and death templates currently use basic fallback extraction.
- Multiple historical certificate formats require additional layout-specific extractors.
- Field-quality rules are heuristic and should be manually reviewed during validation.

## Generated Files

- `outputs\backend_evaluation\backend_extraction_summary.csv`
- `outputs\backend_evaluation\backend_field_quality_summary.csv`
- `outputs\backend_evaluation\backend_extraction_details.json`

# Backend Extraction Evaluation

## Purpose

This document summarizes the backend structured extraction evaluation for the collected certificate samples.

The backend evaluation was created to measure how well the system can convert OCR results into structured certificate fields. The evaluation does not only count whether text was extracted. It also applies quality checks to determine whether extracted values appear useful, questionable, or still require review.

This is important because historical certificate OCR can produce incomplete, noisy, or label-only fragments. The system should not overclaim accuracy. Instead, uncertain fields are marked for human review.

## Evaluation Input

The evaluation uses OCR items generated from the collected certificate samples.

Input file:

```text
outputs/sample_ocr/all_ocr_items_with_boxes.csv

Overall Summary
| Metric                         |  Value |
| ------------------------------ | -----: |
| Files evaluated                |     81 |
| OCR text items processed       |  7,453 |
| Total key fields checked       |  1,224 |
| Useful structured fields       |    624 |
| Questionable structured fields |    152 |
| Review-needed fields           |    448 |
| Useful extraction rate         | 50.98% |

Summary By Certificate Type
| Certificate Type | Files | OCR Items | Key Fields | Useful | Questionable | Review Needed | Useful Rate |
| ---------------- | ----: | --------: | ---------: | -----: | -----------: | ------------: | ----------: |
| Birth            |    17 |       913 |        136 |     21 |            8 |           107 |      15.44% |
| Death            |    32 |     2,547 |        352 |    161 |           99 |            92 |      45.74% |
| Marriage         |    32 |     3,993 |        736 |    442 |           45 |           249 |      60.05% |


