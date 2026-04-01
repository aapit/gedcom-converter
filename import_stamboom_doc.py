#!/usr/bin/env python3
"""
Converteer stamboom Word document naar GEDCOM formaat

Dit script leest een Word (.doc) bestand met een stamboom beschrijving en
converteert het naar GEDCOM formaat. Het document moet gestructureerd zijn
per generatie (I.1, II.1, III.1, etc.) met een legenda bovenin.

Gebruik:
    python3 import_stamboom_doc.py

Het script verwacht:
- Input: THOMASSEN 16 David.doc
- Output: stamboom.ged

De parser herkent:
- Personen met generatie IDs (I.1, II.1, III.1, etc.)
- Geboren (*), gedoopt (△), overleden (†), begraven (▭)
- Huwelijken (otr., tr.)
- Ouder-kind relaties (zn. van, dr. van)
- Kinderen (Hieruit:, Uit (1):, Uit (2):)

Vereisten:
- macOS (gebruikt textutil voor .doc conversie)
- Python 3.6+
"""

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


class Person:
    """Representeert een persoon in de stamboom"""

    def __init__(self, generation_id, ref_num=None):
        self.generation_id = generation_id  # bijv. "I.1", "II.1"
        self.ref_num = ref_num  # bijv. "512"
        self.name = ""
        self.birth_date = None
        self.birth_place = None
        self.baptism_date = None
        self.baptism_place = None
        self.baptism_witnesses = []
        self.death_date = None
        self.death_place = None
        self.burial_date = None
        self.burial_place = None
        self.sex = None
        self.marriages = []  # lijst van Marriage objecten
        self.children = []  # lijst van generation_ids
        self.parent_ref = None  # referentie naar ouder (bijv. "II.1")
        self.parent_marriage_num = None  # huwelijksnummer van de ouder (1, 2, 3, etc.) voor "Uit (1):", "Uit (2):"
        self.notes = []  # extra tekstuele notities


class Marriage:
    """Representeert een huwelijk"""

    def __init__(self):
        self.marriage_num = 1  # 1, 2, 3 voor meerdere huwelijken
        self.engagement_date = None
        self.engagement_place = None
        self.marriage_date = None
        self.marriage_place = None
        self.spouse_name = ""
        self.spouse_info = ""
        self.spouse_birth_date = None
        self.spouse_birth_place = None
        self.spouse_death_date = None
        self.spouse_death_place = None
        self.spouse_baptism_date = None
        self.spouse_baptism_place = None
        self.spouse_burial_date = None
        self.spouse_burial_place = None
        self.spouse_father_name = None  # Naam van vader van partner
        self.spouse_mother_name = None  # Naam van moeder van partner
        self.witnesses = []


