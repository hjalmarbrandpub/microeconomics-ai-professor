# Technical Guide: Sequential Textbook Chapter Extraction Pipeline (`extract_all_chapters-v11.py`)

## 1. System Overview & Architectural Purpose

In Retrieval-Augmented Generation (RAG) pipelines and educational AI tools, processing a full textbook as a single monolithic PDF introduces severe context degradation, retrieval noise, and vector store inefficiencies. To prepare structured textbook data for chunking and vector indexing, documents must be sliced into isolated, per-chapter files.

The **Sequential Textbook Chapter Extractor (`extract_all_chapters-v11.py`)** is an automated PDF parsing and extraction tool designed to process digital textbook PDFs. It systematically identifies chapter boundaries, slices the raw PDF into standalone per-chapter PDF files, and converts each chapter into structured Markdown preserving headings and mathematical layout.

### Key Capabilities
* **Sequential State-Machine Search**: Scans the textbook strictly in ascending order ($1 \rightarrow 2 \rightarrow \dots \rightarrow N$), preventing false splits, out-of-order page matches, or premature chapter creation.
* **Strict Uppercase Keyword Matching**: Requires exact capital letter matching for `CHAPTER` headings to avoid false positives in body text.
* **Spaced Double-Digit Handling**: Accounts for complex PDF font encoding where double-digit numbers contain spaces or line breaks (e.g., `CHAPTER 1 0`, `CHAPTER 1 1`).
* **Whole-Page Scanning**: Evaluates the full page text to catch chapter titles placed below publisher logos, decorative artwork, or chapter subheadings.
* **Terminal Index Boundary Detection**: Automatically locates the back-of-book `INDEX` section (or `I N D E X`) and caps the final chapter immediately before it begins.
* **Dual Output & Docling Integration**: Exports both standalone `.pdf` files and high-fidelity `.md` Markdown documents via IBM Docling, with a graceful fallback to `pypdf` text extraction.

---

## 2. Prerequisites & Module Dependencies

The extraction script relies on standard Python environment libraries alongside specialized document processing packages.

| Module | Type | Purpose | Installation Required? |
| :--- | :--- | :--- | :--- |
| `os` | Standard Library | Directory creation, file path construction, and file existence checks | No (Built-in) |
| `re` | Standard Library | Regular expression compilation for strict keyword and spaced-digit pattern matching | No (Built-in) |
| `json` | Standard Library | Structuring and exporting chapter page ranges to `chapter_page_ranges.json` | No (Built-in) |
| `pypdf` | External Package | PDF page scanning, text extraction, page slicing, and writing output PDFs | **Yes** |
| `docling` | External Package | Advanced PDF-to-Markdown conversion preserving tables, LaTeX, and headings | **Optional (Recommended)** |

### Environment Setup

To install the required dependencies in a Google Colab notebook or local terminal, execute the following command:

```bash
pip install pypdf docling
```

If IBM Docling is not installed, the script automatically detects its absence and falls back to native `pypdf` text extraction without raising an error.

---

## 3. Extraction Architecture & Algorithm Breakdown

The script operates through a two-phase workflow: **Boundary Discovery** followed by **Page Slicing & File Generation**.

### Phase 1: Sequential Boundary Discovery Engine

The discovery engine uses a state machine tracked by `current_target_ch`, starting at `1`. For every page in the PDF, the engine builds a targeted regular expression pattern matching the current chapter goal.

#### 1. Single-Digit Matching (Chapters 1 to 9)
For chapters 1 through 9, the script matches uppercase `CHAPTER` followed by whitespace and the single target digit bounded by word delimiters:

$$\text{Pattern}_{<10} = \text{r}'\backslash\text{bCHAPTER}[\backslash\text{s}\backslash\text{xa0}\backslash\text{n}]+N\backslash\text{b}'$$

#### 2. Spaced Double-Digit Matching (Chapters 10 and Beyond)
In many digital textbooks, font kerning or layout encoding causes double-digit chapter titles to extract as separate characters (e.g., `CHAPTER 1 0` or `CHAPTER 1\n0`). To resolve this, the script splits the target number into two separate digit variables, $d_1$ and $d_2$:

$$\text{Pattern}_{\ge 10} = \text{r}'\backslash\text{bCHAPTER}[\backslash\text{s}\backslash\text{xa0}\backslash\text{n}]+d_1[\backslash\text{s}\backslash\text{xa0}\backslash\text{n}]*d_2\backslash\text{b}'$$

