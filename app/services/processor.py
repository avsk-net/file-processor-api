# app/services/processor.py

import json
import pandas as pd
from PIL import Image
import pdfplumber
from pathlib import Path
import numpy as np

# ─── CSV ───────────────────────────────────────────────────────────────────────

def process_csv(upload_path: str, output_path: str):
    try:
        df = pd.read_csv(upload_path)
    except Exception as e:
        raise ValueError(f"Could not parse CSV: {e}")

    if df.empty:
        raise ValueError("CSV file is empty.")

    summary = {}
    for col in df.columns:
        summary[col] = {}
        for stat, val in df.describe(include="all")[col].items():
            if pd.isna(val):
                summary[col][stat] = None
            elif isinstance(val, np.integer):
                summary[col][stat] = int(val)      # numpy.int64 → Python int
            elif isinstance(val, np.floating):
                summary[col][stat] = float(val)    # numpy.float64 → Python float
            else:
                summary[col][stat] = val

    report = {
        "rows": int(len(df)),                      # len() returns numpy int in some versions
        "columns": list(df.columns),
        "dtypes": {col: str(dt) for col, dt in df.dtypes.items()},
        "null_counts": {col: int(n) for col, n in df.isnull().sum().items()},
        "summary": summary,
        "preview": df.head(5).fillna("").to_dict(orient="records"),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)



# ─── IMAGE ─────────────────────────────────────────────────────────────────────

MAX_DIMENSION = 800  # max width OR height after resize

def process_image(upload_path: str, output_path: str):
    """
    Resizes the image so neither dimension exceeds MAX_DIMENSION,
    preserving the original aspect ratio.

    thumbnail() never upscales — only shrinks if the image is larger.
    LANCZOS is the highest-quality downsampling filter in Pillow.

    RGBA/P → RGB conversion: JPEG doesn't support transparency.
    We paste onto a white background instead of losing alpha data.
    """
    try:
        img = Image.open(upload_path)
    except Exception as e:
        raise ValueError(f"Could not open image: {e}")

    # Convert palette or transparent images to RGB
    if img.mode in ("RGBA", "P", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    # quality=85: good balance between file size and visual quality
    img.save(output_path, "JPEG", quality=85, optimize=True)


# ─── PDF ───────────────────────────────────────────────────────────────────────

def process_pdf(upload_path: str, output_path: str):
    """
    Extracts text from every page of the PDF.

    Works on text-based PDFs (Word exports, digital PDFs).
    Does NOT work on scanned PDFs (photos of pages) — those need OCR.

    extract_text() returns None on pages with no text — handled with 'or ""'.
    """
    try:
        pdf_file = pdfplumber.open(upload_path)
    except Exception as e:
        raise ValueError(f"Could not open PDF: {e}")

    pages = []
    with pdf_file:
        for num, page in enumerate(pdf_file.pages, start=1):
            text = page.extract_text() or ""
            pages.append({
                "page": num,
                "text": text.strip(),
                "char_count": len(text.strip()),
                "word_count": len(text.split()) if text.strip() else 0,
            })

    report = {
        "total_pages": len(pages),
        "total_chars": sum(p["char_count"] for p in pages),
        "total_words": sum(p["word_count"] for p in pages),
        "pages": pages,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


# ─── Dispatcher ────────────────────────────────────────────────────────────────

def process_file(file_id: str, file_type: str,
                 upload_path: str, output_path: str):
    """
    Routes to the correct processor based on file_type.

    This is the Dispatcher pattern — callers don't need to know
    which processor handles which type. They call process_file()
    and it figures out the rest.

    In Phase 4 the Celery task calls this exact function.
    """
    processors = {
        "csv":   process_csv,
        "image": process_image,
        "pdf":   process_pdf,
    }

    if file_type not in processors:
        raise ValueError(f"No processor registered for file type: {file_type}")

    processors[file_type](upload_path, output_path)
