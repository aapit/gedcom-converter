# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains two Python converters that transform genealogical data into GEDCOM format (GEnealogical Data COMmunication), the standard format for genealogy software.

1. **Kwartierstaat Converter** (`import_kwartierstaat.py`) - Converts Excel-based ancestor lists (Ahnentafel/kwartierstaat) to GEDCOM
2. **Stamboom Converter** (`import_stamboom_doc.py`) - Converts structured Word documents (.doc) containing family tree descriptions to GEDCOM

## Running the Converters

```bash
# Activate virtual environment (if it exists)
source venv/bin/activate

# Run kwartierstaat converter
python3 import_kwartierstaat.py
# Input: kwartierstaat TT excel.xlsx
# Output: gedcom/kwartierstaat.ged

# Run stamboom converter (macOS only - uses textutil)
# Process all .doc/.docx files in stambomen/ directory
python3 import_stamboom_doc.py
# Outputs: One .ged file per input in gedcom/ directory
#   - gedcom/JONGE_DE_3_X.ged
#   - gedcom/THOMASSEN_16_David.ged
#   - gedcom/WETELING_1_Philippus.ged
#   - gedcom/RUTJES_9.ged

# Process a specific file
python3 import_stamboom_doc.py stambomen/THOMASSEN\ 16\ David.doc
# Output: gedcom/THOMASSEN_16_David.ged

# Specify custom output filename (still goes to gedcom/ directory)
python3 import_stamboom_doc.py stambomen/THOMASSEN\ 16\ David.doc custom_output.ged
# Output: gedcom/custom_output.ged
```

## Dependencies

- Python 3.6+
- pandas and openpyxl (for Excel parsing - kwartierstaat only)
- macOS textutil command (for .doc/.docx conversion - stamboom only)

Install dependencies:
```bash
pip install pandas openpyxl pytest
```

## Directory Structure

```
.
├── stambomen/              # Input: Word documents (.doc/.docx)
│   ├── JONGE DE 3 X.doc
│   ├── RUTJES 9.docx
│   ├── THOMASSEN 16 David.doc
│   └── WETELING 1 Philippus.doc
├── gedcom/                 # Output: Generated GEDCOM files
│   ├── JONGE_DE_3_X.ged
│   ├── RUTJES_9.ged
│   ├── THOMASSEN_16_David.ged
│   ├── WETELING_1_Philippus.ged
│   └── kwartierstaat.ged
├── import_stamboom_doc.py  # Stamboom converter
├── import_kwartierstaat.py # Kwartierstaat converter
└── test_stamboom_parser.py # Unit tests
```

## Testing

### Unit Tests

Both converters have comprehensive unit test coverage:
- **Stamboom converter:** 61 tests in `test_stamboom_parser.py`
- **Kwartierstaat converter:** 13 tests in `test_kwartierstaat.py`

**Running tests:**
```bash
# Activate virtual environment
source venv/bin/activate

# Run all stamboom tests
pytest test_stamboom_parser.py -v

# Run all kwartierstaat tests
pytest test_kwartierstaat.py -v

# Run all tests
pytest test_*.py -v

# Run specific test class
pytest test_stamboom_parser.py::TestParseSpouseParents -v

# Run with coverage report
pytest test_stamboom_parser.py --cov=import_stamboom_doc --cov-report=html
pytest test_kwartierstaat.py --cov=import_kwartierstaat --cov-report=html
```

**Stamboom test coverage includes:**
- `parse_spouse_parents()` - Parent extraction with profession/address filtering
- `parse_place_date()` - Various date and place formats
- `parse_date()` - Date format variations (DD-MM-YYYY, ±YYYY, etc.)
- `normalize_name()` - ALL-CAPS to Title Case, Dutch prepositions
- `parse_person_header()` - Generation IDs with/without trailing period
- Integration tests - Birth/death/marriage on same line
- Class structures - Person and Marriage initialization
- URL filtering, occupation filtering, BS reference removal
- Marriage patterns (Tr., Otr., Ondertr., Relatie met)
- Spouse name handling: "NN" (nomen nescio), "zie" reference filtering

**Kwartierstaat test coverage includes:**
- `parse_place_year()` - Date/year extraction with uncertainty markers
- Date format support: `±1850` (circa), `<1800` (before), `>1900` (after)
- Place extraction with "Geb." prefix removal
- Edge cases: year-only, place-only, with/without spaces
- Name parsing with Dutch prepositions and abbreviations
- Surname detection: `a/d` (aan de), `v/d` (van de), `van`, `de`, etc.
- Test cases: "Willems a/d Rooijendijk", "Jansen v/d Berg", "van den Brink"

**IMPORTANT: Always run tests after making changes**

```bash
# Quick test before committing
source venv/bin/activate && pytest test_*.py -v
```

