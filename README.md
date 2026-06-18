# Uttarakhand GK MCQ Practice App

This folder now contains a browser-based practice app for the 7 BS Negi PDF units and the Kanishta Sahayak paper pattern.

## Run the App

Open `index.html` in a browser, or start a simple local server:

```powershell
python -m http.server 8000
```

Then visit `http://localhost:8000`.

## Features

- 7 unit selector.
- 10-question practice set for a selected unit.
- All-units mode with 10 questions from each unit.
- English, Hindi, or bilingual display.
- 4 options per question.
- Marking: `+1` correct, `-0.25` wrong, `0` unattempted.
- Score history in browser storage.
- Analytics for attempts, average score, best score, accuracy, and unit-wise performance.
- JSON import for new OCR-generated or manually reviewed questions.

## OCR And Generated Questions

The scanned PDFs have now been OCRed with Tesseract Hindi + English OCR.

- Extracted text is in `extracted_text/`.
- The previous-year Kanishta Sahayak paper OCR is in `extracted_text/kanishtha_sahayak_2025.txt`.
- The active generated question bank is `data/generated_questions.js`.
- A JSON copy is available at `data/generated_questions.json`.
- The app automatically prefers the generated OCR bank over the starter bank.

Current generated bank: 840 questions, 120 questions per unit.

To regenerate after improving OCR or replacing PDFs:

```powershell
python scripts/extract_text.py --unit all --dpi 180
python scripts/generate_questions.py
```

For best quality, review generated questions over time because OCR can merge columns or misread letters from scanned pages.
