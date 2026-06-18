"""OCR the scanned BS Negi PDFs into per-unit text files.

The PDFs in this folder are scanned page images. This script renders each page
with PyMuPDF and runs Tesseract with Hindi + English language data.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "extracted_text"
TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
TESSDATA = ROOT / "tools" / "tessdata"

PDFS = {
    "unit_1": "BS NEgi 5 edition Unit 1.pdf",
    "unit_2": "BS Negi 5 edition unit 2.pdf",
    "unit_3": "BS negi 5 edition (unit 3).pdf",
    "unit_4": "BS negi 5 edition UNIT-4.pdf",
    "unit_5": "BS negi 5 edition UNIT-5.pdf",
    "unit_6": "BS negi unit 6 complete.pdf",
    "unit_7": "b s negi 5 edition (unit 7)chp-43-55.pdf",
    "kanishtha_sahayak_2025": "कनिष्ठ_सहायक_एग्जाम_पेपर_19,01,2025.pdf",
}


def page_numbers(total: int, start: int | None, end: int | None, limit: int | None) -> range:
    first = max(1, start or 1)
    last = min(total, end or total)
    if limit:
        last = min(last, first + limit - 1)
    return range(first, last + 1)


def ocr_page(doc: fitz.Document, page_no: int, tmp_dir: Path, dpi: int) -> str:
    page = doc.load_page(page_no - 1)
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    image_path = tmp_dir / f"page_{page_no:04d}.png"
    output_base = tmp_dir / f"page_{page_no:04d}"
    pix.save(image_path)

    env = os.environ.copy()
    env["TESSDATA_PREFIX"] = str(TESSDATA)
    command = [
        str(TESSERACT),
        str(image_path),
        str(output_base),
        "-l",
        "hin+eng",
        "--tessdata-dir",
        str(TESSDATA),
        "--psm",
        "6",
    ]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env)
    text_path = output_base.with_suffix(".txt")
    return text_path.read_text(encoding="utf-8", errors="ignore").strip()


def extract_pdf(key: str, filename: str, args: argparse.Namespace) -> None:
    pdf_path = ROOT / filename
    out_path = OUT_DIR / f"{key}.txt"
    if not pdf_path.exists():
        print(f"Missing: {filename}")
        return

    doc = fitz.open(pdf_path)
    pages = list(page_numbers(doc.page_count, args.start, args.end, args.limit))
    chunks: list[str] = []
    with tempfile.TemporaryDirectory(prefix=f"ocr_{key}_") as tmp:
        tmp_dir = Path(tmp)
        for page_no in pages:
            try:
                text = ocr_page(doc, page_no, tmp_dir, args.dpi)
            except subprocess.CalledProcessError as exc:
                err = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else str(exc)
                text = f"[OCR failed on page {page_no}: {err}]"
            chunks.append(f"\n\n--- Page {page_no} ---\n{text}")
            print(f"{key}: page {page_no}/{doc.page_count} OCR complete")

    out_path.write_text("".join(chunks).strip() + "\n", encoding="utf-8")
    print(f"Wrote {out_path.relative_to(ROOT)} ({len(chunks)} pages)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit", choices=[*PDFS.keys(), "all"], default="all")
    parser.add_argument("--start", type=int, help="First page number, 1-based.")
    parser.add_argument("--end", type=int, help="Last page number, 1-based.")
    parser.add_argument("--limit", type=int, help="Maximum pages per PDF.")
    parser.add_argument("--dpi", type=int, default=220)
    args = parser.parse_args()

    if not TESSERACT.exists():
        print(f"Tesseract not found: {TESSERACT}")
        return 2
    if not (TESSDATA / "hin.traineddata").exists():
        print(f"Hindi trained data not found: {TESSDATA / 'hin.traineddata'}")
        return 2

    OUT_DIR.mkdir(exist_ok=True)
    selected = PDFS.items() if args.unit == "all" else [(args.unit, PDFS[args.unit])]
    for key, filename in selected:
        extract_pdf(key, filename, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