**Adding new tests:**
When adding new parsing features:
1. Add corresponding unit tests to `test_stamboom_parser.py`
2. Test both normal cases and edge cases
3. Use descriptive test names: `test_<what>_<expected_result>`
4. Run full test suite to prevent regressions

See `test_README.md` for detailed test documentation.

## Architecture

### Kwartierstaat Converter (`import_kwartierstaat.py`)

Converts structured Excel spreadsheets where ancestors are numbered using the Ahnentafel system (1=proband, 2=father, 3=mother, 2n=father of n, 2n+1=mother of n).

**Key Components:**
- `GedcomGenerator` class handles all GEDCOM generation
- `parse_place_year()` - Extracts year and place from combined strings
- `determine_sex()` - Determines gender from Ahnentafel number (even=male, odd=female)
- `create_families()` - Builds family relationships from parent-child numbering

### Stamboom Converter (`import_stamboom_doc.py`)

Parses Word documents with generational structure (I.1, II.1, III.1, etc.) containing detailed biographical information.

**Key Components:**
- `Person` class - Stores individual data (birth, death, baptism, burial, marriages, children)
- `Marriage` class - Stores marriage details (date, place, spouse, witnesses)
- `StamboomParser` class - Main parser with state machine for processing lines

**Parser Flow:**
1. Convert .doc to text using macOS `textutil` command
2. Skip legend, process line-by-line starting from first generation
3. Detect person headers (regex: `^[IVX]+\.\d+`)
4. Parse life events (symbols: * birth, △ baptism, † death, ▭ burial)
5. Parse marriages (keywords: "Otr.", "Tr.")
6. Parse children ("Hieruit:", "Uit (1):", "Uit (2):")
7. Build family structures in two passes:
   - Pass 1: Create families for all marriages
   - Pass 2: Link children to parent families

**Name Normalization:**
- `normalize_name()` - Converts ALL-CAPS names to Title Case
- Dutch prepositions (van, den, de, der, etc.) → lowercase
- Special abbreviations (NN, N.N.) → preserved in caps
- Handles names with parentheses and punctuation

### GEDCOM Generation

Both converters create GEDCOM 5.5.1 format with:
- UTF-8 encoding for Dutch characters
- Bidirectional family references (INDI ↔ FAM)
- FAMS (spouse in family) and FAMC (child in family) links
- Standard tags: BIRT, CHR, MARR, DEAT, BURI
- Notes for additional context and source references

**Critical for GEDCOM validity:**
- Every person with FAMS must appear as HUSB/WIFE in that family
- Every family with HUSB/WIFE must have that person link back via FAMS
- Family IDs must be unique and properly referenced

## Document Structure Expectations

### Kwartierstaat Excel Format
- Column 0: Generation number (optional)
- Column 1: Ahnentafel number (required)
- Column 2: Full name
- Column 3: Birth (format: "Place year")
- Column 4: Death (format: "Place year")
- Column 5: Marriage (format: "Place year")

### Stamboom Word Format
Document must have:
- Legend at top with symbol definitions
- Generation headers: "Eerste generatie", "Tweede generatie", etc.
- Person entries: `I.1 Name [ref_num]`
- Gender markers: "zn. van" (son of) or "dr. van" (daughter of)
- Life event symbols: *, △, †, ▭
- Marriage markers: "Otr.", "Tr.", "otr. / tr."
- Children sections: "Hieruit:", "Uit (1):", "Uit (2):"
- Cross-references: "zie III.1" links to other persons

## Common Issues and Solutions

**Stamboom Parser:**
- False positive marriages: Parser only triggers on lines starting with "Otr." or "Tr." to avoid matching archival text
- Partner names: Detected on line immediately after marriage line, filtered to exclude location names
- All-caps names: Automatically normalized but can be adjusted in `LOWERCASE_PREPOSITIONS` set
- Missing FAMS links: Ensure families are created before writing INDI records
- **NN (nomen nescio)**: Recognized as valid spouse name (exception to minimum length filter)
- **Multiple marriages**: Children correctly assigned to marriage families using "Uit (1):", "Uit (2):" markers
- **Name variants**: Consecutive names without life event symbols (before baptism Δ) are merged as "Ook bekend als" notes
- **Child marriage context**: After a child's marriage ("Tr. met"), the next line is treated as spouse, then context resets for subsequent children
- **Keyword filters**: Removed overly broad filters ("cuijk", "uit", "hieruit") that blocked archival references like marriage contracts

**GEDCOM Validation:**
- Use the validation script pattern in commit history to check bidirectional references
- Import errors about "not a member of family" indicate missing HUSB/WIFE links
- Header warnings can be resolved by simplifying to minimal GEDCOM 5.5.1 structure

## File Naming

Input files are currently hardcoded:
- Kwartierstaat: `kwartierstaat TT excel.xlsx`
- Stamboom: `THOMASSEN 16 David.doc`

To change filenames, modify the `main()` function in respective scripts.
