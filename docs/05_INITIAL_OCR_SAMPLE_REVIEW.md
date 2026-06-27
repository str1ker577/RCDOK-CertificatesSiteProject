# Initial OCR Sample Review

## Purpose

This document summarizes the first OCR batch test for the certificate digitization project.

## OCR Scope

The current MVP focuses on printed and typed certificate text. Handwritten or cursive text will be treated as review-needed unless OCR confidence is clearly acceptable.

## Batch Summary

- Total OCR text items detected: 7453
- Total files processed: 81

## Results by Certificate Type

| Certificate Type | Files | OCR Text Items | Average Items Per File |
|---|---:|---:|---:|
| birth | 17 | 913 | 53.71 |
| death | 32 | 2547 | 79.59 |
| marriage | 32 | 3993 | 124.78 |

## Early Interpretation

- PaddleOCR successfully processed all available sample certificate images after disabling the problematic PaddlePaddle PIR/oneDNN runtime path.
- Marriage certificates produced the most OCR text items on average, suggesting they may contain denser layouts or more printed fields.
- Birth certificates produced fewer OCR text items, suggesting simpler layouts or fewer visible fields.
- Death certificates produced a moderate number of OCR text items and appear suitable for structured field extraction testing.

## MVP Decision

The project should proceed as a certificate digitization assistant, not a fully automatic cursive handwriting translator.

The system will:

- extract printed and typed text automatically;
- attempt to read handwritten text when possible;
- mark low-confidence or cursive fields for human review;
- export structured CSV/JSON/TXT outputs.

## Generated Output Files

- `outputs\sample_ocr\all_ocr_items.csv`
- `outputs\sample_ocr\keyword_hits_by_file.csv`
- `outputs\sample_ocr\ocr_summary.csv`

## Next Step

Build the first field extraction rules for repeated labels in birth, death, and marriage certificates.