This pattern matches all of the following PDF extraction variations:
* `CHAPTER 10`
* `CHAPTER 1 0`
* `CHAPTER 1  0`
* `CHAPTER 1\n0`

#### 3. Terminal Index Truncation
Once all chapters have been identified, the script scans the pages following the start of the final chapter for the back-of-book index heading using the pattern:

$$\text{Pattern}_{\text{Index}} = \text{r}'\backslash\text{bINDEX}\backslash\text{b}|\backslash\text{bI}[\backslash\text{s}\backslash\text{xa0}\backslash\text{n}]+N[\backslash\text{s}\backslash\text{xa0}\backslash\text{n}]+D[\backslash\text{s}\backslash\xa0\backslash\text{n}]+E[\backslash\text{s}\backslash\xa0\backslash\text{n}]+X\backslash\text{b}'$$

If `INDEX` is found on page $P_{\text{index}}$, the end page for the final chapter is capped at $P_{\text{index}} - 1$.

---

## 4. Complete Script Code (`extract_all_chapters-v11.py`)

Below is the complete, standalone Python implementation:

```python
import os
import re
import json
from pypdf import PdfReader, PdfWriter

def find_chapter_page_ranges(pdf_path="Intermediate Microeconomics Textbook.pdf", output_json="chapter_page_ranges.json"):
    """
    Scans a textbook PDF page by page in strict sequential order:
    CHAPTER 1 -> CHAPTER 2 -> ... -> CHAPTER 9 -> CHAPTER 1 0 -> CHAPTER 1 1 ...
    
    Handles PDF formatting where digits after Chapter 9 have spaces between them
    (e.g., 'CHAPTER 1 0', 'CHAPTER 1 1', or 'CHAPTER 2 5').
    
    The last chapter stops when it encounters 'INDEX' (or 'I N D E X').
    """
    if not os.path.exists(pdf_path):
        print(f"❌ Input PDF '{pdf_path}' not found. Please verify the file path.")
        return None

    print(f"🔍 Reading '{pdf_path}' (Scanning for UPPERCASE 'CHAPTER' and 'INDEX')...")
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    print(f"📖 Total pages in textbook: {total_pages}\n")

    current_target_ch = 1
    chapter_starts = {}

    for idx in range(total_pages):
        page_text = reader.pages[idx].extract_text() or ""
        
        # Build strict regex pattern for target chapter
        if current_target_ch < 10:
            # Single digit: CHAPTER 1 ... CHAPTER 9
            pattern_str = rf'\bCHAPTER[\s\xa0\n]+{current_target_ch}\b'
        else:
            # Double digit: CHAPTER 1 0, CHAPTER 1 1, etc.
            ch_str = str(current_target_ch)
            d1, d2 = ch_str[0], ch_str[1]
            pattern_str = rf'\bCHAPTER[\s\xa0\n]+{d1}[\s\xa0\n]*{d2}\b'

        pattern = re.compile(pattern_str)

        if pattern.search(page_text):
            chapter_starts[current_target_ch] = idx + 1  # 1-based page index
            print(f"📍 Found CHAPTER {current_target_ch:2d} -> Starts at PDF Page {idx + 1}")
            current_target_ch += 1

    if not chapter_starts:
        print("⚠️ No chapters were detected. Please check the PDF formatting or file path.")
        return None

    sorted_chs = sorted(chapter_starts.items())

    # Search for INDEX starting after the last chapter start page
    last_ch_num, last_ch_start = sorted_chs[-1]
    index_start_page = None

    for idx in range(last_ch_start - 1, total_pages):
        page_text = reader.pages[idx].extract_text() or ""
        lines = [line.strip() for line in page_text.split('\n') if line.strip()]
        top_lines_text = " ".join(lines[:5]) if lines else page_text

        # Match uppercase INDEX or spaced I N D E X in header or page text
        index_pattern = re.compile(r'\bINDEX\b|\bI[\s\xa0\n]+N[\s\xa0\n]+D[\s\xa0\n]+E[\s\xa0\n]+X\b')
        if index_pattern.search(top_lines_text):
            index_start_page = idx + 1  # 1-based index
            print(f"📍 Found INDEX -> Starts at PDF Page {index_start_page}")
            break

    page_ranges = []

    print("\n" + "="*55)
    print(f"{'CHAPTER':<12} | {'START PAGE':<12} | {'END PAGE':<12} | {'TOTAL PAGES':<12}")
    print("="*55)

    for i in range(len(sorted_chs)):
        ch_num, start_p = sorted_chs[i]
        if i + 1 < len(sorted_chs):
            end_p = sorted_chs[i + 1][1] - 1
        else:
            # Last chapter ends right before INDEX if INDEX was found, else total_pages
            end_p = (index_start_page - 1) if index_start_page else total_pages

        num_pages = end_p - start_p + 1
        range_info = {
            "chapter": ch_num,
            "start_page": start_p,
            "end_page": end_p,
            "total_pages": num_pages
        }
        page_ranges.append(range_info)
        print(f"CHAPTER {ch_num:<4d} | Page {start_p:<7d} | Page {end_p:<7d} | {num_pages:<5d} pages")

    print("="*55)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(page_ranges, f, indent=2)

    print(f"\n🎉 Successfully exported page ranges to '{output_json}'.")
    return page_ranges

def extract_all_chapters(pdf_path="Intermediate Microeconomics Textbook.pdf", output_dir="data/processed/chapters"):
    page_ranges = find_chapter_page_ranges(pdf_path)
    if not page_ranges:
        return

    os.makedirs(output_dir, exist_ok=True)
    pdf_out_dir = os.path.join(output_dir, "pdfs")
    md_out_dir = os.path.join(output_dir, "markdowns")
    os.makedirs(pdf_out_dir, exist_ok=True)
    os.makedirs(md_out_dir, exist_ok=True)

    reader = PdfReader(pdf_path)

    docling_available = False
    try:
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        docling_available = True
        print("\n🚀 IBM Docling parser detected. Markdown conversion enabled.")
    except ImportError:
        print("\n⚠️ Docling not installed. Using pypdf text extraction fallback.")

    for item in page_ranges:
        ch_num = item["chapter"]
        start_idx = item["start_page"] - 1
        end_idx = item["end_page"]

        chapter_pdf_path = os.path.join(pdf_out_dir, f"chapter_{ch_num}.pdf")
        chapter_md_path = os.path.join(md_out_dir, f"chapter_{ch_num}.md")

        print(f"\n📦 Extracting CHAPTER {ch_num} (Pages {item['start_page']} to {item['end_page']})...")

        writer = PdfWriter()
        for p in range(start_idx, end_idx):
            writer.add_page(reader.pages[p])

        with open(chapter_pdf_path, "wb") as f:
            writer.write(f)

        if docling_available:
            try:
                res = converter.convert(chapter_pdf_path)
                md_text = res.document.export_to_markdown()
            except Exception as e:
                print(f"   ⚠️ Docling error on Ch {ch_num}: {e}. Falling back to pypdf...")
                md_text = fallback_text(reader, start_idx, end_idx, ch_num)
        else:
            md_text = fallback_text(reader, start_idx, end_idx, ch_num)

        with open(chapter_md_path, "w", encoding="utf-8") as f:
            f.write(md_text)

        print(f"   💾 PDF: {chapter_pdf_path}")
        print(f"   📝 Markdown: {chapter_md_path} ({len(md_text)} chars)")

    print(f"\n🎉 Complete! All {len(page_ranges)} chapters extracted to '{output_dir}'.")

def fallback_text(reader, start_idx, end_idx, ch_num):
    text = f"# CHAPTER {ch_num}\n\n"
    for p in range(start_idx, end_idx):
        text += f"<!-- Page {p+1} -->\n" + (reader.pages[p].extract_text() or "") + "\n\n"
    return text

if __name__ == "__main__":
    extract_all_chapters()
```

---

## 5. Execution Workflow & Output Directory Structure

### Execution Steps

1. Place your target textbook PDF in the working directory as `Intermediate Microeconomics Textbook.pdf` (or update the `pdf_path` parameter in `extract_all_chapters()`).
2. Run the script:
   ```bash
   python extract_all_chapters-v11.py
   ```

### Output Artifacts

The script creates the following organized directory tree:

```
data/
└── processed/
    └── chapters/
        ├── pdfs/
        │   ├── chapter_1.pdf
        │   ├── chapter_2.pdf
        │   ├── ...
        │   └── chapter_36.pdf
        └── markdowns/
            ├── chapter_1.md
            ├── chapter_2.md
            ├── ...
            └── chapter_36.md
chapter_page_ranges.json
```

* **`chapter_page_ranges.json`**: Contains a structured JSON array mapping every chapter number to its exact start page, end page, and total page count.
* **`pdfs/`**: Contains clean, isolated PDF files sliced directly from the original document.
* **`markdowns/`**: Contains formatted Markdown files ready for hierarchical chunking (`rag_hierarchical_chunker.py`) and vector database ingestion.
