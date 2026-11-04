import os
import re
import json
import pymupdf
import pdfplumber
import pandas as pd
from docling.document_converter import DocumentConverter

PDF_PATH = "sample_docs/OBE_Document_Version_2.2_BSCS_BSSE.pdf"

if not os.path.exists(PDF_PATH):
    print(f"Error: File not found at {PDF_PATH}")
    exit(1)


# =====================================================================
# 1. DYNAMIC PLO MATRIX EXTRACTION (pdfplumber)
# Scans every page for tables containing PLO matrix markers
# =====================================================================
def extract_plo_matrices_dynamically(pdf_path):
    print("\n==================================================")
    print(" 1. DYNAMIC PLO MATRIX EXTRACTION (pdfplumber)    ")
    print("==================================================")
    
    matrix_tables = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for table in tables:
                table_str = str(table)
                
                # Dynamic Trigger: Table must contain core category names or checkmark symbols
                if "Computing Core" in table_str or "Domain Core" in table_str or "✔" in table_str or "☑" in table_str:
                    matrix_tables.append((page_num, table))
                    
    print(f"Dynamically detected {len(matrix_tables)} PLO matrix table(s) across the document.\n")
    
    for page_num, table in matrix_tables[:2]:  # Preview first 2 detected matrices
        df = pd.DataFrame(table).dropna(how="all")
        print(f"--- Matrix Table Detected on Page {page_num} ---")
        print(df.head(6).to_string(index=False, header=False))
        print("-" * 50)


# =====================================================================
# 2. DYNAMIC COURSE & CLO EXTRACTION (PyMuPDF)
# Uses Regex pattern matching (e.g., "CS3683: Theory of Automata")
# =====================================================================
def extract_courses_dynamically(pdf_path):
    print("\n==================================================")
    print(" 2. DYNAMIC COURSE & CLO EXTRACTION (PyMuPDF)    ")
    print("==================================================")
    
    doc = pymupdf.open(pdf_path)
    
    # Regex pattern matching course headers: CODE + 4 digits + COLON + TITLE
    # Example matches: "CS3683: Theory of Automata", "SE3213: Software Design and Architecture"
    course_header_pattern = re.compile(r'^([A-Z]{2,4}\s*\d{4})\s*:\s*(.+)$', re.MULTILINE)
    
    # Read entire document text sequentially
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"
        
    matches = list(course_header_pattern.finditer(full_text))
    extracted_courses = []
    
    for idx, match in enumerate(matches):
        course_code = match.group(1).strip()
        course_title = match.group(2).strip()
        
        # Determine current course block boundary (from current header to next header)
        start_pos = match.end()
        end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
        course_body = full_text[start_pos:end_pos]
        
        # Dynamic regex search for Credit Hours
        credit_match = re.search(r'Credit\s*Hours\s*:\s*([^\n]+)', course_body, re.IGNORECASE)
        credit_hours = credit_match.group(1).strip() if credit_match else "N/A"
        
        # Dynamic search for CLO statements (numbered items under Course Learning Outcomes)
        clo_matches = re.findall(r'(\d+\.\s*[\s\S]*?\((?:Cognitive|Affective|Psychomotor)[\s\S]*?\)\s*-\s*\([^)]+\))', course_body)
        
        extracted_courses.append({
            "code": course_code,
            "title": course_title,
            "credit_hours": credit_hours,
            "clos_found": len(clo_matches),
            "sample_clo": clo_matches[0].replace('\n', ' ').strip() if clo_matches else "N/A"
        })
        
    print(f"Dynamically parsed {len(extracted_courses)} total course syllabi across the document.\n")
    print("Sample Extracted Course Data (JSON format):")
    print(json.dumps(extracted_courses[:2], indent=2))


# =====================================================================
# 3. DYNAMIC FULL-DOCUMENT MARKDOWN CONVERSION (Docling)
# Converts the whole document automatically regardless of page count
# =====================================================================
def convert_full_document_to_markdown(pdf_path):
    print("\n==================================================")
    print(" 3. DYNAMIC MARKDOWN CONVERSION (Docling)         ")
    print("==================================================")
    
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    markdown_output = result.document.export_to_markdown()
    
    print(f"Successfully converted full PDF into Markdown ({len(markdown_output)} characters).")
    print("\nSample Markdown Block:\n")
    print(markdown_output[1500:2200])  # Print a snippet from the middle of output


if __name__ == "__main__":
    extract_plo_matrices_dynamically(PDF_PATH)
    extract_courses_dynamically(PDF_PATH)
    convert_full_document_to_markdown(PDF_PATH)