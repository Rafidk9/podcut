#!/usr/bin/env python3
"""
Redacts sensitive personal information from visa grant / skills assessment
letters, using the local Claude Code CLI (no Anthropic API key needed) to
classify which words are PII.

Handles both digital PDFs (native text layer) and scanned/photographed
letters (falls back to OCR via Tesseract when a page has no text layer).

Usage:
    Single file:
        python redact_letter.py input.pdf output.pdf
        python redact_letter.py input.pdf output.png --pages 1 --format png
        python redact_letter.py input.pdf output.pdf --pages 1,3-4

    Batch (input is a folder -> output must be a folder):
        python redact_letter.py ./letters ./redacted --format png

Flags:
    --pages   Which pages to include, e.g. "1" or "1,3-4". Default: all pages.
    --format  Output format: pdf (default), png, or jpg.
    --auto    Skip the confirmation prompt (always on in batch mode).
"""

import sys
import os
import glob
import json
import re
import subprocess
import argparse
import fitz  # PyMuPDF
import pytesseract
from PIL import Image

TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe".format(os.environ.get("USERNAME", "")),
]
for _cand in TESSERACT_CANDIDATES:
    if os.path.exists(_cand):
        pytesseract.pytesseract.tesseract_cmd = _cand
        break

OCR_DPI = 300


def parse_pages(spec, num_pages):
    """Parses a spec like '1,3-4' (1-based, inclusive) into sorted 0-based indices."""
    if not spec:
        return list(range(num_pages))
    result = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-")
            for p in range(int(a), int(b) + 1):
                result.add(p - 1)
        else:
            result.add(int(part) - 1)
    return sorted(p for p in result if 0 <= p < num_pages)


def ocr_page_words(page, id_start):
    """OCR fallback for pages with no text layer (scanned/photographed letters)."""
    zoom = OCR_DPI / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    words = []
    word_id = id_start
    scale = 72 / OCR_DPI  # convert OCR pixel coords back to PDF point coords
    for i, text in enumerate(data["text"]):
        text = text.strip()
        if not text:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        bbox = [x * scale, y * scale, (x + w) * scale, (y + h) * scale]
        words.append({"id": word_id, "page": page.number, "text": text, "bbox": bbox})
        word_id += 1
    return words


def extract_words(pdf_path, page_indices):
    """Returns a flat list of words (with page/id/text/bbox) for the given pages,
    using the PDF's native text layer where available and OCR otherwise."""
    doc = fitz.open(pdf_path)
    words = []
    word_id = 0
    used_ocr_pages = []
    for page_index in page_indices:
        page = doc[page_index]
        native = page.get_text("words")
        if native:
            for x0, y0, x1, y1, text, block_no, line_no, word_no in native:
                words.append({"id": word_id, "page": page_index, "text": text, "bbox": [x0, y0, x1, y1]})
                word_id += 1
        else:
            ocr_words = ocr_page_words(page, word_id)
            words.extend(ocr_words)
            word_id += len(ocr_words)
            if ocr_words:
                used_ocr_pages.append(page_index + 1)
    doc.close()
    return words, used_ocr_pages


def build_prompt(words):
    lines = [f'{w["id"]}: {w["text"]}' for w in words]
    word_list = "\n".join(lines)
    return f"""You are redacting a visa grant letter or skills assessment letter.
Below is a numbered list of every word on the page (id: word).

Identify every word ID that is part of SENSITIVE PERSONAL INFORMATION, including:
- Full names (applicant, and any other named individual)
- Date of birth
- Passport number
- Visa grant number / TRN (Transaction Reference Number)
- Client ID / application ID / assessment reference number
- Residential or mailing address (street, suburb, postcode)
- Phone number, email address
- Any other unique identifier tied to a specific person

Do NOT flag: generic letter boilerplate, department/organisation names, visa
subclass names, dates that are not the person's DOB (e.g. grant date, letter
date), section headers, or legal/informational text.

Word list:
{word_list}

Respond with ONLY a JSON array of the sensitive word IDs, e.g. [3,4,5,12,13].
No explanation, no markdown, just the JSON array. If none, respond with []."""


def call_claude(prompt):
    result = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "text"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {result.stderr.strip()}")
    return result.stdout.strip()


def parse_id_list(raw_output):
    match = re.search(r"\[[\d,\s]*\]", raw_output)
    if not match:
        raise ValueError(f"Could not find a JSON array in claude output:\n{raw_output}")
    return json.loads(match.group(0))


