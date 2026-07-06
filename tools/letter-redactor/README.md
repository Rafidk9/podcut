# Letter Redactor

Redacts sensitive personal info from visa grant / skills assessment letter PDFs, using the local `claude` CLI (no separate API key needed) to identify PII.

## How it works
1. `redact_letter.py` extracts every word + its exact position from the PDF (PyMuPDF). If a page has no text layer (a scanned/photographed letter), it falls back to OCR (Tesseract).
2. It sends the word list to `claude -p` and asks it to flag which word IDs are sensitive (names, DOB, passport/reference numbers, address, email, phone).
3. It applies a **true redaction** over those words (removes the underlying text/pixels, not just a visual overlay) and saves the output.

## Usage

Single file:
```
python redact_letter.py input.pdf output.pdf
```
Shows what it found and asks for confirmation before writing. Add `--auto` to skip the prompt.

Pick specific pages and/or output as an image instead of a PDF:
```
python redact_letter.py input.pdf output.png --pages 1 --format png
python redact_letter.py input.pdf output.pdf --pages 1,3-4
```
`--format` accepts `pdf` (default), `png`, or `jpg`.

Batch mode — point at a folder instead of a file (output must also be a folder). Every PDF in the input folder gets redacted, non-interactively:
```
python redact_letter.py ./letters ./redacted --format png
```

## Scanned / photographed letters
Handled automatically via OCR (Tesseract, installed locally) when a page has no digital text layer — no separate flag needed, it detects this per page.

## Files
- `redact_letter.py` — the tool
- `make_test_letter.py` — generates a synthetic fake letter for testing (no real client data)
- `test_letter.pdf` — test fixture (safe to redact repeatedly, contains no real client data)