class StamboomParser:
    """Parser voor stamboom Word document"""

    # Nederlandse beroepen die niet als namen geparsed moeten worden
    # Deze worden in kleine letter of Title Case gebruikt in documenten
    DUTCH_OCCUPATIONS = {
        'timmerman', 'landbouwer', 'bakker', 'smid', 'kleermaker',
        'schoenmaker', 'machinist', 'dienstbode', 'werkman', 'arbeider',
        'molenaar', 'wever', 'metselaar', 'schilder', 'timmermansknecht',
        'koopman', 'veehouder', 'veeboer', 'pachter', 'daglooner',
        'dagloner', 'spinner', 'naaister', 'dienstmeid', 'knecht',
        'meid', 'boer', 'landbouwster', 'winkelierster', 'winkelier',
        'vroedvrouw', 'onderwijzer', 'onderwijzeres', 'schoolmeester',
        'peuterleidster', 'politieagent', 'veldwachter', 'gemeenteveldwachter',
        'rijksveldwachter', 'agent', 'brigadier', 'hoofdagent', 'rijksambtenaar',
        'ambtenaar', 'klerk', 'kassier', 'werktuigkundige', 'bibliothecaris',
        'aannemer',
    }

    def __init__(self):
        self.persons = {}  # generation_id -> Person
        self.current_person = None
        self.current_marriage = None
        self.in_children_section = False
        self.current_marriage_num = 0
        self.parsing_spouse_info = False  # True wanneer we partner info aan het parsen zijn
        self.met_seen = False  # True nadat "met" is gezien na een Tr.-regel (partner volgt daarna)
        self.unnamed_children = []  # Kinderen zonder generatie ID
        self.current_child = None  # Huidig kind zonder generatie ID
        self.current_child_has_baptism = False  # True als we een Δ hebben gezien voor current_child
        self.child_marriage_context = False  # True wanneer we een huwelijk van een kind aan het parsen zijn
        self.child_marriage_lines_seen = 0  # Tel hoeveel regels we hebben gezien in child_marriage_context
        self.pending_name_variants = []  # Tijdelijke opslag voor naamvarianten van hetzelfde kind
        self.last_child_marriage = None  # Laatste huwelijk van kind, voor ouder-info op volgende regel
        self.current_child_spouse_stored = False  # True nadat partner van kind is opgeslagen (voorkomt dat * / △ / † de kind-data overschrijft)

    def parse_witnesses(self, text):
        """Extract getuigen uit tekst met 'gett.' of 'get.' patroon.
        
        Returns tuple (clean_text, witnesses_list).
        clean_text is de tekst zonder getuigen-deel.
        witnesses_list is lijst van getuigennamen.
        """
        if not text:
            return text, []
        
        # Split op gett./get.
        parts = re.split(r',?\s*gett?\.?\s*', text, maxsplit=1)
        if len(parts) < 2:
            return text, []
        
        clean_text = parts[0].strip()
        witness_text = parts[1].strip()
        
        # Verwijder alles na ; of † of ▭ of Tr. (dat is geen getuigen-info meer)
        witness_text = re.split(r'[;†▭]|\bTr\.|\bdr\.\s*van\b|\bzn\.\s*van\b', witness_text)[0].strip()
        
        # Split op ", " en " en " om individuele namen te krijgen
        raw_names = re.split(r',\s+|\s+en\s+', witness_text)
        
        # Filter: alleen echte namen behouden (minstens 2 woorden, begint met hoofdletter)
        witnesses = []
        for name in raw_names:
            name = name.strip().rstrip('.,;)')
            if name and re.match(r'^[A-Z]', name) and len(name) > 2:
                # Skip als het een bronvermelding is (DTB, BS, etc.)
                if not re.match(r'^(DTB|BS|RK|NG|NH)\b', name):
                    witnesses.append(name)
        
        return clean_text, witnesses

    def normalize_name(self, name):
        """Converteer all-caps namen naar title case"""
        if not name:
            return name

        # Enkel ALL-CAPS woord zonder voornaam is altijd een achternaam (bijv. "BELLEMANS", "HOUBEN")
        # Bewaar de ALL-CAPS vorm zodat de GEDCOM-schrijver het als achternaam kan herkennen
        words = name.split()
        if len(words) == 1 and words[0].isupper() and len(words[0]) > 2:
            return name  # Ongewijzigd teruggeven: "BELLEMANS" blijft "BELLEMANS"

        # Speciale afkortingen die altijd in caps moeten blijven
        KEEP_CAPS = {"NN", "N.N."}

        # Nederlandse tussenvoegsels die in kleine letters moeten
        LOWERCASE_PREPOSITIONS = {"VAN", "DER", "DEN", "DE", "HET", "TER", "TE", "'T", "VD"}

        # Check of de naam volledig in hoofdletters is (behalve haakjes en spaties)
        words = name.split()
        normalized_words = []

        for word in words:
            # Skip haakjes bij de check
            word_clean = word.strip("(),/[]")

            # Bewaar speciale afkortingen in caps
            if word_clean in KEEP_CAPS:
                normalized_words.append(word)
            # Converteer tussenvoegsels naar lowercase
            elif word_clean in LOWERCASE_PREPOSITIONS:
                # Behoud haakjes indien aanwezig
                if word.startswith("(") and word.endswith(")"):
                    normalized = "(" + word_clean.lower() + ")"
                elif word.startswith("("):
                    normalized = "(" + word_clean.lower()
                elif word.endswith(")"):
                    normalized = word_clean.lower() + ")"
                else:
                    normalized = word_clean.lower()
                normalized_words.append(normalized)
            # Initialen-patroon: één of meer hoofdletter-punt-combinaties (bijv. "A.W.", "J.P.M.")
            # Altijd in hoofdletters bewaren — niet naar title case converteren
            elif re.match(r'^([A-Z]\.)+$', word_clean):
                normalized_words.append(word)
            # Als het woord volledig in hoofdletters is en langer dan 1 karakter
            elif word_clean.isupper() and len(word_clean) > 1:
                # Converteer naar title case - gebruik slimme functie die alleen
                # de eerste letter capitaliseert (Python's .title() capitaliseert ook
                # na niet-letters zoals haakjes, bijv. WE(E)TELING → We(E)Teling i.p.v. We(e)teling)
                def _smart_title(s):
                    result = []
                    first_alpha = True
                    for c in s:
                        if c.isalpha():
                            result.append(c.upper() if first_alpha else c.lower())
                            first_alpha = False
                        else:
                            result.append(c)
                    return ''.join(result)

                # Behoud haakjes indien aanwezig
                if word.startswith("(") and word.endswith(")"):
                    normalized = "(" + _smart_title(word_clean) + ")"
                elif word.startswith("("):
                    normalized = "(" + _smart_title(word_clean)
                elif word.endswith(")"):
                    normalized = _smart_title(word_clean) + ")"
                else:
                    normalized = _smart_title(word_clean)
                normalized_words.append(normalized)
            else:
                # Behoud origineel als het niet all-caps is
                normalized_words.append(word)

        return " ".join(normalized_words)

    def read_doc_file(self, doc_path):
        """Lees .doc of .docx bestand en converteer naar tekst.
        
        .txt bestanden worden direct gelezen.
        .doc/.docx bestanden worden geconverteerd met het beste beschikbare
        gereedschap per platform:
        - macOS: textutil
        - Windows: Microsoft Word via COM automation (win32com)
        - Linux: LibreOffice (headless)
        - Fallback .docx: python-docx
        - Fallback .doc: antiword
        """
        doc_path = str(doc_path)
        
        # .txt bestanden direct lezen
        if doc_path.endswith('.txt'):
            with open(doc_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        # .docx via platform-specifieke tools, daarna python-docx fallback
        if doc_path.endswith('.docx'):
            text = self._convert_with_platform_tool(doc_path)
            if text is not None:
                return text
            # Fallback: python-docx
            try:
                import docx
                doc = docx.Document(doc_path)
                return '\n'.join(p.text for p in doc.paragraphs)
            except ImportError:
                raise RuntimeError(
                    f"Kan {doc_path} niet lezen: geen platform-tool beschikbaar "
                    f"en python-docx niet geïnstalleerd"
                )
        
        # .doc via platform-specifieke tools, daarna antiword fallback
        text = self._convert_with_platform_tool(doc_path)
        if text is not None:
            return text
        try:
            result = subprocess.run(
                ["antiword", doc_path],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except (FileNotFoundError, subprocess.CalledProcessError):
            raise RuntimeError(
                f"Kan {doc_path} niet lezen. Installeer een van: "
                f"textutil (macOS), Microsoft Word (Windows), "
                f"LibreOffice (Linux), of antiword"
            )

    def _convert_with_platform_tool(self, doc_path):
        """Probeer doc/docx te converteren met het platform-specifieke gereedschap.
        
        Returns tekst als string, of None als geen tool beschikbaar is.
        """
        import platform as _platform
        system = _platform.system()
        
        # macOS: textutil
        if system == "Darwin":
            try:
                result = subprocess.run(
                    ["textutil", "-convert", "txt", doc_path, "-stdout"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return result.stdout
            except (FileNotFoundError, subprocess.CalledProcessError):
                return None
        
        # Windows: Microsoft Word via COM automation
        if system == "Windows":
            try:
                import win32com.client
            except ImportError:
                print("⚠️  pywin32 is niet geïnstalleerd. Installeer met: pip install pywin32")
                return None
            try:
                from pathlib import Path
                abs_path = str(Path(doc_path).resolve())
                word = win32com.client.Dispatch("Word.Application")
                word.Visible = False
                try:
                    doc = word.Documents.Open(abs_path)
                    text = doc.Content.Text
                    doc.Close(False)
                    return text
                finally:
                    word.Quit()
            except ImportError:
                print("⚠️  pywin32 is niet geïnstalleerd. Installeer met: pip install pywin32")
                return None
            except Exception as e:
                print(
                    f"⚠️  Kan Microsoft Word niet starten: {e}\n"
                    f"    Zorg dat Microsoft Word geïnstalleerd is op deze computer.\n"
                    f"    Download Word via https://www.microsoft.com/microsoft-365"
                )
                return None
        
        # Linux: LibreOffice headless
        if system == "Linux":
            try:
                import tempfile
                from pathlib import Path
                with tempfile.TemporaryDirectory() as tmpdir:
                    subprocess.run(
                        ["libreoffice", "--headless", "--convert-to", "txt:Text",
                         "--outdir", tmpdir, doc_path],
                        capture_output=True,
                        check=True,
                    )
                    txt_file = Path(tmpdir) / (Path(doc_path).stem + ".txt")
                    if txt_file.exists():
                        return txt_file.read_text(encoding='utf-8')
                return None
            except (FileNotFoundError, subprocess.CalledProcessError):
                return None
        
        return None

    def parse_date(self, text):
        """Parse datum uit verschillende formaten"""
        if not text:
            return None

        text = text.strip()

        # Probeer verschillende datum patronen
        # ±1645, <1800, >1900, 30-06-1703, 23-04 / 07-05-1702, etc.
        patterns = [
            r"(\d{1,2}-\d{1,2}-\d{4})",  # 30-06-1703 (volledige datum eerst!)
            r"(\d{1,2}/\d{1,2}/\d{4})",  # 30/06/1703
            r"(\d{4})/(\d{4})",  # 1786/1787 (slash-jaar: "tussen jaar1 en jaar2")
            r"([<>±]?\s*\d{4})",  # ±1645, <1800, >1900, of 1645
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                # Slash-jaar patroon: twee capture groups → GEDCOM "BET x AND y"
                if match.lastindex == 2:
                    return f"BET {match.group(1)} AND {match.group(2)}"
                return match.group(1).strip()

        return None

    def _find_date_span_in_text(self, text):
        """Vind de originele tekst-span van de datum in de input string.
        Retourneert (start, end) indices of None als geen datum gevonden."""
        if not text:
            return None
        patterns = [
            r"\d{1,2}-\d{1,2}-\d{4}",  # 30-06-1703
            r"\d{1,2}/\d{1,2}/\d{4}",  # 30/06/1703
            r"\d{4}/\d{4}",  # 1786/1787
            r"[<>±]?\s*\d{4}",  # ±1645, <1800, >1900, 1645
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.start(), match.end()
        return None

    def parse_place_date(self, text):
        """Parse combinatie van plaats en datum"""
        if not text:
            return None, None

        # Zoek datum
        date = self.parse_date(text)

        # Plaats is meestal voor de datum
        place = None
        if date:
            # Gebruik de originele tekst-span om de plaats te bepalen
            span = self._find_date_span_in_text(text)
            if span:
                parts = [text[:span[0]], text[span[1]:]]
            else:
                parts = text.split(date)
            if parts[0].strip():
                place = parts[0].strip()
                # Verwijder eventuele symbolen en prefixen aan het begin:
                # - Levenssymbolen: * △ † ▭
                # - Schuine streep als separator (bijv. "* / Δ Delft" → "/ Δ Delft")
                # - "en" prefix (bijv. "en △ Kekerdom" = "en gedoopt Kekerdom")
                # - "RK" (Rooms-Katholiek)
                place = re.sub(r"^[*/△†▭Δ]\s*", "", place)
                place = re.sub(r"^(?:en\s+)?(?:RK\s+)?[△Δ▭]\s*", "", place, flags=re.IGNORECASE)
                place = re.sub(r"^en\s+", "", place, flags=re.IGNORECASE)
        else:
            place = text.strip()
            place = re.sub(r"^[*/△†▭Δ]\s*", "", place)
            place = re.sub(r"^(?:en\s+)?(?:RK\s+)?[△Δ▭]\s*", "", place, flags=re.IGNORECASE)
            place = re.sub(r"^en\s+", "", place, flags=re.IGNORECASE)

        # Filter ongewenste plaats-woorden
        if place and place.lower() in ["met", "als", "met name"]:
            place = None

        # Trim trailing commas en symbolen
        if place:
            # Verwijder doop-suffix achteraan (bijv. "Nieuwe Kraayert, Δ RK" of "Ovezande ±1801, Δ Ovezande")
            # Alles vanaf ", Δ" of ", △" is doop-info, niet geboorteplaats
            place = re.sub(r',?\s*(?:[A-Z]{2}\s+)?[△Δ].*$', '', place).strip()
            place = place.rstrip(",.;-<>")
            place = place.lstrip("<>")
            # Verwijder lege plaatsen
            if place in [">", "<", ""]:
                place = None

        return place, date

    def parse_person_header(self, line):
        """Parse de header regel van een persoon"""
        # Patroon: "III.1 Jan Thomassen (Joannes Thomae) (van den BRUNCKOM), zn. van II.1 [128]"
        # Of: "I.1 Joannes Thomissen [512]"
        # Of: "IV. 1. Thomas Jans" (met spatie tussen IV. en 1.)

        # Extract generation ID
        # Patroon kan zijn "VII.5 ", "VII.5. " of "VII. 5. " (met optionele spatie en punt)
        gen_match = re.match(r"^([IVX]+)\.\s*(\d+)\.?\s+(.+)$", line)
        if not gen_match:
            return None

        # Generatie ID zonder spaties: "IV.1" in plaats van "IV. 1"
        gen_id = f"{gen_match.group(1)}.{gen_match.group(2)}"
        rest = gen_match.group(3)

        # Extract reference number [xxx]
        ref_match = re.search(r"\[(\d+)\]", rest)
        ref_num = ref_match.group(1) if ref_match else None

        # Extract parent reference (zn. van of dr. van)
        parent_match = re.search(r"(?:zn\.|dr\.)\s+van\s+([IVX]+\.\d+)", rest)
        parent_ref = parent_match.group(1) if parent_match else None

        # Extract name (alles voor de komma of [ref])
        name_part = rest

        # Verwijder eerst de parent reference uit de tekst
        if parent_match:
            # Vind positie van "zn. van" of "dr. van"
            parent_pos = rest.find("zn. van") if "zn. van" in rest else rest.find("dr. van")
            if parent_pos > 0:
                name_part = rest[:parent_pos].strip()
                # Verwijder ook een eventueel onafgesloten '(' voor "zn. van"
                # Bijv. "(zn. van VIII.2)" laat "Naam (" achter
                name_part = name_part.rstrip('(').strip()

        # Verwijder het referentienummer
        if ref_match:
            name_part = re.sub(r"\[\d+\]", "", name_part).strip()

        # Detecteer omgekeerde naamvolgorde: "ACHTERNAAM, Voornamen"
        # Bijv. "COPPENS, Wilhelmina Johanna" → herorden naar "Wilhelmina Johanna COPPENS"
        if "," in name_part:
            _first_comma = name_part.index(',')
            _before_comma = name_part[:_first_comma].strip()
            _after_comma = name_part[_first_comma + 1:].strip()
            if re.match(r'^[A-Z]{2,}$', _before_comma) and _after_comma:
                name_part = f"{_after_comma} {_before_comma}"

        # Neem alles voor de EERSTE komma die NIET binnen haakjes staat
        # Bijv. "(Remi, Rum) Thomassen, zn." → knipt bij ", zn." maar NIET bij ", Rum"
        if "," in name_part:
            depth = 0
            for i, ch in enumerate(name_part):
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                elif ch == ',' and depth == 0:
                    name_part = name_part[:i].strip()
                    break

        # Bepaal geslacht
        sex = None
        if "zn. van" in rest:
            sex = "M"
        elif "dr. van" in rest:
            sex = "F"

        person = Person(gen_id, ref_num)
        person.name = self.normalize_name(name_part.strip())
        person.parent_ref = parent_ref
        person.sex = sex

        return person

    def parse_spouse_parents(self, spouse_info):
        """Parse ouders uit spouse info string"""
        # Patroon: "dr. van Benignus Joseph Coppens en Cornelia Francisca Xaveria Story"
        # Of: "zn. van [vader] en [moeder]"

        # Zoek "zn. van" / "dr. van" en splits daarna op het eerste " en " BUITEN haakjes
        # Bijv: "Priem (landman en schepen van Ovezande) en Maria" → vader=Priem (...), moeder=Maria
        van_match = re.search(r"(?:zn\.|dr\.)\s+van\s+", spouse_info, re.IGNORECASE)
        if not van_match:
            return None, None
        rest_after_van = spouse_info[van_match.end():]
        _depth_sp = 0
        _en_pos = None
        for _i_sp, _c_sp in enumerate(rest_after_van):
            if _c_sp == '(':
                _depth_sp += 1
            elif _c_sp == ')':
                _depth_sp -= 1
            elif _depth_sp == 0 and rest_after_van[_i_sp:_i_sp+4] == ' en ':
                _en_pos = _i_sp
                break
        parent_match = _en_pos is not None  # use as boolean flag
        if parent_match:
            father_name = rest_after_van[:_en_pos].strip()
            _mother_rest = rest_after_van[_en_pos+4:]
            # Trim moeder tot eerste komma buiten haakjes
            _depth_m = 0
            _comma_pos = len(_mother_rest)
            for _j_m, _cm in enumerate(_mother_rest):
                if _cm == '(':
                    _depth_m += 1
                elif _cm == ')':
                    _depth_m -= 1
                elif _cm == ',' and _depth_m == 0:
                    _comma_pos = _j_m
                    break
            mother_name = _mother_rest[:_comma_pos].strip()
        if parent_match:

            # Verwijder referentienummers [xx] uit namen
            father_name = re.sub(r'\s*\[\d+\]\s*', '', father_name).strip()
            mother_name = re.sub(r'\s*\[\d+\]\s*', '', mother_name).strip()

            # Verwijder BS (burgerlijke stand) referenties
            # Bijvoorbeeld: "(BS Bemmel 1923 O 69)" of "(Bs Beuningen 1911 O 45)"
            # Inclusief eventuele spatie ervoor
            father_name = re.sub(r'\s*\(BS\s+[^)]+\)', '', father_name, flags=re.IGNORECASE).strip()
            mother_name = re.sub(r'\s*\(BS\s+[^)]+\)', '', mother_name, flags=re.IGNORECASE).strip()

            # Verwijder geboorte/sterfte info (*, †) uit namen
            # Bijv. "Jan Wilbers, * Cuyk" → "Jan Wilbers"
            father_name = re.sub(r',?\s*[*†△▭].*$', '', father_name).strip()
            mother_name = re.sub(r',?\s*[*†△▭].*$', '', mother_name).strip()

            # Verwijder trailing punctuatie die kan overblijven
            father_name = father_name.rstrip('.,;:(')
            mother_name = mother_name.rstrip('.,;:(')

            # Verwijder alles na een punt gevolgd door een hoofdletter of cijfer (nieuwe zin/info)
            # Maar ALLEEN buiten haakjes om te voorkomen dat "(tr. Cuijk)" wordt geknipt
            # Bijv. "Anna Catharina Teeuwen. Winkelierster. Molenstraat 84"
            # Vereist ≥3 kleine letters voor de punt om afkortingen als "mw.", "dhr.", "dr." te vermijden.
            # "A.W. Lensing" → geen match (initialen) ✓
            # "Teeuwen. Winkelierster" → match na "Teeuwen" ✓
            # "mw. Broeders. Gescheiden." → match na "Broeders", niet na "mw." ✓
            mother_name_outside = re.sub(r'\([^)]*\)', '', mother_name)
            period_match = re.search(r'[a-z]{3,}(\.\s+[A-Z0-9])', mother_name_outside)
            if period_match:
                dot_pos = period_match.start(1)
                mother_name = mother_name[:dot_pos + 1].strip().rstrip('.')

            father_name_outside = re.sub(r'\([^)]*\)', '', father_name)
            period_match = re.search(r'[a-z]{3,}(\.\s+[A-Z0-9])', father_name_outside)
            if period_match:
                dot_pos = period_match.start(1)
                father_name = father_name[:dot_pos + 1].strip().rstrip('.')

            # Verwijder eventueel nog openstaande haakjes
            father_name = father_name.rstrip('(').strip()
            mother_name = mother_name.rstrip('(').strip()

            # Verwijder eventuele extra info na de naam (zoals beroep, religie, etc.)
            # Stop bij bekende beroepen (", bakker" of " bakker" patroon)
            occupations_pattern = '|'.join(re.escape(occ) for occ in self.DUTCH_OCCUPATIONS)
            occ_regex = re.compile(rf',?\s+(?:{occupations_pattern})\b.*', re.IGNORECASE)
            father_name = occ_regex.sub('', father_name).strip()
            mother_name = occ_regex.sub('', mother_name).strip()

            # Strip ook parenthetical beroepsomschrijvingen (bijv. "(landman en schepen van Ovezande)")
            # Deze worden niet gevangen door occ_regex omdat het beroep na "(" staat, niet na spatie
            occ_paren_regex = re.compile(rf'\s*\([^)]*(?:{occupations_pattern})[^)]*\)', re.IGNORECASE)
            father_name = occ_paren_regex.sub('', father_name).strip()
            mother_name = occ_paren_regex.sub('', mother_name).strip()

            # Stop ook bij religie-afkortingen
            for stop_word in [". rk", ". ng", ". herv"]:
                if stop_word in mother_name.lower():
                    mother_name = mother_name[:mother_name.lower().index(stop_word)].strip()
                if stop_word in father_name.lower():
                    father_name = father_name[:father_name.lower().index(stop_word)].strip()

            # Slotpunctatie verwijderen (kan overblijven na beroep-strip)
            father_name = father_name.rstrip('.,;:(').strip()
            mother_name = mother_name.rstrip('.,;:(').strip()

            return father_name, mother_name

        return None, None

    def _parse_inline_children(self, rest):
        """Verwerk inline kindnamen na 'Hieruit ' (zonder dubbele punt).
        Bijv: 'Dieuweke, Menso' of 'Jonne Anne Kateriene * Roermond 04-05-1993'"""
        if not self.current_person:
            return
        # Splits op komma of " en " (maar niet binnen haakjes)
        parts = []
        depth = 0
        current = []
        i = 0
        while i < len(rest):
            ch = rest[i]
            if ch == '(':
                depth += 1
                current.append(ch)
            elif ch == ')':
                depth -= 1
                current.append(ch)
            elif depth == 0 and ch == ',':
                parts.append(''.join(current).strip())
                current = []
            elif depth == 0 and rest[i:i+4] == ' en ':
                parts.append(''.join(current).strip())
                current = []
                i += 3  # skip " en" (loop adds 1 more)
            else:
                current.append(ch)
            i += 1
        if current:
            parts.append(''.join(current).strip())

        marriage_num = self.current_marriage_num if self.current_marriage_num is not None else 1
        for part in parts:
            part = part.strip().rstrip('.,;:').strip()
            if not part or not re.search(r'[A-Za-z]', part):
                continue
            # Strip afsluitend haakje met locatie/notitie (bijv. "Marieke (Amsterdam)" → "Marieke")
            part = re.sub(r'\s*\([^)]*\)\s*$', '', part).strip()
            if not part:
                continue
            # Haal geboorte info op als aanwezig (* Roermond 04-05-1993)
            # Naam staat vóór *, geboorteinfo (plaats + datum) staat ná *
            birth_info = None
            if '*' in part:
                star_pos = part.index('*')
                birth_match = re.search(r'\*\s*([^,†]+)', part)
                if birth_match:
                    birth_str = birth_match.group(1).strip()
                    bplace, bdate = self.parse_place_date(birth_str)
                    if bplace or bdate:
                        birth_info = (bplace, bdate)
                part = part[:star_pos].strip()
            if not part or not re.search(r'[A-Za-z]', part):
                continue
            child_id = f"{self.current_person.generation_id}_child_{len(self.unnamed_children)+1}"
            child = Person(child_id, None)
            child.name = self.normalize_name(part)
            child.parent_ref = self.current_person.generation_id
            child.parent_marriage_num = self.current_marriage_num
            if birth_info:
                child.birth_place, child.birth_date = birth_info
            self.unnamed_children.append(child)
            self.current_person.children.append((child_id, marriage_num))

    def parse_line(self, line):
        """Parse een enkele regel"""
        line = line.strip()
        if not line:
            return

        # Check of dit een nieuwe persoon is (met optionele punt en spatie: "VII.5.", "VII.5 " of "VII. 5. ")
        # Sluit "VII.3 ZIE JAEGERS" stijl kruisverwijzingen uit (beginnen met ZIE na het ID)
        if re.match(r"^[IVX]+\.\s*\d+\.?\s+", line) and not re.match(r"^[IVX]+\.\s*\d+\.?\s+ZIE\b", line, re.IGNORECASE):
            # Sla vorige persoon op
            if self.current_person:
                self.persons[self.current_person.generation_id] = self.current_person

            # Parse nieuwe persoon
            self.current_person = self.parse_person_header(line)
            self.current_marriage = None
            self.in_children_section = False
            self.parsing_spouse_info = False
            self.met_seen = False
            self.current_marriage_num = 0
            self.current_child = None
            self.child_marriage_context = False
            self.current_child_spouse_stored = False
            return

        if not self.current_person:
            return

        # Parse geboren (*)
        if line.startswith("*"):
            rest = line[1:].strip()

            # ─── Splits de regel op event-symbolen: geboorte | doop | overlijden | begraving ───
            death_part = None
            burial_part = None
            baptism_part = None  # Doop op dezelfde * regel

            # Gecombineerde notaties: "* en △ Datum", "* / △ Datum", "*/△ Datum"
            # Betekenis: geboorte en doop op dezelfde datum/plaats
            combined_match = re.match(r'^(?:en\s+|/\s*)[△Δ]|^/[△Δ]', rest)
            if combined_match:
                after = rest[combined_match.end():].strip()
                if '†' in after:
                    p = after.split('†', 1)
                    after = p[0].strip().rstrip('.,')
                    death_part = p[1].strip()
                elif '▭' in after:
                    p = after.split('▭', 1)
                    after = p[0].strip().rstrip('.,')
                    burial_part = p[1].strip()
                # Check voor dubbele datum: "* / △ Appeldorn 14-05 / 26-05-1816"
                # (zelfde plaats, geboorte- en doopdatum verschillend)
                double_date_match = re.match(
                    r'^(.+?)\s+(\d{1,2}-\d{1,2}(?:-\d{2,4})?)\s*/\s*(\d{1,2}-\d{1,2}-\d{2,4})\s*$',
                    after
                )
                if double_date_match:
                    common_place = double_date_match.group(1).strip()
                    birth_date_str = double_date_match.group(2).strip()
                    bap_date_str = double_date_match.group(3).strip()
                    # Voeg jaar toe aan geboortedatum als alleen DD-MM opgegeven
                    if not re.search(r'-\d{4}$', birth_date_str):
                        year = re.search(r'\d{4}$', bap_date_str).group()
                        birth_date_str = f"{birth_date_str}-{year}"
                    rest = f"{common_place} {birth_date_str}"
                    baptism_part = f"{common_place} {bap_date_str}"
                else:
                    rest = after
                    baptism_part = after  # zelfde info voor geboorte en doop
            else:
                # Zoek positie van △/Δ, † en ▭
                chr_pos = min((rest.find(s) for s in ['△', 'Δ'] if s in rest), default=-1)
                dth_pos = rest.find('†') if '†' in rest else -1
                bur_pos = rest.find('▭') if '▭' in rest else -1

                if chr_pos != -1 and (dth_pos == -1 or chr_pos < dth_pos) and (bur_pos == -1 or chr_pos < bur_pos):
                    # △ komt vóór †/▭: splits eerst op △
                    # Bijv. "* Erlecom, △ Kekerdom 10-04-1712, gett. X, † Ooij 1827"
                    rest = rest[:chr_pos].strip().rstrip('.,')
                    after_chr = line[1:].strip()[chr_pos + 1:].strip()  # alles na △
                    if '†' in after_chr:
                        p = after_chr.split('†', 1)
                        baptism_part = p[0].strip().rstrip('.,')
                        death_part = p[1].strip()
                    elif '▭' in after_chr:
                        p = after_chr.split('▭', 1)
                        baptism_part = p[0].strip().rstrip('.,')
                        burial_part = p[1].strip()
                    else:
                        baptism_part = after_chr
                elif dth_pos != -1 and (bur_pos == -1 or dth_pos < bur_pos):
                    # Geen △ eerder, wel †
                    parts = rest.split('†', 1)
                    rest = parts[0].strip().rstrip('.,')
                    death_part = parts[1].strip()
                elif bur_pos != -1:
                    # Alleen ▭
                    parts = rest.split('▭', 1)
                    rest = parts[0].strip().rstrip('.,')
                    burial_part = parts[1].strip()

            # Splits geboorte info van huwelijks info op dezelfde regel
            # Bijv. "Breda, tr. Goirle 23-08-1991met" → rest = "Breda"
            _tr_split = re.split(r',?\s*\b(?:Otr?|Tr)\.\s+', rest, maxsplit=1, flags=re.IGNORECASE)
            if len(_tr_split) > 1:
                rest = _tr_split[0].strip().rstrip('.,')

            place, date = self.parse_place_date(rest)

            # Bepaal waar we deze info opslaan
            if self.in_children_section and self.current_child and not self.current_child_spouse_stored:
                # Dit is een kind zonder generatie ID - sla geboorte info op
                self.current_child.birth_place = place
                self.current_child.birth_date = date
            elif self.in_children_section and self.current_child and self.current_child_spouse_stored and self.current_child.marriages:
                # Spouse van kind: geboorte info na partner naam
                self.current_child.marriages[-1].spouse_birth_place = place
                self.current_child.marriages[-1].spouse_birth_date = date
                # Parse ouders van partner
                full_rest = line[1:].strip()
                father_name, mother_name = self.parse_spouse_parents(full_rest)
                if father_name and mother_name:
                    self.current_child.marriages[-1].spouse_father_name = father_name
                    self.current_child.marriages[-1].spouse_mother_name = mother_name
            elif self.in_children_section:
                # Negeer - kinderen sectie maar geen current_child
                pass
            elif self.parsing_spouse_info and self.current_marriage:
                # Dit is partner geboorte info
                self.current_marriage.spouse_birth_place = place
                self.current_marriage.spouse_birth_date = date

                # Parse ouders van partner indien aanwezig op deze regel
                # Bijvoorbeeld: "* Den Haag 18-05-1955, dr. van Benignus Joseph Coppens en Cornelia Francisca Xaveria Story"
                full_rest = line[1:].strip()  # Volledige regel na het * symbool
                father_name, mother_name = self.parse_spouse_parents(full_rest)
                if father_name and mother_name:
                    self.current_marriage.spouse_father_name = father_name
                    self.current_marriage.spouse_mother_name = mother_name
            else:
                # Dit is de huidige persoon
                self.current_person.birth_place = place
                self.current_person.birth_date = date

            # Parse doop info als die op dezelfde * regel stond (bijv. "* Erlecom, △ Kekerdom 10-04-1712")
            if baptism_part:
                # Verwerk gett./get. getuigen in de doopinfo
                bap_place_date_str, bap_witnesses = self.parse_witnesses(baptism_part)
                if not bap_witnesses:
                    bap_place_date_str = baptism_part
                bap_place, bap_date = self.parse_place_date(bap_place_date_str)
                if self.in_children_section and self.current_child and not self.current_child_spouse_stored:
                    self.current_child.baptism_place = bap_place
                    self.current_child.baptism_date = bap_date
                    if bap_witnesses:
                        self.current_child.baptism_witnesses = bap_witnesses
                elif self.in_children_section and self.current_child and self.current_child_spouse_stored and self.current_child.marriages:
                    self.current_child.marriages[-1].spouse_baptism_place = bap_place
                    self.current_child.marriages[-1].spouse_baptism_date = bap_date
                elif self.parsing_spouse_info and self.current_marriage:
                    self.current_marriage.spouse_baptism_place = bap_place
                    self.current_marriage.spouse_baptism_date = bap_date
                elif not self.in_children_section and not self.parsing_spouse_info:
                    self.current_person.baptism_place = bap_place
                    self.current_person.baptism_date = bap_date
                    if bap_witnesses:
                        self.current_person.baptism_witnesses = bap_witnesses

            # Parse sterfte info als die op dezelfde regel staat
            if death_part:
                # Splits death_part op ▭ als die erin zit
                # Bijv: "Huissen 19-08-1791 (inwendige kwaal) en ▭ aldaar 25-08-1791"
                # Bijv: "Duiven 26-09-1944 tgv een granaatontploffing, ▭ Duiven 28-09-1944"
                # Bijv: "en ▭ Kekerdom 18-11 / 22-11-1753" († en ▭ patroon)
                if '▭' in death_part:
                    bur_split = re.split(r'(?:,?\s*(?:en\s+)?|;\s*)▭\s*', death_part, maxsplit=1)
                    death_part_clean = bur_split[0].strip().rstrip('.,;')
                    if len(bur_split) > 1:
                        burial_extra = bur_split[1].strip()
                        # "aldaar" verwijst naar de overlijdensplaats
                        if burial_extra.startswith('aldaar'):
                            death_place_tmp, _ = self.parse_place_date(death_part_clean)
                            burial_extra = burial_extra.replace('aldaar', death_place_tmp or '', 1).strip()
                        
                        # "† en ▭ Plaats DD-MM / DD-MM-YYYY" patroon:
                        # Overlijden en begraven op dezelfde plaats, twee datums gescheiden door /
                        # Bijv: "† en ▭ Kekerdom 18-11 / 22-11-1753"
                        if not death_part_clean or death_part_clean.lower() in ('en', ''):
                            # death_part was leeg na strip → "† en ▭" patroon
                            # Check of burial_extra een "DD-MM / DD-MM-YYYY" bevat
                            dual_date = re.search(r'(\d{1,2}-\d{1,2})\s*/\s*(\d{1,2}-\d{1,2}-\d{4})', burial_extra)
                            if dual_date:
                                # Eerste datum = overlijden, tweede = begraven
                                death_date_str = dual_date.group(1)
                                burial_date_str = dual_date.group(2)
                                # Voeg jaar toe aan overlijdensdatum
                                year = re.search(r'\d{4}$', burial_date_str).group()
                                death_date_str = f"{death_date_str}-{year}"
                                # Extract plaats (alles voor de eerste datum)
                                place_str = burial_extra[:dual_date.start()].strip().rstrip('.,;')
                                # Strip alles na de tweede datum
                                burial_extra_clean = f"{place_str} {burial_date_str}".strip()
                                death_part_clean = f"{place_str} {death_date_str}".strip()
                                burial_extra = burial_extra_clean
                        
                        if not burial_part:
                            burial_part = burial_extra
                    # Handle "en ▭" case where death_part starts with "en "
                    death_part_clean = re.sub(r'^en\s+', '', death_part_clean).strip()
                    death_part = death_part_clean

                death_place, death_date = self.parse_place_date(death_part)
                if self.in_children_section and self.current_child and not self.current_child_spouse_stored:
                    self.current_child.death_place = death_place
                    self.current_child.death_date = death_date
                elif self.in_children_section and self.current_child and self.current_child_spouse_stored and self.current_child.marriages:
                    self.current_child.marriages[-1].spouse_death_place = death_place
                    self.current_child.marriages[-1].spouse_death_date = death_date
                elif self.parsing_spouse_info and self.current_marriage:
                    self.current_marriage.spouse_death_place = death_place
                    self.current_marriage.spouse_death_date = death_date
                elif not self.in_children_section:
                    self.current_person.death_place = death_place
                    self.current_person.death_date = death_date

            # Parse begrafenis info als die op dezelfde regel staat (bijv. "* ±1672. ▭ Kekerdom 18-04-1723")
            if burial_part:
                burial_place, burial_date = self.parse_place_date(burial_part)
                if self.in_children_section and self.current_child and not self.current_child_spouse_stored:
                    self.current_child.burial_place = burial_place
                    self.current_child.burial_date = burial_date
                elif self.in_children_section and self.current_child and self.current_child_spouse_stored and self.current_child.marriages:
                    # Spouse van kind: * regel na partner naam
                    self.current_child.marriages[-1].spouse_burial_place = burial_place
                    self.current_child.marriages[-1].spouse_burial_date = burial_date
                elif self.parsing_spouse_info and self.current_marriage:
                    self.current_marriage.spouse_burial_place = burial_place
                    self.current_marriage.spouse_burial_date = burial_date
                elif not self.in_children_section and not self.parsing_spouse_info:
                    self.current_person.burial_place = burial_place
                    self.current_person.burial_date = burial_date

            # Check of er huwelijks info op dezelfde regel staat
            # Bijvoorbeeld: "* ... † ... Tr. plaats datum met"
            if self.in_children_section and self.current_child:
                # Kind met huwelijks info op geboortegel: "* R'dam 12-04-1950, tr. Breda 05-09-1968 met"
                marriage_match = re.search(r"\b(Otr?\.|Tr\.)\s+(.+?)\s*met\s*$", line, re.IGNORECASE)
                if marriage_match:
                    place_date_str = marriage_match.group(2).strip()
                    m_place, m_date = self.parse_place_date(place_date_str)
                    marriage = Marriage()
                    marriage.marriage_place = m_place
                    marriage.marriage_date = m_date
                    self.current_child.marriages.append(marriage)
                    self.parsing_spouse_info = True
                    self.child_marriage_context = True
                    self.child_marriage_lines_seen = 0
            elif not self.in_children_section and not self.parsing_spouse_info:
                marriage_match = re.search(r"\b(Otr?\.|Tr\.)\s+(.+?)\s*met\s*$", line, re.IGNORECASE)
                if marriage_match:
                    # Start een nieuw huwelijk
                    self.current_marriage_num += 1
                    self.current_marriage = Marriage()
                    self.current_marriage.marriage_num = self.current_marriage_num
                    self.current_person.marriages.append(self.current_marriage)
                    self.parsing_spouse_info = True  # We verwachten partner naam op volgende regel

                    # Parse huwelijks datum en plaats
                    place_date_str = marriage_match.group(2).strip()
                    place, date = self.parse_place_date(place_date_str)
                    self.current_marriage.marriage_place = place
                    self.current_marriage.marriage_date = date

        # Parse gedoopt (△ of Δ)
        elif line.startswith("△") or line.startswith("Δ") or re.match(r'^RK\s+[△Δ]', line):
            rest = line.lstrip('△ΔRK ').strip()
            if line.startswith("RK"):
                rest = re.sub(r'^RK\s+[△Δ]\s*', '', line).strip()
            else:
                rest = line[1:].strip()
            
            # ─── Splits op †/▭ in de HELE rest (ook na getuigen/;) ───
            death_part = None
            burial_part = None
            
            # Zoek †/▭ posities in de hele rest string
            dth_pos = rest.find('†')
            bur_pos = rest.find('▭')
            
            if dth_pos != -1 and (bur_pos == -1 or dth_pos < bur_pos):
                # △ ... † ... [▭ ...]
                after_death = rest[dth_pos + 1:].strip()
                rest = rest[:dth_pos].strip().rstrip('.,;')
                if '▭' in after_death:
                    p = after_death.split('▭', 1)
                    death_part = p[0].strip().rstrip('.,;')
                    burial_part = p[1].strip()
                else:
                    death_part = after_death
            elif bur_pos != -1:
                # △ ... ▭ ... (geen †)
                # Alles na ▭ (inclusief na ;) is burial info
                burial_part_raw = rest[bur_pos + 1:].strip()
                rest = rest[:bur_pos].strip().rstrip('.,;')
                burial_part = burial_part_raw
            
            # Parse de doop info (verwijder getuigen)
            bap_place_date_str, bap_witnesses = self.parse_witnesses(rest)
            if not bap_witnesses:
                bap_place_date_str = rest
            
            bap_place, bap_date = self.parse_place_date(bap_place_date_str)
            
            # In kinderen sectie: markeer dat current_child een doop heeft en sla info op
            if self.in_children_section and self.current_child and not self.current_child_spouse_stored:
                self.current_child_has_baptism = True
                # Reset child_marriage_context omdat Δ altijd een nieuw kind aangeeft
                self.child_marriage_context = False
                self.child_marriage_lines_seen = 0
                self.current_child.baptism_place = bap_place
                self.current_child.baptism_date = bap_date
                if bap_witnesses:
                    self.current_child.baptism_witnesses = bap_witnesses
                # Sla overlijden/begraven op voor het kind
                if death_part:
                    dplace, ddate = self.parse_place_date(death_part)
                    self.current_child.death_place = dplace
                    self.current_child.death_date = ddate
                if burial_part:
                    bplace, bdate = self.parse_place_date(burial_part)
                    self.current_child.burial_place = bplace
                    self.current_child.burial_date = bdate
            elif self.in_children_section and self.current_child and self.current_child_spouse_stored and self.current_child.marriages:
                # Doop info voor de partner van een kind
                self.current_child.marriages[-1].spouse_baptism_place = bap_place
                self.current_child.marriages[-1].spouse_baptism_date = bap_date
                if death_part:
                    dplace, ddate = self.parse_place_date(death_part)
                    self.current_child.marriages[-1].spouse_death_place = dplace
                    self.current_child.marriages[-1].spouse_death_date = ddate
                if burial_part:
                    bplace, bdate = self.parse_place_date(burial_part)
                    self.current_child.marriages[-1].spouse_burial_place = bplace
                    self.current_child.marriages[-1].spouse_burial_date = bdate
            elif self.parsing_spouse_info and self.current_marriage:
                # Doop info voor partner
                self.current_marriage.spouse_baptism_place = bap_place
                self.current_marriage.spouse_baptism_date = bap_date
                if death_part:
                    dplace, ddate = self.parse_place_date(death_part)
                    self.current_marriage.spouse_death_place = dplace
                    self.current_marriage.spouse_death_date = ddate
                if burial_part:
                    bplace, bdate = self.parse_place_date(burial_part)
                    self.current_marriage.spouse_burial_place = bplace
                    self.current_marriage.spouse_burial_date = bdate
            elif not self.in_children_section and not self.parsing_spouse_info:
                self.current_person.baptism_place = bap_place
                self.current_person.baptism_date = bap_date
                if bap_witnesses:
                    self.current_person.baptism_witnesses = bap_witnesses
                if death_part:
                    dplace, ddate = self.parse_place_date(death_part)
                    self.current_person.death_place = dplace
                    self.current_person.death_date = ddate
                if burial_part:
                    bplace, bdate = self.parse_place_date(burial_part)
                    self.current_person.burial_place = bplace
                    self.current_person.burial_date = bdate

        # Parse overleden (†)
        elif line.startswith("†"):
            rest = line[1:].strip()
            
            # ─── Splits op ▭ als die in de rest voorkomt ───
            # Patronen: "† en ▭ Kekerdom 18-11/22-11-1753"
            #           "† Huissen 19-08-1791 en ▭ aldaar 25-08-1791"
            #           "† Duiven 26-09-1944, ▭ Duiven 28-09-1944"
            #           "† Duiven 05-11, ▭ 07-11-1949"
            #           "† Rijssen 08-09-1969 en ▭ aldaar 11-09-1969"
            burial_part = None
            if '▭' in rest:
                # Split op ▭, met optionele "en " of ", " ervoor
                bur_split = re.split(r'(?:,?\s*(?:en\s+)?|;\s*)▭\s*', rest, maxsplit=1)
                rest = bur_split[0].strip().rstrip('.,;')
                if len(bur_split) > 1:
                    burial_raw = bur_split[1].strip()
                    # "aldaar" verwijst naar de overlijdensplaats
                    if burial_raw.startswith('aldaar'):
                        # Parse de death part eerst om de plaats te krijgen
                        death_place_tmp, _ = self.parse_place_date(rest)
                        burial_raw = burial_raw.replace('aldaar', death_place_tmp or '', 1).strip()
                    burial_part = burial_raw
            
            # "† en ▭" patroon: rest kan beginnen met "en " → strip dat
            rest = re.sub(r'^en\s+', '', rest).strip()
            
            place, date = self.parse_place_date(rest)

            # Bepaal waar we deze info opslaan
            if self.in_children_section and self.current_child and not self.current_child_spouse_stored:
                # Dit is een kind zonder generatie ID - sla overleden info op
                self.current_child.death_place = place
                self.current_child.death_date = date
                if burial_part:
                    bplace, bdate = self.parse_place_date(burial_part)
                    self.current_child.burial_place = bplace
                    self.current_child.burial_date = bdate
            elif self.in_children_section:
                # Negeer - kinderen sectie maar geen current_child (of partner-info)
                pass
            elif self.parsing_spouse_info and self.current_marriage:
                # Dit is partner overleden info
                self.current_marriage.spouse_death_place = place
                self.current_marriage.spouse_death_date = date
                if burial_part:
                    bplace, bdate = self.parse_place_date(burial_part)
                    self.current_marriage.spouse_burial_place = bplace
                    self.current_marriage.spouse_burial_date = bdate
            else:
                # Dit is de huidige persoon
                self.current_person.death_place = place
                self.current_person.death_date = date
                if burial_part:
                    bplace, bdate = self.parse_place_date(burial_part)
                    self.current_person.burial_place = bplace
                    self.current_person.burial_date = bdate

        # Parse begraven (▭)
        # Herken ook regels als "infans (Pauli Rutjens) ▭ Zyfflich 07-11-1751"
        elif "begr." in line.lower() or line.startswith("▭") or ('▭' in line and not line.startswith("*") and not line.startswith("△") and not line.startswith("Δ") and not line.startswith("†")):
            # "begr. RK Beers 14-02-1731" of "▭ Zyfflich 25-07-1795"
            # of "infans (Pauli Rutjens) ▭ Zyfflich 07-11-1751"
            if '▭' in line:
                rest = line.split('▭', 1)[1].strip()
            else:
                rest = re.sub(r"begr\.?\s*", "", line, flags=re.IGNORECASE).strip()
            place, date = self.parse_place_date(rest)

            if self.in_children_section and self.current_child and not self.current_child_spouse_stored:
                self.current_child.burial_place = place
                self.current_child.burial_date = date
            elif self.in_children_section and self.current_child and self.current_child_spouse_stored and self.current_child.marriages:
                # Begraven info voor de partner van een kind
                self.current_child.marriages[-1].spouse_burial_place = place
                self.current_child.marriages[-1].spouse_burial_date = date
            elif self.parsing_spouse_info and self.current_marriage:
                self.current_marriage.spouse_burial_place = place
                self.current_marriage.spouse_burial_date = date
            elif not self.in_children_section and not self.parsing_spouse_info:
                self.current_person.burial_place = place
                self.current_person.burial_date = date

        # Parse huwelijk of relatie
        elif (re.search(r"^(Relatie met|Ondertr\.|Otr?\.|Tr\.)", line, re.IGNORECASE) or
              re.search(r"\b(otr|ot)\.\s*/?\s*(tr\.?)", line, re.IGNORECASE)):
            # Als we in de kinderen sectie zitten, is dit een huwelijk van een kind
            if self.in_children_section:
                # Als current_child bestaat, maak een huwelijk aan voor dit kind
                if self.current_child:
                    # Parse huwelijksdatum en plaats uit de huidige regel
                    marriage_text = line
                    marriage_place, marriage_date = None, None

                    # Probeer plaats/datum te extraheren (bijv. "Tr. Beers 1758 met")
                    # Verwijder "Tr.", "met", etc.
                    # Eerst: strip volledige "Otr. / tr." of "Ondertr. / tr." prefix
                    clean_text = re.sub(r'^(?:ondertr\.?\s*/?\s*tr\.?|otr?\.?\s*/?\s*tr\.?|tr\.)\s*', '', marriage_text, flags=re.IGNORECASE)
                    clean_text = re.sub(r'\s+(met|with)\s*$', '', clean_text, flags=re.IGNORECASE).strip()
                    # Strip haakjes-inhoud (archiefbronnen)
                    clean_text = re.sub(r'\s*\([^)]*\)\s*$', '', clean_text).strip()

                    if clean_text:
                        # Herken dual-date patroon: "Plaats DD-MM/DD-MM-YYYY" of "Plaats DD-MM / DD-MM-YYYY"
                        dual_date_match = re.search(r'(\d{1,2}-\d{1,2})\s*/\s*(\d{1,2}-\d{1,2}-\d{4})', clean_text)
                        if dual_date_match:
                            eng_date_str = dual_date_match.group(1)
                            mar_date_str = dual_date_match.group(2)
                            year = re.search(r'\d{4}$', mar_date_str).group()
                            eng_date_str = f"{eng_date_str}-{year}"
                            place_str = clean_text[:dual_date_match.start()].strip().rstrip('.,;')
                            marriage_place = place_str if place_str else None
                            marriage_date = mar_date_str
                        else:
                            marriage_place, marriage_date = self.parse_place_date(clean_text)

                    # Extract getuigen voor child marriage
                    child_marriage_witnesses = []
                    paren_w = re.search(r'\(gett?\.\s*([^)]+)\)', marriage_text)
                    if paren_w:
                        _, child_marriage_witnesses = self.parse_witnesses("gett. " + paren_w.group(1))
                    elif re.search(r',\s*gett?\.\s*', marriage_text):
                        gp = re.split(r',\s*gett?\.\s*', marriage_text, maxsplit=1)
                        if len(gp) > 1:
                            wt = re.split(r',?\s*\bmet\b', gp[1], maxsplit=1)[0]
                            _, child_marriage_witnesses = self.parse_witnesses("gett. " + wt)
                    
                    # Maak Marriage object voor het kind
                    marriage = Marriage()
                    marriage.marriage_place = marriage_place
                    marriage.marriage_date = marriage_date
                    if child_marriage_witnesses:
                        marriage.witnesses = child_marriage_witnesses
                    self.current_child.marriages.append(marriage)
                    # We gaan de partner naam op de volgende regel verwachten
                    self.parsing_spouse_info = True
                    # Nieuw huwelijk begint: partner-opgeslagen vlag resetten
                    self.current_child_spouse_stored = False

                # Markeer dat we nu een huwelijk van een kind parsen
                # De volgende regels (partner naam, etc.) moeten worden genegeerd door child parsing
                self.child_marriage_context = True
                self.child_marriage_lines_seen = 0  # Reset counter
                # Houd current_child intact zodat we de partner kunnen toevoegen
                return

            # Anders is dit een huwelijk van de huidige persoon
            self.current_marriage_num += 1
            self.current_marriage = Marriage()
            self.current_marriage.marriage_num = self.current_marriage_num
            self.current_person.marriages.append(self.current_marriage)
            self.in_children_section = False
            self.parsing_spouse_info = True  # We gaan nu partner info parsen
            self.met_seen = bool(re.search(r'\bmet\b', line, re.IGNORECASE))

            # Parse datum en plaats
            # "Otr. / tr. als jongeman  NG Beers 23-04 / 07-05-1702"
            # "Tr. RK Beers 11-05-1727 (gett. ...)"
            # "Tr. RK Leuth 11-05-1765, gett. X, Y, met"
            # "Ondertr. / tr. Gendt 01-08/22-08-1697 met Maria VAN BERCK"
            
            # Extract huwelijksgetuigen (twee patronen)
            marriage_witnesses = []
            # Patroon 1: (gett. X en Y) of (gett. X, Y)
            paren_witness_match = re.search(r'\(gett?\.\s*([^)]+)\)', line)
            if paren_witness_match:
                _, marriage_witnesses = self.parse_witnesses("gett. " + paren_witness_match.group(1))
            # Patroon 2: , gett. X, Y, met (zonder haakjes)
            elif re.search(r',\s*gett?\.\s*', line):
                gett_part = re.split(r',\s*gett?\.\s*', line, maxsplit=1)
                if len(gett_part) > 1:
                    witness_text = re.split(r',?\s*\bmet\b', gett_part[1], maxsplit=1)[0]
                    _, marriage_witnesses = self.parse_witnesses("gett. " + witness_text)
            
            if marriage_witnesses:
                self.current_marriage.witnesses = marriage_witnesses
            
            # Extract plaats en datum
            place_date_match = re.search(
                r"(?:ondertr\.?\s*/?\s*tr\.?|otr?\.?\s*/?\s*tr\.?|tr\.)\s+(?:als\s+\w+\s+)?(.+?)(?:\(|gett?\.|met|$)", line, re.IGNORECASE
            )
            if place_date_match:
                place_date_str = place_date_match.group(1).strip()
                
                # Herken dual-date patroon voor Otr./tr.: "Plaats DD-MM/DD-MM-YYYY" of "Plaats DD-MM / DD-MM-YYYY"
                # Bijv: "RK Ooij en Persingen 19-10/07-11-1770" → engagement=19-10-1770, marriage=07-11-1770, place=RK Ooij en Persingen
                # Bijv: "Gendt 01-08/22-08-1697" → engagement=01-08-1697, marriage=22-08-1697, place=Gendt
                dual_date_match = re.search(r'(\d{1,2}-\d{1,2})\s*/\s*(\d{1,2}-\d{1,2}-\d{4})', place_date_str)
                if dual_date_match:
                    eng_date_str = dual_date_match.group(1)
                    mar_date_str = dual_date_match.group(2)
                    # Voeg jaar toe aan ondertrouw-datum als alleen DD-MM
                    year = re.search(r'\d{4}$', mar_date_str).group()
                    eng_date_str = f"{eng_date_str}-{year}"
                    # Extract plaats (alles voor de eerste datum)
                    place_str = place_date_str[:dual_date_match.start()].strip().rstrip('.,;')
                    self.current_marriage.marriage_place = place_str if place_str else None
                    self.current_marriage.marriage_date = mar_date_str
                    self.current_marriage.engagement_date = eng_date_str
                    self.current_marriage.engagement_place = place_str if place_str else None
                else:
                    place, date = self.parse_place_date(place_date_str)
                    self.current_marriage.marriage_place = place
                    self.current_marriage.marriage_date = date

            # Check of partner naam op dezelfde regel staat (na "met")
            # Bijvoorbeeld: "Ondertr. / tr. Gendt 01-08/22-08-1697 met Maria VAN BERCK [289]"
            spouse_inline_match = re.search(r'\bmet\s+(.+?)(?:\[|\(|$)', line, re.IGNORECASE)
            if spouse_inline_match:
                spouse_name = spouse_inline_match.group(1).strip()
                # Verwijder referentie nummers en extra spaties
                spouse_name = re.sub(r'\s*\[\d+\]\s*$', '', spouse_name)
                spouse_name = re.sub(r'\s*\(\d+\)\s*$', '', spouse_name)
                # Filter out divorce markers die geen echte naam zijn:
                # "en gesch. van", "en sch. 18-08-1933 van", "en gescheiden van", etc.
                # Match: (optioneel "en") + (optioneel datum) + scheidingswoord + (optioneel datum) + (optioneel "van")
                if not re.match(r'^(en\s+)?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\s+)?(sch\.|gesch\.?|gescheiden)(\s+\d{1,2}[-/]\d{1,2}[-/]\d{2,4})?(\s+van)?(\s+.*)?$', spouse_name, re.IGNORECASE):
                    if spouse_name and len(spouse_name) > 2:
                        self.current_marriage.spouse_name = self.normalize_name(spouse_name)
                        self.current_marriage.spouse_info = spouse_name

        # Check if this line starts with a marriage number like "(2)" or "(3)"
        # This indicates a new marriage ONLY if current marriage already has a spouse
        elif self.current_person and not self.in_children_section and \
             re.match(r'^\s*\((\d+)\)\s+', line):
            numbered_spouse_match = re.match(r'^\s*\((\d+)\)\s+(.+)', line)
            if numbered_spouse_match:
                marriage_num = int(numbered_spouse_match.group(1))
                # Only create new marriage if current marriage already has a spouse set
                # This handles cases like:
                #   Tr. met
                #   (1) First Spouse
                #   (2) Second Spouse  <- creates new marriage here
                if self.current_marriage and self.current_marriage.spouse_name:
                    # Current marriage already has spouse, so (2) must be a new marriage
                    self.current_marriage_num += 1
                    self.current_marriage = Marriage()
                    self.current_marriage.marriage_num = self.current_marriage_num
                    self.current_person.marriages.append(self.current_marriage)

            # Now parse the spouse name (for both new marriage and existing)
            if self.current_marriage and not self.current_marriage.spouse_name:
                # Skip URLs
                if "http://" in line or "https://" in line or "www." in line.lower():
                    return

                # Skip regels die te lang zijn
                if len(line) > 100:
                    return

                # Dit zou de partner kunnen zijn
                if not any(
                    keyword in line.lower()
                    for keyword in ["hieruit:", "uit (", "arch.", "beers", "cuijk", "wanroij", "schepenbanken", "http://", "https://", "www.", "zie"]
                ):
                    clean_name = line.strip()
                    clean_name = re.sub(r'^[•\-*†△▭]\s*', '', clean_name)
                    clean_name = re.sub(r'\s*\[\d+\]\s*$', '', clean_name)
                    clean_name = re.sub(r'^\s*\(\d+\)\s*', '', clean_name)
                    clean_name = re.split(r'[*†△▭]', clean_name)[0].strip()

                    if clean_name.upper() not in ["NN", "N.N."]:
                        if len(clean_name) < 3 or not re.search(r'[A-Za-z]', clean_name):
                            return

                    self.current_marriage.spouse_name = self.normalize_name(clean_name)
                    self.current_marriage.spouse_info = line

                    father_name, mother_name = self.parse_spouse_parents(line)
                    if father_name and mother_name:
                        self.current_marriage.spouse_father_name = father_name
                        self.current_marriage.spouse_mother_name = mother_name

        # Parse partner (regel na tr./otr.) - original logic for non-numbered spouses
        elif self.current_marriage and not self.current_marriage.spouse_name and \
             not re.match(r"^[IVX]+\.\d+", line) and not self.in_children_section:
            # Skip URLs (ook met leading whitespace)
            if "http://" in line or "https://" in line or "www." in line.lower():
                return

            # Skip regels die te lang zijn (waarschijnlijk notities, niet namen)
            if len(line) > 100:
                return

            # Dit zou de partner kunnen zijn
            # Simpele heuristiek: als het geen andere keyword bevat
            if not any(
                keyword in line.lower()
                for keyword in ["hieruit:", "uit (", "arch.", "beers", "cuijk", "wanroij", "schepenbanken", "http://", "https://", "www.", "zie"]
            ):
                # Verwijder referentie nummer [xxx] en huwelijksnummer (1), (2), etc. uit partner naam
                # Bijvoorbeeld: "(1) Maria ABEN [33]" -> "Maria ABEN"
                clean_name = line.strip()

                # Verwijder symbolen en extra informatie
                clean_name = re.sub(r'^[•\-*†△▭]\s*', '', clean_name)  # Verwijder symbolen aan begin
                clean_name = re.sub(r'\s*\[\d+\]\s*$', '', clean_name)  # Verwijder [xxx] aan het einde
                clean_name = re.sub(r'^\s*\(\d+\)\s*', '', clean_name)  # Verwijder (1) aan het begin

                # Verwijder alles na geboort/sterfte symbolen (waarschijnlijk data)
                clean_name = re.split(r'[*†△▭]', clean_name)[0].strip()

                # Skip als de naam te kort is (< 3 chars) of alleen cijfers/symbolen bevat
                # Maar maak uitzondering voor "NN" en "N.N." (nomen nescio = naam onbekend)
                if clean_name.upper() not in ["NN", "N.N."]:
                    if len(clean_name) < 3 or not re.search(r'[A-Za-z]', clean_name):
                        return
                    # "met" op een eigen regel is het signaal dat de partner naam volgt
                    if clean_name.lower() == "met":
                        self.met_seen = True
                        return
                    # Skip enkelvoudige Nederlandse voorzetsels/voegwoorden als partnernaam
                    if clean_name.lower() in {"van", "de", "den", "der", "het", "aan",
                                              "in", "op", "uit", "bij", "voor", "na", "als",
                                              "en", "om", "af", "tot", "te"}:
                        return

                # Wacht tot "met" is gezien voordat we een partnernaam accepteren
                if not self.met_seen:
                    return

                self.current_marriage.spouse_name = self.normalize_name(clean_name)
                self.current_marriage.spouse_info = line

                # Parse ouders van partner indien aanwezig
                father_name, mother_name = self.parse_spouse_parents(line)
                if father_name and mother_name:
                    self.current_marriage.spouse_father_name = father_name
                    self.current_marriage.spouse_mother_name = mother_name

        # Parse partner voor kinderen in kinderen sectie
        # Alleen als het LAATSTE huwelijk van het kind nog geen partnernaam heeft; anders valt de
        # regel door naar "elif self.in_children_section:" zodat het als nieuw kind wordt geparsed.
        elif (self.in_children_section and self.current_child and
              len(self.current_child.marriages) > 0 and
              not self.current_child.marriages[-1].spouse_name):
            # Het kind heeft een huwelijk maar nog geen partner naam
            child_marriage = self.current_child.marriages[-1]
            if not re.match(r"^[IVX]+\.\d+", line):
                # Skip URLs
                if "http://" in line or "https://" in line or "www." in line.lower():
                    return

                # Skip te lange regels
                if len(line) > 100:
                    return

                # Skip regels met keywords
                if not any(
                    keyword in line.lower()
                    for keyword in ["hieruit:", "uit (", "arch.", "beers", "wanroij", "schepenbanken", "http://", "https://", "www.", "zie", "nageslacht"]
                ):
                    clean_name = line.strip()

                    # Verwijder symbolen en referenties
                    clean_name = re.sub(r'^[•\-*†△▭]\s*', '', clean_name)
                    clean_name = re.sub(r'\s*\[\d+\]\s*$', '', clean_name)
                    clean_name = re.sub(r'^\s*\(\d+\)\s*', '', clean_name)
                    clean_name = re.split(r'[*†△▭]', clean_name)[0].strip()

                    # Check minimum lengte (met NN exceptie)
                    if clean_name.upper() not in ["NN", "N.N."]:
                        if len(clean_name) < 3 or not re.search(r'[A-Za-z]', clean_name):
                            return
                        # Skip enkelvoudige Nederlandse voorzetsels/voegwoorden
                        if clean_name.lower() in {"met", "van", "de", "den", "der", "het", "aan",
                                                  "in", "op", "uit", "bij", "voor", "na", "als",
                                                  "en", "om", "af", "tot", "te"}:
                            return

                    # Sla partner naam op
                    child_marriage.spouse_name = self.normalize_name(clean_name)
                    child_marriage.spouse_info = line

                    # Bewaar referentie voor eventuele "dr. van / zn. van" ouderregel op volgende regel
                    self.last_child_marriage = child_marriage

                    # Partner gevonden: zet vlag zodat * / △ / † hieronder niet de KIND-data overschrijven.
                    # current_child blijft intact zodat een eventueel volgend huwelijk (Tr.) voor hetzelfde
                    # kind een nieuwe Marriage kan aanmaken (bijv. "(2) Paul de Vries" na "(1) Claes Leenders").
                    self.parsing_spouse_info = False
                    self.child_marriage_context = False
                    self.current_child_spouse_stored = True
                    return

        # Parse kinderen sectie
        elif line.startswith("Hieruit:") or re.match(r"^Uit\s+\(\d+\)", line) or \
             re.match(r'^Uit\s+deze\b', line, re.IGNORECASE) or \
             (re.match(r'^Hieruit\s+\S', line, re.IGNORECASE) and self.current_person):
            self.in_children_section = True
            self.parsing_spouse_info = False  # Niet meer in partner info sectie
            self.child_marriage_context = False  # Reset huwelijk context
            self.current_child = None  # Reset current child voor nieuwe kinderen sectie
            self.current_child_has_baptism = False  # Reset doop flag voor nieuwe kinderen sectie
            self.current_child_spouse_stored = False  # Reset partner-opgeslagen vlag
            # Extract huwelijksnummer
            marriage_num_match = re.search(r"Uit\s+\((\d+)\)", line)
            if marriage_num_match:
                self.current_marriage_num = int(marriage_num_match.group(1))
            # "Hieruit X, Y, Z" → inline kind-lijst op dezelfde regel
            # Maar NIET als de regel eindigt op ":" (bijv. "Hieruit (Geneanet):" = sectie-header met bronvermelding)
            hieruit_inline = re.match(r'^Hieruit\s+(\S.+)', line, re.IGNORECASE)
            if hieruit_inline and not line.startswith("Hieruit:") and not line.rstrip().endswith(":"):
                self._parse_inline_children(hieruit_inline.group(1))

        # Parse kind
        elif self.in_children_section:
            # Check of dit ouder-info is voor de partner van het vorige kind
            # Bijv. "dr. van dhr. van Seeters en mw. Broeders. Gescheiden."
            if self.last_child_marriage and re.match(r'^\s*(dr\.|zn\.)\s+van\b', line, re.IGNORECASE):
                father_name, mother_name = self.parse_spouse_parents(line)
                if father_name:
                    self.last_child_marriage.spouse_father_name = father_name
                if mother_name:
                    self.last_child_marriage.spouse_mother_name = mother_name
                self.last_child_marriage = None
                return
            self.last_child_marriage = None  # Reset als andere regel volgt

            # Skip URLs (http://, https://, etc.)
            if line.startswith("http://") or line.startswith("https://"):
                return

            # Skip cross-reference regels als "VII.3 ZIE JAEGERS" die niet als persoonshoofd worden herkend
            # (omdat de ZIE-exclusie ze doorlaat naar de kinderen-sectie)
            if re.match(r"^[IVX]+\.\s*\d+\.?\s+ZIE\b", line, re.IGNORECASE):
                return

            # "Hieruit X, Y" zonder dubbele punt binnen kinderensectie → inline kindlijst, geen kindnaam
            # Maar NIET als de regel eindigt op ":" (bijv. "Hieruit (Geneanet):" = sectie-header met bronvermelding)
            hieruit_inline2 = re.match(r'^Hieruit\s+(\S.+)', line, re.IGNORECASE)
            if hieruit_inline2 and not line.startswith("Hieruit:") and not line.rstrip().endswith(":"):
                self._parse_inline_children(hieruit_inline2.group(1))
                return

            # "Kinderen X, Y, Z" of "Kinderen: X, Y" → kleinkinderen van huidige persoon
            # Ook: "Plaatsnaam. Kinderen X, Y" (plaatsnaam-notitie + kindlijst)
            # Deze zijn GEEN directe kinderen van current_person → sla op als notitie bij huidig kind
            kinderen_line = re.match(r'^(?:.*?\.\s+)?Kinderen:?\s+(\S.*)', line, re.IGNORECASE)
            if kinderen_line:
                rest = kinderen_line.group(1).strip()
                # "Kinderen en kleinkinderen" is een notitie-kop, geen kindlijst
                if not re.match(r'^en\b', rest, re.IGNORECASE):
                    target = self.current_child if self.current_child else self.current_person
                    if target:
                        target.notes.append(line.strip())
                # Zorg dat child_marriage_context altijd gereset wordt (bijv. lang archief-tekst
                # die toevallig "Kinderen Hieruit" bevat mag geen context laten hangen)
                self.child_marriage_context = False
                return
            # Kale "Kinderen" regel (geen namen) → skip
            if re.match(r'^Kinderen[.,]?\s*$', line, re.IGNORECASE):
                return

            # Check of het geboorte/sterfte info is voor het huidige kind, maar met een plaatsnaam vóór de *
            # Bijv: "Cuijk * 27-05-1874, † 02-07-1874" (andere notatie dan "* Cuijk 27-05-1874")
            if self.current_child and '*' in line and not line.startswith('*'):
                star_pos = line.index('*')
                before_star = line[:star_pos].strip().rstrip(',')
                # Als het deel vóór * kort is en geen HOOFDLETTERNAAM bevat → geboorte info voor huidig kind
                if before_star and len(before_star.split()) <= 3 and not re.search(r'[A-Z]{3,}', before_star):
                    birth_match = re.search(r'\*\s*([^,†]+)', line)
                    if birth_match:
                        birth_str = f"{before_star} {birth_match.group(1).strip()}".strip()
                        place, date = self.parse_place_date(birth_str)
                        if place or date:
                            self.current_child.birth_place = place
                            self.current_child.birth_date = date
                    if '†' in line:
                        death_match = re.search(r'†\s*([^,*]+)', line)
                        if death_match:
                            death_place, death_date = self.parse_place_date(death_match.group(1).strip())
                            self.current_child.death_place = death_place
                            self.current_child.death_date = death_date
                    return

            # Kijk of het een verwijzing naar een kind is
            # "Jan (Joannes) Thomassen, 1703, zie III.1"
            # Of: "• Agnes RUTJES, 1803, zie V.10" (met bullet point)
            child_match = re.search(r"zie\s+([IVX]+\.\d+)", line)
            if child_match:
                child_ref = child_match.group(1)
                # Sla kind op met huwelijksnummer: (child_ref, marriage_num)
                # Als marriage_num None is (geen "Uit (X):"), dan is het uit "Hieruit:" (eerste huwelijk)
                marriage_num = self.current_marriage_num if self.current_marriage_num is not None else 1
                
                # Duplicaat-fix: als vorige regel ALLEEN naam bevat en huidige regel plaats/jaar + zie
                # (geen andere naam op huidig regel), dan vervang het unnamed child door referentie.
                # Bijv: "Hermina RUTJES" (vorige) + "Bergharen 1820, zie V.14" (huidig) → één persoon
                # Maar "Remigius Jozef Maria PELT, zie IX.30" (huidig, met naam) → twee personen
                before_zie = line[:line.index('zie')].strip().rstrip(',;')
                has_name_before_zie = bool(re.search(r'[A-Z][A-Za-z\s]+[A-Z]', before_zie))
                
                if (not has_name_before_zie and  # Huidig regel heeft geen naam voor "zie"
                    self.current_child and 
                    self.current_child.generation_id in [ref for ref, _ in self.current_person.children] and
                    not self.current_child.birth_date and not self.current_child.baptism_date and
                    not self.current_child.death_date and not self.current_child.burial_date and
                    not self.current_child.marriages):
                    # Vorige unnamed child heeft geen data en huidig regel heeft geen naam
                    # → waarschijnlijk plaats-info voor vorige child = duplicaat
                    # Verwijder unnamed child en gebruik referentie
                    self.current_person.children = [
                        (ref, mn) for ref, mn in self.current_person.children 
                        if ref != self.current_child.generation_id
                    ]
                    self.unnamed_children = [
                        uc for uc in self.unnamed_children 
                        if uc.generation_id != self.current_child.generation_id
                    ]
                
                self.current_person.children.append((child_ref, marriage_num))
                self.current_child = None  # Reset current child
                self.current_child_has_baptism = False  # Reset doop flag
                self.child_marriage_context = False  # Reset huwelijk context
                self.current_child_spouse_stored = False  # Reset partner-opgeslagen vlag
            elif (re.match(r"^[A-Z•(]", line) or re.match(r"^\d+\.?\s*\t", line)) and not any(
                keyword in line.lower()
                for keyword in ["arch.", "beers", "wanroij", "ibid", "error", "generatie", "nageslacht",
                                "http://", "https://", "www.", "(kinderen)", "ik heb", "ik heb gezocht",
                                "register"]
            ):
                # Filter notitie-achtige regels (te lang, of beginnen met algemene woorden)
                # Skip regels die beginnen met algemene woorden (niet namen)
                if re.match(r"^(Zo'n|De|Het|In|Van|Op|Een|Brieven|Archive|Door|Voor|Ik\s|Geen|Dit|Er|Zij|Hij|Niet|Nog|Wel|Als|Bij|Uit|Dat|Die|Dergelijke|Mogelijk|Volgens|Vermeld|Merkwaardig)\s", line):
                    return

                # Skip regels met cijfers gevolgd door woorden (waarschijnlijk notities)
                # MAAR niet als het geboorte/sterfte symbolen bevat (* of †)
                # EN niet als het een lange archiefregel is (> 200 chars) zoals huwelijkscontracten
                if re.search(r'\d{2,}', line) and not re.search(r'[*†△▭]', line) and len(line) < 200:  # 2+ cijfers achter elkaar, geen levensgebeurtenissen, korte regel
                    return

                # Skip straatadressen (bijv. "Roermond Prinses Marijkestr. 5" of "Tooroplaan 1, Weert")
                # Patroon: tekst met een straatafkorting (str., straat, weg, laan, ...) gevolgd door een huisnummer
                # Geen eindeankering ($): adres kan gevolgd worden door ", Plaatsnaam"
                if re.search(r'(str\.|straat|weg|laan|plein|kade|dijk|singel|gracht|dreef|boulevard)\s*\d+', line, re.IGNORECASE):
                    return

                # Skip Nederlandse beroepen (occupations)
                # Bijvoorbeeld: "Timmerman", "timmerman", "Timmerman (1938)", "landbouwer."
                line_lower = line.strip().lower()
                # Verwijder jaar in haakjes voor de check
                line_clean = re.sub(r'\s*\(\d{4}\)\s*$', '', line_lower).strip()
                # Verwijder bullet points
                line_clean = re.sub(r'^[•\-]\s*', '', line_clean).strip()
                # Verwijder trailing punctuatie (punt, komma, etc.)
                line_clean = line_clean.rstrip('.,;:')

                if line_clean in self.DUTCH_OCCUPATIONS:
                    return
                # Als we in een huwelijk context van een kind zitten, check of dit een nieuw kind is
                # of de partner naam
                if self.child_marriage_context:
                    # Check of dit mogelijk een nieuw kind is door te kijken naar de achternaam
                    # Als de regel de familie achternaam bevat (van de huidige persoon),
                    # dan is het waarschijnlijk een kind, niet een partner
                    parent_surname = None
                    if self.current_person and self.current_person.name:
                        # Extract achternaam van de huidige persoon
                        # Bijvoorbeeld: "Jo(h)annes (Jan) THOMASSEN" -> "THOMASSEN"
                        # Of genormaliseerd: "Johannes (Jan) Thomassen" -> "Thomassen"
                        name_parts = self.current_person.name.split()
                        if name_parts:
                            # De achternaam is meestal het laatste woord
                            parent_surname = name_parts[-1].upper()

                    # Check of deze regel de familie achternaam bevat
                    # Maar lange regels (> 150 tekens) zijn archiefreferenties, nooit kindnamen
                    is_likely_child = False
                    if len(line) > 150:
                        # Archiefregel bevat mogelijk de familienaam als bijlage-vermelding
                        # → reset context en sla over
                        self.child_marriage_context = False
                        return
                    elif parent_surname and parent_surname in line.upper():
                        is_likely_child = True
                    elif "nageslacht" in line.lower():
                        # Dit is een nieuwe sectie, stop met kinderen parsen
                        self.in_children_section = False
                        self.child_marriage_context = False
                        return

                    # Als het waarschijnlijk geen kind is, negeer de regel (het is de partner)
                    # EN reset direct child_marriage_context zodat volgende regels als kinderen worden geparsed
                    if not is_likely_child:
                        self.child_marriage_context = False  # Reset na het skippen van partner
                        return

                    # Anders, val door en parse het als een kind
                    self.child_marriage_context = False  # Reset voor nieuw kind

                # Dit is een kind zonder generatie ID
                child_line = line.strip()

                # Verwijder bullet points, nummering en annotaties als "(Hyp.)" (hypothetisch)
                child_line = re.sub(r'^[•\-]\s*', '', child_line)
                child_line = re.sub(r'^\d+\.?\s*\t\s*', '', child_line)  # "1.\tElisabeth" → "Elisabeth"
                child_line = re.sub(r'^\(Hyp\.?\)\s*', '', child_line, flags=re.IGNORECASE)

                # In dit document hebben kindnamen altijd een ACHTERNAAM IN HOOFDLETTERS (bijv. "THOMASSEN")
                # Regels zonder 3+ aaneengesloten hoofdletters VOOR DE EERSTE KOMMA zijn notities, geen kindnamen
                # Bijv. "Gouda." (woonplaats) of "Ongehuwd, huishoudster bij haar broer..."
                # Check alleen het naamgedeelte (voor komma buiten haakjes) om archiefcodes na komma te negeren
                # Bijv. "RK △ Duiven 28-01-1780, gett. ... (DTB Duiven)" → "DTB" na komma triggerde ten onrechte
                _name_check = child_line
                _depth_nc = 0
                for _i_nc, _c_nc in enumerate(child_line):
                    if _c_nc == '(':
                        _depth_nc += 1
                    elif _c_nc == ')':
                        _depth_nc -= 1
                    elif _c_nc == ',' and _depth_nc == 0:
                        _name_check = child_line[:_i_nc]
                        break
                if not re.search(r'[A-Z]{3,}', _name_check):
                    # Plaatsnaamnotaties eindigen met een punt (bijv. "Gouda.", "Brooklyn – New York.")
                    # Kindnamen eindigen nooit met een punt → als notitie opslaan
                    if child_line.rstrip().endswith('.'):
                        if self.current_child:
                            self.current_child.notes.append(child_line.rstrip('.,;:').strip())
                        return
                    # Ook Title Case namen accepteren
                    _words_only = re.sub(r'\([^)]*\)', '', _name_check).split()
                    _words_only = [w.rstrip('.,;:') for w in _words_only if w.rstrip('.,;:')]
                    if len(_words_only) >= 2:
                        # Meerdere woorden: laatste moet met hoofdletter beginnen
                        if not _words_only[-1][:1].isupper():
                            if self.current_child:
                                self.current_child.notes.append(child_line.rstrip('.,;:').strip())
                            return
                    elif len(_words_only) == 1:
                        # Enkel woord: alleen als het volledig alfabetisch is (bijv. "Rudolphus", "Joanna")
                        # Dit onderscheidt voornamen van cijfer-/leesteken-strings
                        if not re.match(r'^[A-Z][a-zA-Z]{2,}$', _words_only[0]):
                            if self.current_child:
                                self.current_child.notes.append(child_line.rstrip('.,;:').strip())
                            return
                        # Bekende niet-namen: burgerlijke staat (bijv. "Ongehuwd, huishoudster...")
                        # Na bracket-aware komma-split blijft alleen "Ongehuwd" over → geen kindnaam
                        _CIVIL_STATUS = {'ongehuwd', 'gehuwd', 'weduwe', 'weduwnaar',
                                         'gescheiden', 'ongetrouwd', 'celibatair'}
                        if _words_only[0].lower() in _CIVIL_STATUS:
                            if self.current_child:
                                self.current_child.notes.append(child_line.rstrip('.,;:').strip())
                            return
                    else:
                        if self.current_child:
                            self.current_child.notes.append(child_line.rstrip('.,;:').strip())
                        return

                # Check of dit een naamvariant is van het huidige kind
                # Naamvariant detectie: als current_child bestaat EN de regel heeft geen symbolen/markers
                # EN de achternaam lijkt op de huidige kind naam (zelfde achternaam of hoofdletter patroon)
                # MAAR: alleen als current_child nog geen levensgebeurtenis heeft (anders is dit een nieuw kind)
                is_name_variant = False
                if self.current_child and not any(symbol in child_line for symbol in ['*', '†', '△', '▭', 'Δ', 'zie', 'Tr.', 'tr.', 'Otr.', 'otr.']):
                    # Als current_child al een levensgebeurtenis heeft (geboorte, doop, sterfte), is dit geen variant maar een nieuw kind
                    has_life_event = (
                        self.current_child_has_baptism or
                        self.current_child.birth_date or self.current_child.birth_place or
                        self.current_child.death_date or self.current_child.death_place or
                        self.current_child.baptism_date or self.current_child.baptism_place
                    )
                    if not has_life_event:
                        # Extract achternaam van huidige kind
                        current_name_parts = self.current_child.name.split()
                        if current_name_parts:
                            current_surname = current_name_parts[-1].upper()

                            # Extract achternaam van nieuwe regel
                            variant_name_temp = re.sub(r",.*$", "", child_line)  # Verwijder alles na komma
                            variant_name_temp = re.sub(r"\s*\d{4}.*$", "", variant_name_temp)  # Verwijder jaar
                            variant_parts = variant_name_temp.split()

                            if variant_parts:
                                variant_surname = variant_parts[-1].upper()

                                # Als achternamen overeenkomen OF beide namen HOOFDLETTERS bevatten (KEIJZERS stijl)
                                # dan is het waarschijnlijk een variant — maar alleen als de voornaam
                                # met dezelfde letter begint (Thomas/Thoon ✓, Thomas/Maria ✗)
                                surname_match = current_surname == variant_surname or (
                                    any(c.isupper() for c in current_surname if c.isalpha()) and
                                    any(c.isupper() for c in variant_surname if c.isalpha()) and
                                    len(variant_parts) >= 2  # Minimaal voornaam + achternaam
                                )
                                if surname_match:
                                    cfw = current_name_parts[0].upper()
                                    vfw = variant_parts[0].upper()
                                    # Eén voornaam moet een prefix zijn van de ander (min. 3 tekens)
                                    # Bijv. "Tom" is prefix van "Thomas" → variant ✓
                                    # Maar "Thomas" en "Thoon" zijn geen elkaars prefix → aparte personen ✓
                                    if (len(cfw) >= 3 and len(vfw) >= 3 and
                                            (cfw.startswith(vfw) or vfw.startswith(cfw))):
                                        is_name_variant = True

                if is_name_variant:
                    # Voeg deze naamvariant toe aan het huidige kind als notitie
                    variant_name = re.sub(r",.*$", "", child_line)  # Verwijder alles na komma
                    variant_name = re.sub(r"\s*\d{4}.*$", "", variant_name)  # Verwijder jaar
                    if variant_name.strip():
                        # Voeg toe als alternatieve naam in notities
                        alt_name = f"Ook bekend als: {self.normalize_name(variant_name)}"
                        if alt_name not in self.current_child.notes:
                            self.current_child.notes.append(alt_name)
                    return  # Niet verder parsen, dit is een variant

                # Probeer geboorte/sterfte info te extraheren voordat we de naam cleanen
                birth_info = None
                death_info = None
                if "*" in child_line:
                    # Extract geboorte info
                    birth_match = re.search(r'\*\s*([^,†]+)', child_line)
                    if birth_match:
                        birth_str = birth_match.group(1).strip()
                        birth_place, birth_date = self.parse_place_date(birth_str)
                        if birth_place or birth_date:
                            birth_info = (birth_place, birth_date)

                if "†" in child_line:
                    # Extract sterfte info
                    death_match = re.search(r'†\s*([^,*]+)', child_line)
                    if death_match:
                        death_str = death_match.group(1).strip()
                        death_place, death_date = self.parse_place_date(death_str)
                        if death_place or death_date:
                            death_info = (death_place, death_date)

                # Extraheer alleen de naam (alles voor de eerste komma BUITEN haakjes, of sterfte symbool)
                child_name = child_line
                # Knipt bij eerste komma die NIET binnen haakjes staat (bijv. "Alida (Ida, Ietje)" → behoudt hele bijnaam)
                depth = 0
                cut_pos = len(child_name)
                for ci, ch in enumerate(child_name):
                    if ch == '(':
                        depth += 1
                    elif ch == ')':
                        depth -= 1
                    elif ch == ',' and depth == 0:
                        cut_pos = ci
                        break
                child_name = child_name[:cut_pos]
                # Strip levenssymbolen en alles erna uit de naam (bijv. "Wilhelmina EUJEN * ±1722" → "Wilhelmina EUJEN")
                child_name = re.sub(r"\s*[*△Δ†▭]\s*.*$", "", child_name)
                child_name = re.sub(r"\s*\d{4}.*$", "", child_name)  # Verwijder eventueel resterend jaar
                child_name = child_name.rstrip('.,;:').strip()  # Strip afsluitende interpunctie (bijv. "PELT (Vaals).")

                # Skip als de naam eruitziet als een gedeeltelijke datum na jaar-strip
                # Bijv. "Cuijk 22-07-" (afkomstig van "Cuijk 22-07-1775 Schepenbanken...")
                if re.match(r'^[\w\s]+\s+\d{1,2}-\d{2}-\s*$', child_name.strip()):
                    return

                # Skip als dit leeg is
                if not child_name.strip():
                    return

                child_id = f"{self.current_person.generation_id}_child_{len(self.unnamed_children)+1}"
                child = Person(child_id, None)
                child.name = self.normalize_name(child_name)
                child.parent_ref = self.current_person.generation_id
                child.parent_marriage_num = self.current_marriage_num  # Bewaar welk huwelijk (1, 2, 3, etc.)

                # Sla geboorte/sterfte info op als geëxtraheerd
                if birth_info:
                    child.birth_place, child.birth_date = birth_info
                if death_info:
                    child.death_place, child.death_date = death_info

                # Probeer geslacht te bepalen uit naam patronen
                # Dit is niet perfect, maar beter dan niets
                child.sex = None  # Onbekend, tenzij we het kunnen afleiden

                self.unnamed_children.append(child)

                # BELANGRIJK: Voeg dit kind ook toe aan parent's children lijst om volgorde te bewaren
                # Gebruik marriage_num van de huidige huwelijk sectie
                marriage_num = self.current_marriage_num if self.current_marriage_num is not None else 1
                self.current_person.children.append((child_id, marriage_num))

                self.current_child = child
                self.current_child_has_baptism = False  # Reset doop flag voor nieuw kind
                self.child_marriage_context = False  # Reset huwelijk context voor nieuw kind
                self.current_child_spouse_stored = False  # Reset partner-opgeslagen vlag voor nieuw kind

        # Anders: notitie
        else:
            # Lange beschrijvingen, archiefverwijzingen etc.
            # Skip URLs
            if line.startswith("http://") or line.startswith("https://"):
                return

            # Check of dit een impliciete echtgeno(o)t(e)-naam is zonder "Tr."-regel.
            # Patroon: "Voornaam ACHTERNAAM" direct voor "Hieruit:", zonder huwelijksmarkering.
            # Voorbeeld: "Elisabeth VAN KESTEREN" als vrouw van III.3 Wilhelmus RUTJENS.
            # Criteria (conservatief om valse positieven te voorkomen):
            #   - Niet in kinderensectie
            #   - 2–5 woorden (korte naam, geen beschrijvingszin)
            #   - Bevat 3+ aaneengesloten HOOFDLETTERS (achternaam-conventie in stamboomdocumenten)
            #   - Bevat ook kleine letters (voornaam)
            #   - Eerste woord begint met hoofdletter EN heeft kleine letters (gegeven naam)
            #   - Geen levenssymbolen, haakjes, cijfers of verwijzingsmarkers
            _words = line.strip().split()
            if (self.current_person is not None
                    and not self.in_children_section
                    and 2 <= len(_words) <= 5
                    and re.search(r'[A-Z]{3,}', line)
                    and re.search(r'[a-z]', line)
                    and _words[0][0].isupper()
                    and any(c.islower() for c in _words[0])
                    and not re.search(r'[*†△▭\[\]()0-9]', line)
                    and not re.search(
                        r'\b(get|gett|zie|bron|arch|kerk|doop|geb|gest|overl|woon|nageslacht)\b',
                        line, re.IGNORECASE)):
                # Behandel als echtgeno(o)t(e) zonder expliciete huwelijksregel
                spouse_name = self.normalize_name(line.strip())
                self.current_marriage_num = (self.current_marriage_num or 0) + 1
                self.current_marriage = Marriage()
                self.current_marriage.marriage_num = self.current_marriage_num
                self.current_marriage.spouse_name = spouse_name
                self.current_person.marriages.append(self.current_marriage)
                self.parsing_spouse_info = True
                return

            if len(line) > 20 and not line.startswith("Error"):
                self.current_person.notes.append(line)

    def parse(self, text):
        """Parse de volledige tekst"""
        # Split ook op U+2028 (LINE SEPARATOR) en U+2029 (PARAGRAPH SEPARATOR):
        # Word-documenten gebruiken U+2028 voor zachte regeleinden (Shift+Enter),
        # zodat namen en huwelijksinfo op aparte logische regels staan maar in één alinea.
        lines = re.split(r'[\n\u2028\u2029]', text)

        # Skip legenda (eerste regels tot eerste generatie header)
        start_idx = 0
        for i, line in enumerate(lines):
            if "Eerste generatie" in line or re.match(r"^I\.\d+\s+", line):
                start_idx = i
                break

        # Parse alle regels
        for line in lines[start_idx:]:
            self.parse_line(line)

        # Sla laatste persoon op
        if self.current_person:
            self.persons[self.current_person.generation_id] = self.current_person

    def generate_gedcom(self, output_file="stamboom.ged"):
        """Genereer GEDCOM bestand"""
        # Maak ID mapping - gebruik referentienummer als ID
        person_id_map = {}  # generation_id -> @Ixxx@
        spouse_persons = {}  # spouse_key -> Person object voor partners

        # Bepaal hoogste ref_num om ID conflicten te voorkomen
        max_ref_num = 0
        for person in self.persons.values():
            if person.ref_num:
                max_ref_num = max(max_ref_num, int(person.ref_num))

        # Start next_id na de hoogste ref_num om conflicten te vermijden
        next_id = max_ref_num + 1

        for gen_id in sorted(self.persons.keys()):
            person = self.persons[gen_id]
            # Gebruik referentienummer als ID indien beschikbaar
            if person.ref_num:
                person_id_map[gen_id] = f"@I{person.ref_num}@"
            else:
                # Fallback naar sequentieel nummer
                person_id_map[gen_id] = f"@I{next_id}@"
                next_id += 1

        # Maak personen aan voor partners die geen eigen generatie ID hebben
        spouse_id_start = 10000  # Start bij 10000 om conflict te vermijden
        for gen_id, person in self.persons.items():
            for i, marriage in enumerate(person.marriages):
                if marriage.spouse_name:
                    spouse_key = f"{gen_id}_spouse_{i+1}"
                    # Maak een nieuw Person object voor de partner
                    spouse_person = Person(spouse_key, None)
                    spouse_person.name = self.normalize_name(marriage.spouse_name)
                    spouse_person.birth_date = marriage.spouse_birth_date
                    spouse_person.birth_place = marriage.spouse_birth_place
                    spouse_person.death_date = marriage.spouse_death_date
                    spouse_person.death_place = marriage.spouse_death_place
                    spouse_person.baptism_date = marriage.spouse_baptism_date
                    spouse_person.baptism_place = marriage.spouse_baptism_place
                    spouse_person.burial_date = marriage.spouse_burial_date
                    spouse_person.burial_place = marriage.spouse_burial_place
                    # Bepaal geslacht (tegenovergestelde van hoofdpersoon)
                    if person.sex == "M":
                        spouse_person.sex = "F"
                    elif person.sex == "F":
                        spouse_person.sex = "M"
                    spouse_persons[spouse_key] = spouse_person
                    person_id_map[spouse_key] = f"@I{spouse_id_start}@"
                    spouse_id_start += 1

        # Maak personen aan voor ouders van partners
        parent_id_start = 30000  # Start bij 30000 om conflict te vermijden
        parent_persons = {}
        parent_families = {}  # Voor het opslaan van ouder-familie paren

        for gen_id, person in self.persons.items():
            for i, marriage in enumerate(person.marriages):
                if marriage.spouse_father_name and marriage.spouse_mother_name:
                    spouse_key = f"{gen_id}_spouse_{i+1}"
                    parent_fam_key = f"{spouse_key}_parents"

                    # Maak vader persoon
                    father_key = f"{spouse_key}_father"
                    if father_key not in person_id_map:
                        father_person = Person(father_key, None)
                        father_person.name = self.normalize_name(marriage.spouse_father_name)
                        father_person.sex = "M"
                        parent_persons[father_key] = father_person
                        person_id_map[father_key] = f"@I{parent_id_start}@"
                        parent_id_start += 1

                    # Maak moeder persoon
                    mother_key = f"{spouse_key}_mother"
                    if mother_key not in person_id_map:
                        mother_person = Person(mother_key, None)
                        mother_person.name = self.normalize_name(marriage.spouse_mother_name)
                        mother_person.sex = "F"
                        parent_persons[mother_key] = mother_person
                        person_id_map[mother_key] = f"@I{parent_id_start}@"
                        parent_id_start += 1

                    # Sla familie relatie op voor later
                    parent_families[parent_fam_key] = {
                        "father_key": father_key,
                        "mother_key": mother_key,
                        "child_key": spouse_key  # De partner is kind van deze ouders
                    }

        # Maak personen aan voor kinderen zonder generatie ID
        child_id_start = 20000  # Start bij 20000 om conflict te vermijden
        child_persons = {}
        for child in self.unnamed_children:
            child_persons[child.generation_id] = child
            person_id_map[child.generation_id] = f"@I{child_id_start}@"
            child_id_start += 1

        # Maak families - eerst alle families creëren
        families = {}
        family_id = 1
        person_families = {}  # gen_id -> list of family IDs voor FAMS links

        # Stap 1: Maak families voor alle huwelijken
        for gen_id in sorted(self.persons.keys()):
            person = self.persons[gen_id]
            person_id = person_id_map[gen_id]
            person_families[gen_id] = []

            for i, marriage in enumerate(person.marriages):
                fam_key = f"{gen_id}_m{i+1}"
                fam_id = f"@F{family_id}@"
                family_id += 1

                # Bepaal partner ID
                spouse_key = f"{gen_id}_spouse_{i+1}"
                spouse_id = person_id_map.get(spouse_key)

                families[fam_key] = {
                    "id": fam_id,
                    "parent": person_id,
                    "parent_sex": person.sex,
                    "parent_gen_id": gen_id,
                    "spouse_id": spouse_id,  # Nieuw: partner ID
                    "children": [],
                    "marriage": marriage,
                }
                person_families[gen_id].append(fam_id)

                # Voeg ook FAMS voor de partner toe
                if spouse_key in person_id_map:
                    if spouse_key not in person_families:
                        person_families[spouse_key] = []
                    person_families[spouse_key].append(fam_id)

        # Stap 1c: Maak families voor kinderen zonder generatie ID met huwelijken
        for child in self.unnamed_children:
            child_gen_id = child.generation_id
            if child.marriages:
                person_families[child_gen_id] = []

                for i, marriage in enumerate(child.marriages):
                    fam_key = f"{child_gen_id}_m{i+1}"
                    fam_id = f"@F{family_id}@"
                    family_id += 1

                    person_families[child_gen_id].append(fam_id)

                    # Maak familie record
                    families[fam_key] = {
                        "id": fam_id,
                        "parent": person_id_map[child_gen_id],
                        "parent_sex": child.sex,
                        "parent_gen_id": child_gen_id,
                        "spouse_id": None,  # Wordt later gevuld als partner bekend is
                        "children": [],
                        "marriage": marriage,
                    }

                    # Maak partner persoon aan als naam bekend is
                    if marriage.spouse_name:
                        spouse_key = f"{child_gen_id}_spouse_{i+1}"
                        if spouse_key not in person_id_map:
                            # Voeg partner toe aan spouse_persons
                            spouse_person = Person(spouse_key, None)
                            spouse_person.name = marriage.spouse_name
                            spouse_person.birth_date = marriage.spouse_birth_date
                            spouse_person.birth_place = marriage.spouse_birth_place
                            spouse_person.death_date = marriage.spouse_death_date
                            spouse_person.death_place = marriage.spouse_death_place
                            spouse_person.baptism_date = marriage.spouse_baptism_date
                            spouse_person.baptism_place = marriage.spouse_baptism_place
                            spouse_person.burial_date = marriage.spouse_burial_date
                            spouse_person.burial_place = marriage.spouse_burial_place
                            # Bepaal geslacht op basis van parent
                            spouse_person.sex = "F" if child.sex == "M" else "M" if child.sex == "F" else None
                            spouse_persons[spouse_key] = spouse_person
                            person_id_map[spouse_key] = f"@I{spouse_id_start}@"
                            spouse_id_start += 1

                        families[fam_key]["spouse_id"] = person_id_map[spouse_key]

                        # Voeg ook FAMS voor de partner toe
                        if spouse_key not in person_families:
                            person_families[spouse_key] = []
                        person_families[spouse_key].append(fam_id)

                        # Maak ouders voor de partner aan (als ouders bekend zijn)
                        if marriage.spouse_father_name or marriage.spouse_mother_name:
                            parent_fam_key = f"{child_gen_id}_spouse_{i+1}_parents"
                            father_key = f"{child_gen_id}_spouse_{i+1}_father"
                            mother_key = f"{child_gen_id}_spouse_{i+1}_mother"

                            if marriage.spouse_father_name and father_key not in person_id_map:
                                father_person = Person(father_key, None)
                                father_person.name = self.normalize_name(marriage.spouse_father_name)
                                father_person.sex = "M"
                                parent_persons[father_key] = father_person
                                person_id_map[father_key] = f"@I{parent_id_start}@"
                                parent_id_start += 1

                            if marriage.spouse_mother_name and mother_key not in person_id_map:
                                mother_person = Person(mother_key, None)
                                mother_person.name = self.normalize_name(marriage.spouse_mother_name)
                                mother_person.sex = "F"
                                parent_persons[mother_key] = mother_person
                                person_id_map[mother_key] = f"@I{parent_id_start}@"
                                parent_id_start += 1

                            parent_families[parent_fam_key] = {
                                "father_key": father_key if marriage.spouse_father_name else None,
                                "mother_key": mother_key if marriage.spouse_mother_name else None,
                                "child_key": spouse_key,
                            }

        # Stap 1b: Maak families voor ouders van partners (gen_id én unnamed children)
        # Wordt nu na Stap 1c uitgevoerd zodat parent_families voor unnamed children ook verwerkt worden
        if not hasattr(self, 'person_parent_families'):
            self.person_parent_families = {}
        for parent_fam_key, parent_fam_data in parent_families.items():
            if parent_fam_key in families:
                continue  # Reeds verwerkt

            fam_id = f"@F{family_id}@"
            family_id += 1

            father_key = parent_fam_data["father_key"]
            mother_key = parent_fam_data["mother_key"]
            child_key = parent_fam_data["child_key"]

            father_id = person_id_map.get(father_key) if father_key else None
            mother_id = person_id_map.get(mother_key) if mother_key else None
            child_id = person_id_map.get(child_key)

            # Maak familie record
            families[parent_fam_key] = {
                "id": fam_id,
                "parent": father_id,
                "parent_sex": "M",
                "parent_gen_id": father_key,
                "spouse_id": mother_id,
                "children": [child_id] if child_id else [],
                "marriage": None,
            }

            # Voeg FAMS voor vader en moeder toe
            if father_key and father_id:
                if father_key not in person_families:
                    person_families[father_key] = []
                person_families[father_key].append(fam_id)

            if mother_key and mother_id:
                if mother_key not in person_families:
                    person_families[mother_key] = []
                person_families[mother_key].append(fam_id)

            # Voeg FAMC voor kind (de partner) toe
            if child_key not in self.person_parent_families:
                self.person_parent_families[child_key] = []
            self.person_parent_families[child_key].append(fam_id)

        # Stap 2: Voeg kinderen toe aan families (met generatie ID)
        # Nieuwe aanpak: itereer door ouders en hun children lijst
        for parent_gen_id in sorted(self.persons.keys()):
            parent_person = self.persons[parent_gen_id]

            if parent_person.children and parent_gen_id in person_families:
                # Itereer door alle kinderen van deze ouder
                for child_info in parent_person.children:
                    # child_info kan een tuple (child_ref, marriage_num) zijn of een string (backward compatibility)
                    if isinstance(child_info, tuple):
                        child_ref, marriage_num = child_info
                    else:
                        # Oude format: alleen child_ref, gebruik eerste huwelijk
                        child_ref = child_info
                        marriage_num = 1

                    # Zoek het kind in person_id_map (werkt voor named EN unnamed children)
                    if child_ref in person_id_map:
                        child_id = person_id_map[child_ref]

                        # Gebruik het juiste huwelijk op basis van marriage_num
                        marriage_index = marriage_num - 1
                        if marriage_index >= 0 and marriage_index < len(person_families[parent_gen_id]):
                            parent_fam_id = person_families[parent_gen_id][marriage_index]
                        elif len(person_families[parent_gen_id]) > 0:
                            # Fallback naar laatste huwelijk als marriage_index buiten bereik is
                            parent_fam_id = person_families[parent_gen_id][-1]
                        else:
                            # Geen familie beschikbaar, skip dit kind
                            continue

                        # Voeg kind toe aan familie
                        for fam_key, fam_data in families.items():
                            if fam_data["id"] == parent_fam_id:
                                if child_id in families[fam_key]["children"]:
                                    # Duplicaat (bijv. door typefout "zie III.4" i.p.v. "zie III.5"):
                                    # zoek een ongelinkte sibling met dezelfde ouder en wijs die toe.
                                    for sid, sp in self.persons.items():
                                        if (sid != child_ref
                                                and sp.parent_ref == parent_gen_id
                                                and sid not in self.person_parent_families
                                                and sid in person_id_map):
                                            sib_id = person_id_map[sid]
                                            families[fam_key]["children"].append(sib_id)
                                            if sid not in self.person_parent_families:
                                                self.person_parent_families[sid] = []
                                            if parent_fam_id not in self.person_parent_families[sid]:
                                                self.person_parent_families[sid].append(parent_fam_id)
                                            break
                                else:
                                    families[fam_key]["children"].append(child_id)
                                    # Sla FAMC link op voor dit kind
                                    if not hasattr(self, 'person_parent_families'):
                                        self.person_parent_families = {}
                                    if child_ref not in self.person_parent_families:
                                        self.person_parent_families[child_ref] = []
                                    if parent_fam_id not in self.person_parent_families[child_ref]:
                                        self.person_parent_families[child_ref].append(parent_fam_id)
                                break

        # Stap 3 niet meer nodig: unnamed children zitten nu ook in parent.children lijst!

        with open(output_file, "w", encoding="utf-8") as f:
            # Header
            f.write("0 HEAD\n")
            f.write("1 SOUR Stamboom Converter\n")
            f.write("2 VERS 1.0\n")
            f.write("2 NAME Stamboom Word naar GEDCOM\n")
            f.write("1 DEST ANY\n")
            f.write("1 DATE " + datetime.now().strftime("%d %b %Y").upper() + "\n")
            f.write("1 GEDC\n")
            f.write("2 VERS 5.5.1\n")
            f.write("1 CHAR UTF-8\n")

            # Individuen - eerst reguliere personen, dan partners, dan kinderen, dan ouders van partners
            all_persons = list(self.persons.items()) + list(spouse_persons.items()) + list(child_persons.items()) + list(parent_persons.items())

            for gen_id, person in all_persons:
                person_id = person_id_map[gen_id]

                f.write(f"0 {person_id} INDI\n")

                # Naam
                if person.name:
                    # GEDCOM format: voornaam /achternaam/
                    # Verwijder extra haakjes en slashes uit achternaam
                    clean_name = person.name.replace("/(", "/").replace(")/", "/").rstrip("/")

                    # Verwijder referentienummers [xxx] en [xxx=yyy] uit naam
                    clean_name = re.sub(r'\s*\[\d+(?:=\d+)?\]\s*', ' ', clean_name).strip()

                    # Vervang "/" binnen haakjes door " of " om conflict met GEDCOM naam-delimiter te voorkomen
                    # Bijv. "(Gerard / Sjra)" → "(Gerard of Sjra)", "(Toon/Ton)" → "(Toon of Ton)"
                    clean_name = re.sub(r'\(([^)]*)\)', lambda m: '(' + m.group(1).replace(' / ', ' of ').replace('/', ' of ') + ')', clean_name)

                    # Split naam maar behoud context van wat binnen/buiten haakjes staat
                    # Zoek het laatste woord buiten haakjes als achternaam
                    # Bijvoorbeeld: "Jan Thomassen (Joannes) (van den Brunckom)" -> achternaam "Thomassen"
                    # Of: "Maria Aben (Abels, Aaben) [33]" -> achternaam "Aben"
                    # Of: "Agnes Rutjes / Rutjens" -> voornaam "Agnes", achternaam "Rutjes / Rutjens"

                    # Verwijder alles binnen haakjes voor achternaam detectie
                    name_without_parens = re.sub(r'\([^)]*\)', '', clean_name).strip()
                    # Strip afsluitende interpunctie (bijv. "TRIJSELAAR." → "Trijselaar")
                    name_without_parens = name_without_parens.rstrip(".,;:")

                    # Check of er een "/" voorkomt in de naam (variant achternamen of voornamen)
                    # Bijvoorbeeld: "Agnes Rutjes / Rutjens" (achternaam variant)
                    # Of: "Walravius / Walramus van Benthum" (voornaam variant + achternaam)
                    if " / " in name_without_parens or re.search(r'\S/\S|\S/', name_without_parens):
                        # Normaliseer slash-spaties: bijv. "Janse /Jansen" → "Janse / Jansen"
                        # zodat parts[-2] altijd "/" is bij achternaam-varianten
                        name_without_parens = re.sub(r'\s*/\s*', ' / ', name_without_parens).strip()
                        parts = name_without_parens.split()

                        # Check of er een Nederlands tussenvoegsel voorkomt (van, de, den, etc.)
                        # Dit duidt op de start van een achternaam
                        prepositions = ['van', 'de', 'den', 'der', 'van den', 'van de', 'van der', 'ter', 'te', "'t"]
                        surname_start_idx = None

                        for i, word in enumerate(parts):
                            if word.lower() in prepositions:
                                surname_start_idx = i
                                break

                        if surname_start_idx is not None:
                            # We hebben een tussenvoegsel gevonden - alles vanaf daar is achternaam
                            given_parts = parts[:surname_start_idx]
                            surname_parts = parts[surname_start_idx:]
                            given = " ".join(given_parts)
                            surname = " ".join(surname_parts)
                            # Vervang "/" in het voornaam-gedeelte door " of " (GEDCOM delimiter-conflict)
                            given = re.sub(r'\s*/\s*', ' of ', given)
                            f.write(f"1 NAME {given} /{surname}/\n")
                        elif len(parts) >= 3:
                            # Geen tussenvoegsel - check of laatste woord een standalone achternaam is
                            # (d.w.z. het is NIET direct na een "/"):
                            # - "Agnes Rutjes / Rutjens" → parts[-2]="/" → achternaam-variant → given="Agnes", surname="Rutjes / Rutjens"
                            # - "Marie / Mietje Weteling" → parts[-2]="Mietje" → standalone achternaam → given="Marie / Mietje (Maria)", surname="Weteling"
                            if parts[-2] == "/":
                                # Achternaam-variant: het woord vóór de EERSTE "/" is het begin van de achternaam
                                # Bijv. "Agnes Rutjes / Rutjens"        → given="Agnes",        surname="Rutjes / Rutjens"
                                # Bijv. "Anna Geertruijda Scheepers / Schepers" → given="Anna Geertruijda", surname="Scheepers / Schepers"
                                first_slash_idx = parts.index("/")
                                given = " ".join(parts[:first_slash_idx - 1])
                                surname = " ".join(parts[first_slash_idx - 1:])
                                # Dedupliceer identieke achternaam-varianten (bijv. "Rutjens / Rutjens" → "Rutjens")
                                _sv = [v.strip() for v in surname.split("/")]
                                if len(set(v.lower() for v in _sv)) == 1:
                                    surname = _sv[0]
                            else:
                                # Standalone achternaam: zoek in clean_name
                                surname = parts[-1]
                                surname_pos = clean_name.rfind(surname)
                                if surname_pos > 0:
                                    given = clean_name[:surname_pos].strip()
                                else:
                                    given = " ".join(parts[:-1])
                            # Vervang "/" in het voornaam-gedeelte door " of " (GEDCOM delimiter-conflict)
                            given = re.sub(r'\s*/\s*', ' of ', given)
                            f.write(f"1 NAME {given} /{surname}/\n")
                        else:
                            # Fallback naar oude logica
                            parts_outside = name_without_parens.split()
                            surname = parts_outside[-1].strip("/()")
                            given = " ".join(parts_outside[:-1])
                            f.write(f"1 NAME {given} /{surname}/\n")
                    else:
                        # Normale naam zonder "/" varianten
                        parts_outside = name_without_parens.split()

                        if len(parts_outside) > 1:
                            # Het laatste woord buiten haakjes is de achternaam
                            surname = parts_outside[-1].strip("/()")
                            # Veiligheidscheck: als achternaam geen letters bevat (bijv. puur interpunctie),
                            # schrijf de naam zonder achternaam-markers
                            if not re.search(r'[A-Za-z]', surname):
                                f.write(f"1 NAME {clean_name}\n")
                            else:
                                # Gebruik originele naam voor voornaam (met haakjes)
                                # Vind de positie van de achternaam in originele naam
                                surname_pos = clean_name.rfind(surname)
                                if surname_pos > 0:
                                    given = clean_name[:surname_pos].strip()
                                    f.write(f"1 NAME {given} /{surname}/\n")
                                else:
                                    # Fallback naar eenvoudige split
                                    given = " ".join(parts_outside[:-1])
                                    f.write(f"1 NAME {given} /{surname}/\n")
                        else:
                            # Enkel woord: controleer of het ALL-CAPS is (= achternaam zonder voornaam)
                            if clean_name.isupper() and len(clean_name) > 2:
                                surname = clean_name.capitalize()
                                # Gebruik capitalize() niet voor namen met meer dan 1 hoofdletter-segment
                                # (bijv. "McGregor"), maar voor standaard NL achternamen volstaat het
                                def _smart_title_local(s):
                                    result = []
                                    first_alpha = True
                                    for c in s:
                                        if c.isalpha():
                                            result.append(c.upper() if first_alpha else c.lower())
                                            first_alpha = False
                                        else:
                                            result.append(c)
                                    return ''.join(result)
                                surname = _smart_title_local(clean_name)
                                f.write(f"1 NAME /{surname}/\n")
                            else:
                                f.write(f"1 NAME {clean_name}\n")

                # Geslacht
                if person.sex:
                    f.write(f"1 SEX {person.sex}\n")

                # Geboorte
                if person.birth_date or person.birth_place:
                    f.write("1 BIRT\n")
                    if person.birth_date:
                        f.write(f"2 DATE {person.birth_date}\n")
                    if person.birth_place:
                        f.write(f"2 PLAC {person.birth_place}\n")

                # Doop
                if person.baptism_date or person.baptism_place:
                    f.write("1 CHR\n")
                    if person.baptism_date:
                        f.write(f"2 DATE {person.baptism_date}\n")
                    if person.baptism_place:
                        f.write(f"2 PLAC {person.baptism_place}\n")
                    if person.baptism_witnesses:
                        witnesses = ", ".join(person.baptism_witnesses)
                        f.write(f"2 NOTE Getuigen: {witnesses}\n")

                # Overlijden
                if person.death_date or person.death_place:
                    f.write("1 DEAT\n")
                    if person.death_date:
                        f.write(f"2 DATE {person.death_date}\n")
                    if person.death_place:
                        f.write(f"2 PLAC {person.death_place}\n")

                # Begraven
                if person.burial_date or person.burial_place:
                    f.write("1 BURI\n")
                    if person.burial_date:
                        f.write(f"2 DATE {person.burial_date}\n")
                    if person.burial_place:
                        f.write(f"2 PLAC {person.burial_place}\n")

                # Notities
                if person.notes:
                    # Combineer notities
                    combined_notes = "\n".join(person.notes[:5])  # Max 5 notities
                    if combined_notes:
                        # GEDCOM CONT voor multi-line notes
                        note_lines = combined_notes.split("\n")
                        f.write(f"1 NOTE {note_lines[0]}\n")
                        for note_line in note_lines[1:]:
                            if note_line.strip():
                                f.write(f"2 CONT {note_line}\n")

                # Referentienummer als NOTE (alleen als het niet als ID wordt gebruikt)
                # Het referentienummer zit nu al in het @Ixxx@ ID, dus niet meer als notitie nodig

                # Link naar ouders (FAMC)
                # Gebruik person_parent_families als beschikbaar (voor kinderen uit specifieke huwelijken)
                # Anders gebruik de oude logica met parent_ref (voor backward compatibility)
                if hasattr(self, 'person_parent_families') and gen_id in self.person_parent_families:
                    for parent_fam_id in self.person_parent_families[gen_id]:
                        f.write(f"1 FAMC {parent_fam_id}\n")
                elif person.parent_ref and person.parent_ref in person_families:
                    if person_families[person.parent_ref]:
                        # Gebruik de eerste familie van de ouder (fallback voor oude logica)
                        parent_fam_id = person_families[person.parent_ref][0]
                        f.write(f"1 FAMC {parent_fam_id}\n")

                # Link naar eigen huwelijken (FAMS)
                if gen_id in person_families:
                    for fam_id in person_families[gen_id]:
                        f.write(f"1 FAMS {fam_id}\n")

            # Families
            for fam_key, family in families.items():
                f.write(f"0 {family['id']} FAM\n")

                # Ouders - gebruik parent veld voor eigen huwelijken
                if "parent" in family:
                    parent_id = family["parent"]
                    parent_sex = family.get("parent_sex")
                    spouse_id = family.get("spouse_id")

                    # Schrijf HUSB en WIFE op basis van geslacht
                    if parent_sex == "M":
                        f.write(f"1 HUSB {parent_id}\n")
                        if spouse_id:
                            f.write(f"1 WIFE {spouse_id}\n")
                    elif parent_sex == "F":
                        f.write(f"1 WIFE {parent_id}\n")
                        if spouse_id:
                            f.write(f"1 HUSB {spouse_id}\n")
                    else:
                        # Als geslacht onbekend, probeer het alsnog
                        f.write(f"1 HUSB {parent_id}\n")
                        if spouse_id:
                            f.write(f"1 WIFE {spouse_id}\n")
                elif fam_key in self.persons:
                    # Dit is een familie gemaakt voor kinderen (ouders)
                    parent = self.persons[fam_key]
                    if parent.sex == "M":
                        f.write(f"1 HUSB {person_id_map[fam_key]}\n")
                    elif parent.sex == "F":
                        f.write(f"1 WIFE {person_id_map[fam_key]}\n")

                # Kinderen
                for child_id in family["children"]:
                    f.write(f"1 CHIL {child_id}\n")

                # Huwelijk
                marriage = family.get("marriage")
                if marriage:
                    if marriage.marriage_date or marriage.marriage_place:
                        f.write("1 MARR\n")
                        if marriage.marriage_date:
                            f.write(f"2 DATE {marriage.marriage_date}\n")
                        if marriage.marriage_place:
                            f.write(f"2 PLAC {marriage.marriage_place}\n")
                        if marriage.witnesses:
                            witnesses = ", ".join(marriage.witnesses)
                            f.write(f"2 NOTE Getuigen: {witnesses}\n")
                    if marriage.engagement_date or marriage.engagement_place:
                        f.write("1 ENGA\n")
                        if marriage.engagement_date:
                            f.write(f"2 DATE {marriage.engagement_date}\n")
                        if marriage.engagement_place:
                            f.write(f"2 PLAC {marriage.engagement_place}\n")

            # Trailer
            f.write("0 TRLR\n")


def process_file(doc_file, output_file=None, output_dir=None, verbose=True):
    """Process een enkel Word document naar GEDCOM"""
    # Bepaal output directory
    if output_dir is None:
        output_dir = get_base_dir() / "gedcom"
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    # Bepaal output bestandsnaam
    if output_file is None:
        # Converteer bijv. "THOMASSEN 16 David.doc" naar "gedcom/THOMASSEN_16_David.ged"
        doc_path = Path(doc_file)
        output_name = doc_path.stem.replace(" ", "_") + ".ged"
        output_file = output_dir / output_name
    else:
        # Als een specifieke output file is opgegeven, plaats die ook in output_dir/
        output_file = output_dir / Path(output_file).name

    if verbose:
        print(f"\n{'='*60}")
        print(f"Verwerken: {doc_file}")
        print(f"Output: {output_file}")
        print('='*60)

    parser = StamboomParser()

    # Lees document
    try:
        text = parser.read_doc_file(doc_file)
        if verbose:
            print(f"Document gelezen: {len(text)} karakters")
    except Exception as e:
        print(f"❌ Fout bij lezen van {doc_file}: {e}")
        return False

    # Parse document
    if verbose:
        print("Parsen van stamboom...")
    parser.parse(text)

    if verbose:
        print(f"Gevonden: {len(parser.persons)} personen")

        # Toon eerste paar personen
        print("\nVoorbeeld personen:")
        for i, (gen_id, person) in enumerate(list(parser.persons.items())[:3]):
            print(f"  {gen_id}: {person.name}")
            if person.birth_date or person.birth_place:
                print(f"    Geboren: {person.birth_date or '?'} in {person.birth_place or '?'}")
            if person.marriages:
                print(f"    Huwelijken: {len(person.marriages)}")
            if person.children:
                # Extraheer child refs uit tuples (child_ref, marriage_num) of strings
                child_refs = [c[0] if isinstance(c, tuple) else c for c in person.children[:3]]
                print(f"    Kinderen: {len(person.children)} (refs: {', '.join(child_refs)})")

    # Genereer GEDCOM
    if verbose:
        print(f"\nGenereren van {output_file}...")
    parser.generate_gedcom(output_file)

    if verbose:
        print(f"✓ Klaar! GEDCOM bestand gegenereerd: {output_file}")
        print(f"  - {len(parser.persons)} personen")
        print(f"  - Geschatte families: {sum(len(p.marriages) for p in parser.persons.values())}")

    return True


def get_base_dir():
    """Bepaal de basisdirectory: waar de exe/script staat.
    
    Bij PyInstaller exe: de map waar de .exe in staat.
    Bij normaal Python script: de map waar het script in staat.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller exe
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent


def main():
    base_dir = get_base_dir()
    input_dir = base_dir / "stambomen"
    output_dir = base_dir / "gedcom"

    print("Stamboom Word Document naar GEDCOM Converter")
    print("=" * 60)

    # Check command line argumenten
    if len(sys.argv) > 1:
        # Specifiek bestand verwerken
        doc_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None

        if not Path(doc_file).exists():
            print(f"❌ Bestand niet gevonden: {doc_file}")
            _wait_for_exit()
            return

        process_file(doc_file, output_file, output_dir=output_dir, verbose=True)
    else:
        # Maak directories aan als ze niet bestaan
        input_dir.mkdir(exist_ok=True)
        output_dir.mkdir(exist_ok=True)

        # Vind alle .doc en .docx bestanden
        doc_files = list(input_dir.glob("*.doc")) + list(input_dir.glob("*.docx"))

        if not doc_files:
            print(f"\n📂 Plaats je Word-documenten (.doc / .docx) in de map:")
            print(f"   {input_dir}")
            print(f"\n   Start daarna dit programma opnieuw.")
            _wait_for_exit()
            return

        print(f"\n📂 Input:  {input_dir}")
        print(f"📂 Output: {output_dir}")

        print(f"\nGevonden {len(doc_files)} stamboom document(en):")
        for doc_file in doc_files:
            print(f"  - {doc_file.name}")

        print(f"\nVerwerken van {len(doc_files)} bestand(en)...\n")

        success_count = 0
        for doc_file in doc_files:
            if process_file(str(doc_file), output_dir=output_dir, verbose=True):
                success_count += 1

        print(f"\n{'='*60}")
        print(f"✓ Klaar! {success_count}/{len(doc_files)} bestanden succesvol verwerkt")
        print(f"  GEDCOM bestanden staan in: {output_dir}")
        print(f"{'='*60}")

    _wait_for_exit()


def _wait_for_exit():
    """Wacht op Enter zodat het console-venster niet meteen sluit."""
    print("\nDruk op Enter om af te sluiten...")
    try:
        input()
    except EOFError:
        pass


if __name__ == "__main__":
    main()