def redact_and_export(input_path, output_path, words, flagged_ids, page_indices, fmt):
    doc = fitz.open(input_path)
    flagged = set(flagged_ids)
    by_page = {}
    for w in words:
        if w["id"] in flagged:
            by_page.setdefault(w["page"], []).append(w["bbox"])

    for page_index, boxes in by_page.items():
        page = doc[page_index]
        for bbox in boxes:
            page.add_redact_annot(fitz.Rect(bbox), fill=(0, 0, 0))
        page.apply_redactions()

    if len(page_indices) != doc.page_count:
        doc.select(page_indices)

    outputs = []
    if fmt == "pdf":
        out = output_path if output_path.lower().endswith(".pdf") else output_path + ".pdf"
        doc.save(out)
        outputs.append(out)
    else:
        stem = os.path.splitext(output_path)[0]
        multi = doc.page_count > 1
        for i in range(doc.page_count):
            pix = doc[i].get_pixmap(dpi=200)
            out = f"{stem}_page{i+1}.{fmt}" if multi else f"{stem}.{fmt}"
            pix.save(out)
            outputs.append(out)

    doc.close()
    return outputs


def process_file(input_path, output_path, pages_spec, fmt, auto, quiet=False):
    """Runs the full pipeline for one file. Returns a summary dict."""
    log = print if not quiet else (lambda *a, **k: None)

    probe = fitz.open(input_path)
    num_pages = probe.page_count
    probe.close()
    page_indices = parse_pages(pages_spec, num_pages)

    log(f"[{os.path.basename(input_path)}] extracting text (pages {[p+1 for p in page_indices]}) ...")
    words, ocr_pages = extract_words(input_path, page_indices)
    if ocr_pages:
        log(f"  used OCR fallback for scanned page(s): {ocr_pages}")
    if not words:
        log("  No text found (even after OCR attempt). Skipping.")
        return {"file": input_path, "status": "no_text", "flagged": 0}

    prompt = build_prompt(words)
    raw = call_claude(prompt)
    flagged_ids = parse_id_list(raw)

    if not flagged_ids:
        log("  No sensitive fields detected.")
        return {"file": input_path, "status": "no_pii_found", "flagged": 0}

    flagged_words = [w for w in words if w["id"] in set(flagged_ids)]
    log(f"  Detected {len(flagged_words)} sensitive word(s).")

    if not auto:
        for w in flagged_words:
            print(f"    [page {w['page']+1}] {w['text']}")
        answer = input("  Proceed with redaction? [y/N] ").strip().lower()
        if answer != "y":
            log("  Skipped.")
            return {"file": input_path, "status": "skipped", "flagged": len(flagged_words)}

    outputs = redact_and_export(input_path, output_path, words, flagged_ids, page_indices, fmt)
    log(f"  Wrote: {outputs}")
    return {"file": input_path, "status": "redacted", "flagged": len(flagged_words), "outputs": outputs}


def main():
    parser = argparse.ArgumentParser(description="Redact PII from visa/skills letters")
    parser.add_argument("input", help="Input PDF file, or a folder for batch mode")
    parser.add_argument("output", help="Output path (file), or output folder for batch mode")
    parser.add_argument("--pages", help='Pages to include, e.g. "1" or "1,3-4". Default: all pages.')
    parser.add_argument("--format", choices=["pdf", "png", "jpg"], default="pdf", help="Output format")
    parser.add_argument("--auto", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    if os.path.isdir(args.input):
        os.makedirs(args.output, exist_ok=True)
        pdf_files = sorted(glob.glob(os.path.join(args.input, "*.pdf")))
        if not pdf_files:
            print(f"No PDF files found in {args.input}")
            sys.exit(1)

        print(f"Batch mode: {len(pdf_files)} file(s) found in {args.input}\n")
        summary = []
        for f in pdf_files:
            stem = os.path.splitext(os.path.basename(f))[0]
            out_path = os.path.join(args.output, f"{stem}_redacted")
            try:
                result = process_file(f, out_path, args.pages, args.format, auto=True, quiet=True)
            except Exception as e:
                result = {"file": f, "status": "error", "error": str(e)}
            summary.append(result)
            print(f"  {os.path.basename(f):50s} -> {result['status']} ({result.get('flagged', 0)} field(s))")

        print(f"\nDone. {sum(1 for r in summary if r['status']=='redacted')}/{len(summary)} redacted.")
    else:
        process_file(args.input, args.output, args.pages, args.format, auto=args.auto)


if __name__ == "__main__":
    main()
