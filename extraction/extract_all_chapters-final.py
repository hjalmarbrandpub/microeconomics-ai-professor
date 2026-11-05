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
