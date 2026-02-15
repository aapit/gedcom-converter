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
        self.spouse_father_name = None  # Naam van vader van partner
        self.spouse_mother_name = None  # Naam van moeder van partner
        self.witnesses = []


class StamboomParser:
    """Parser voor stamboom Word document"""

    def __init__(self):
        self.persons = {}  # generation_id -> Person
        self.current_person = None
        self.current_marriage = None
        self.in_children_section = False
        self.current_marriage_num = 0
        self.parsing_spouse_info = False  # True wanneer we partner info aan het parsen zijn
        self.unnamed_children = []  # Kinderen zonder generatie ID
        self.current_child = None  # Huidig kind zonder generatie ID
        self.child_marriage_context = False  # True wanneer we een huwelijk van een kind aan het parsen zijn

    def normalize_name(self, name):
        """Converteer all-caps namen naar title case"""
        if not name:
            return name

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
            # Als het woord volledig in hoofdletters is en langer dan 1 karakter
            elif word_clean.isupper() and len(word_clean) > 1:
                # Converteer naar title case
                # Behoud haakjes indien aanwezig
                if word.startswith("(") and word.endswith(")"):
                    normalized = "(" + word_clean.title() + ")"
                elif word.startswith("("):
                    normalized = "(" + word_clean.title()
                elif word.endswith(")"):
                    normalized = word_clean.title() + ")"
                else:
                    normalized = word_clean.title()
                normalized_words.append(normalized)
            else:
                # Behoud origineel als het niet all-caps is
                normalized_words.append(word)

        return " ".join(normalized_words)

    def read_doc_file(self, doc_path):
        """Lees .doc of .docx bestand en converteer naar tekst met textutil (macOS)"""
        result = subprocess.run(
            ["textutil", "-convert", "txt", doc_path, "-stdout"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    def parse_date(self, text):
        """Parse datum uit verschillende formaten"""
        if not text:
            return None

        text = text.strip()

        # Probeer verschillende datum patronen
        # ±1645, 30-06-1703, 23-04 / 07-05-1702, etc.
        patterns = [
            r"(\d{1,2}-\d{1,2}-\d{4})",  # 30-06-1703 (volledige datum eerst!)
            r"(\d{1,2}/\d{1,2}/\d{4})",  # 30/06/1703
            r"(±?\d{4})",  # ±1645 of 1645
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)

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
            parts = text.split(date)
            if parts[0].strip():
                place = parts[0].strip()
                # Verwijder eventuele symbolen aan het begin
                place = re.sub(r"^[*△†▭]\s*", "", place)
        else:
            place = text.strip()
            place = re.sub(r"^[*△†▭]\s*", "", place)

        # Filter ongewenste plaats-woorden
        if place and place.lower() in ["met", "als", "met name"]:
            place = None

        # Trim trailing commas en symbolen
        if place:
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

        # Verwijder het referentienummer
        if ref_match:
            name_part = re.sub(r"\[\d+\]", "", name_part).strip()

        # Neem alles voor de komma
        if "," in name_part:
            name_part = name_part.split(",")[0].strip()

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

        parent_match = re.search(r"(?:zn\.|dr\.)\s+van\s+(.+?)\s+en\s+(.+?)(?:,|$)", spouse_info, re.IGNORECASE)
        if parent_match:
            father_name = parent_match.group(1).strip()
            mother_name = parent_match.group(2).strip()

            # Verwijder alles na een punt gevolgd door een hoofdletter of cijfer (nieuwe zin/info)
            # Bijvoorbeeld: "Anna Catharina Teeuwen. Winkelierster. Molenstraat 84"
            period_match = re.search(r'\.\s+[A-Z0-9]', mother_name)
            if period_match:
                mother_name = mother_name[:period_match.start() + 1].strip().rstrip('.')

            period_match = re.search(r'\.\s+[A-Z0-9]', father_name)
            if period_match:
                father_name = father_name[:period_match.start() + 1].strip().rstrip('.')

            # Verwijder eventuele extra info na de naam (zoals beroep, religie, etc.)
            # Stop bij woorden die indiceren dat het extra info is
            for stop_word in [" bibliothecaris", " winkelierster", " bakker", " boer", " smid", ". rk", ". ng", ". herv"]:
                if stop_word in mother_name.lower():
                    mother_name = mother_name[:mother_name.lower().index(stop_word)].strip()
                if stop_word in father_name.lower():
                    father_name = father_name[:father_name.lower().index(stop_word)].strip()

            return father_name, mother_name

        return None, None

    def parse_line(self, line):
        """Parse een enkele regel"""
        line = line.strip()
        if not line:
            return

        # Check of dit een nieuwe persoon is (met optionele punt en spatie: "VII.5.", "VII.5 " of "VII. 5. ")
        if re.match(r"^[IVX]+\.\s*\d+\.?\s+", line):
            # Sla vorige persoon op
            if self.current_person:
                self.persons[self.current_person.generation_id] = self.current_person

            # Parse nieuwe persoon
            self.current_person = self.parse_person_header(line)
            self.current_marriage = None
            self.in_children_section = False
            self.parsing_spouse_info = False
            self.current_marriage_num = 0
            self.current_child = None
            self.child_marriage_context = False
            return

        if not self.current_person:
            return

        # Parse geboren (*)
        if line.startswith("*"):
            rest = line[1:].strip()

            # Check of er een sterfte symbool (†) op dezelfde regel staat
            death_part = None
            if "†" in rest:
                parts = rest.split("†", 1)
                rest = parts[0].strip()
                death_part = parts[1].strip()
            # Split op komma als er een doop symbool in staat
            elif "," in rest and ("△" in rest or "Δ" in rest):
                parts = rest.split(",")
                rest = parts[0]

            place, date = self.parse_place_date(rest)

            # Bepaal waar we deze info opslaan
            if self.in_children_section and self.current_child:
                # Dit is een kind zonder generatie ID - sla geboorte info op
                self.current_child.birth_place = place
                self.current_child.birth_date = date
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

            # Parse sterfte info als die op dezelfde regel staat
            if death_part:
                death_place, death_date = self.parse_place_date(death_part)
                if self.in_children_section and self.current_child:
                    self.current_child.death_place = death_place
                    self.current_child.death_date = death_date
                elif self.parsing_spouse_info and self.current_marriage:
                    self.current_marriage.spouse_death_place = death_place
                    self.current_marriage.spouse_death_date = death_date
                elif not self.in_children_section:
                    self.current_person.death_place = death_place
                    self.current_person.death_date = death_date

            # Check of er huwelijks info op dezelfde regel staat
            # Bijvoorbeeld: "* ... † ... Tr. plaats datum met"
            if not self.in_children_section and not self.parsing_spouse_info:
                marriage_match = re.search(r"\b(Otr?\.|Tr\.)\s+(.+?)\s+met\s*$", line, re.IGNORECASE)
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
        elif line.startswith("△") or line.startswith("Δ"):
            # Negeer doop data in kinderen sectie of partner info sectie
            if not self.in_children_section and not self.parsing_spouse_info:
                rest = line[1:].strip()
                # Format: "RK Sint Anthonis 26-08-1707, gett. Derick Jans en Joanna Jans"
                if "gett." in rest or "get." in rest:
                    parts = re.split(r",?\s*gett?\.?\s*", rest)
                    if len(parts) > 0:
                        place, date = self.parse_place_date(parts[0])
                        self.current_person.baptism_place = place
                        self.current_person.baptism_date = date
                    if len(parts) > 1:
                        self.current_person.baptism_witnesses = [w.strip() for w in parts[1].split(" en ")]
                else:
                    place, date = self.parse_place_date(rest)
                    self.current_person.baptism_place = place
                    self.current_person.baptism_date = date

        # Parse overleden (†)
        elif line.startswith("†"):
            place, date = self.parse_place_date(line[1:].strip())

            # Bepaal waar we deze info opslaan
            if self.in_children_section and self.current_child:
                # Dit is een kind zonder generatie ID - sla overleden info op
                self.current_child.death_place = place
                self.current_child.death_date = date
            elif self.in_children_section:
                # Negeer - kinderen sectie maar geen current_child
                pass
            elif self.parsing_spouse_info and self.current_marriage:
                # Dit is partner overleden info
                self.current_marriage.spouse_death_place = place
                self.current_marriage.spouse_death_date = date
            else:
                # Dit is de huidige persoon
                self.current_person.death_place = place
                self.current_person.death_date = date

        # Parse begraven (▭)
        elif "begr." in line.lower() or line.startswith("▭"):
            # Negeer begraven data in kinderen sectie of partner info sectie
            if not self.in_children_section and not self.parsing_spouse_info:
                # "begr. RK Beers 14-02-1731"
                rest = re.sub(r"begr\.?\s*", "", line, flags=re.IGNORECASE).strip()
                rest = rest.lstrip("▭").strip()
                place, date = self.parse_place_date(rest)
                self.current_person.burial_place = place
                self.current_person.burial_date = date

        # Parse huwelijk
        elif (re.search(r"^(Otr?\.|Tr\.)", line) or
              re.search(r"\b(otr|ot)\.\s*/?\s*(tr\.?)", line, re.IGNORECASE)):
            # Als we in de kinderen sectie zitten, is dit een huwelijk van een kind
            if self.in_children_section:
                # Markeer dat we nu een huwelijk van een kind parsen
                # De volgende regels (partner naam, etc.) moeten worden genegeerd
                self.child_marriage_context = True
                self.current_child = None  # Reset huidige kind
                return

            # Anders is dit een huwelijk van de huidige persoon
            self.current_marriage_num += 1
            self.current_marriage = Marriage()
            self.current_marriage.marriage_num = self.current_marriage_num
            self.current_person.marriages.append(self.current_marriage)
            self.in_children_section = False
            self.parsing_spouse_info = True  # We gaan nu partner info parsen

            # Parse datum en plaats
            # "Otr. / tr. als jongeman  NG Beers 23-04 / 07-05-1702"
            # "Tr. RK Beers 11-05-1727 (gett. ...)"
            # Extract plaats en datum
            place_date_match = re.search(
                r"(?:otr?\.?\s*/?\s*tr\.?|tr\.)\s+(?:als\s+\w+\s+)?(.+?)(?:\(|met|$)", line, re.IGNORECASE
            )
            if place_date_match:
                place_date_str = place_date_match.group(1).strip()
                place, date = self.parse_place_date(place_date_str)
                self.current_marriage.marriage_place = place
                self.current_marriage.marriage_date = date

        # Parse partner (regel na tr./otr.)
        elif self.current_marriage and not self.current_marriage.spouse_name and \
             not re.match(r"^[IVX]+\.\d+", line) and not self.in_children_section:
            # Skip URLs
            if line.startswith("http://") or line.startswith("https://"):
                return

            # Dit zou de partner kunnen zijn
            # Simpele heuristiek: als het geen andere keyword bevat
            if not any(
                keyword in line.lower()
                for keyword in ["hieruit:", "uit (", "arch.", "beers", "cuijk", "wanroij", "schepenbanken", "http://", "https://"]
            ):
                # Verwijder referentie nummer [xxx] en huwelijksnummer (1), (2), etc. uit partner naam
                # Bijvoorbeeld: "(1) Maria ABEN [33]" -> "Maria ABEN"
                clean_name = re.sub(r'\s*\[\d+\]\s*$', '', line)  # Verwijder [xxx] aan het einde
                clean_name = re.sub(r'^\s*\(\d+\)\s*', '', clean_name)  # Verwijder (1) aan het begin
                self.current_marriage.spouse_name = self.normalize_name(clean_name)
                self.current_marriage.spouse_info = line

                # Parse ouders van partner indien aanwezig
                father_name, mother_name = self.parse_spouse_parents(line)
                if father_name and mother_name:
                    self.current_marriage.spouse_father_name = father_name
                    self.current_marriage.spouse_mother_name = mother_name

        # Parse kinderen sectie
        elif line.startswith("Hieruit:") or re.match(r"^Uit\s+\(\d+\)", line):
            self.in_children_section = True
            self.parsing_spouse_info = False  # Niet meer in partner info sectie
            self.child_marriage_context = False  # Reset huwelijk context
            # Extract huwelijksnummer
            marriage_num_match = re.search(r"Uit\s+\((\d+)\)", line)
            if marriage_num_match:
                self.current_marriage_num = int(marriage_num_match.group(1))

        # Parse kind
        elif self.in_children_section:
            # Skip URLs (http://, https://, etc.)
            if line.startswith("http://") or line.startswith("https://"):
                return

            # Kijk of het een verwijzing naar een kind is
            # "Jan (Joannes) Thomassen, 1703, zie III.1"
            # Of: "• Agnes RUTJES, 1803, zie V.10" (met bullet point)
            child_match = re.search(r"zie\s+([IVX]+\.\d+)", line)
            if child_match:
                child_ref = child_match.group(1)
                self.current_person.children.append(child_ref)
                self.current_child = None  # Reset current child
                self.child_marriage_context = False  # Reset huwelijk context
            elif re.match(r"^[A-Z•]", line) and not any(
                keyword in line.lower()
                for keyword in ["arch.", "beers", "cuijk", "wanroij", "ibid", "error", "uit", "hieruit", "generatie", "nageslacht", "tr.", "otr.", "http://", "https://"]
            ):
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
                    is_likely_child = False
                    if parent_surname and parent_surname in line.upper():
                        is_likely_child = True
                    elif "nageslacht" in line.lower():
                        # Dit is een nieuwe sectie, stop met kinderen parsen
                        self.in_children_section = False
                        self.child_marriage_context = False
                        return

                    # Als het waarschijnlijk geen kind is, negeer de regel (het is de partner)
                    if not is_likely_child:
                        return

                    # Anders, val door en parse het als een kind
                    self.child_marriage_context = False  # Reset voor nieuw kind

                # Dit is een kind zonder generatie ID
                # Maak een nieuw kind persoon aan
                child_name = line.strip()

                # Verwijder bullet points
                child_name = re.sub(r'^[•\-]\s*', '', child_name)

                # Verwijder eventuele trailing punten en datums
                child_name = re.sub(r",.*$", "", child_name)  # Verwijder alles na komma
                child_name = re.sub(r"\s*\d{4}.*$", "", child_name)  # Verwijder jaar

                # Skip als dit leeg is
                if not child_name.strip():
                    return

                child = Person(f"{self.current_person.generation_id}_child_{len(self.unnamed_children)+1}", None)
                child.name = self.normalize_name(child_name)
                child.parent_ref = self.current_person.generation_id
                # Probeer geslacht te bepalen uit naam patronen
                # Dit is niet perfect, maar beter dan niets
                child.sex = None  # Onbekend, tenzij we het kunnen afleiden

                self.unnamed_children.append(child)
                self.current_child = child
                self.child_marriage_context = False  # Reset huwelijk context voor nieuw kind

        # Anders: notitie
        else:
            # Lange beschrijvingen, archiefverwijzingen etc.
            # Skip URLs
            if line.startswith("http://") or line.startswith("https://"):
                return
            if len(line) > 20 and not line.startswith("Error"):
                self.current_person.notes.append(line)

    def parse(self, text):
        """Parse de volledige tekst"""
        lines = text.split("\n")

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

        # Stap 1b: Maak families voor ouders van partners
        for parent_fam_key, parent_fam_data in parent_families.items():
            fam_id = f"@F{family_id}@"
            family_id += 1

            father_key = parent_fam_data["father_key"]
            mother_key = parent_fam_data["mother_key"]
            child_key = parent_fam_data["child_key"]

            father_id = person_id_map.get(father_key)
            mother_id = person_id_map.get(mother_key)
            child_id = person_id_map.get(child_key)

            # Maak familie record
            families[parent_fam_key] = {
                "id": fam_id,
                "parent": father_id,
                "parent_sex": "M",
                "parent_gen_id": father_key,
                "spouse_id": mother_id,
                "children": [child_id] if child_id else [],
                "marriage": None,  # Geen huwelijks info voor ouders van partners
            }

            # Voeg FAMS voor vader en moeder toe
            if father_key not in person_families:
                person_families[father_key] = []
            person_families[father_key].append(fam_id)

            if mother_key not in person_families:
                person_families[mother_key] = []
            person_families[mother_key].append(fam_id)

            # Voeg FAMC voor kind (de partner) toe - dit is de link die ontbrak!
            # We markeren dit met een speciale key zodat we het later kunnen verwerken
            if child_key not in person_families:
                person_families[child_key] = []
            # Voeg een marker toe dat dit een FAMC link is (niet FAMS)
            # We slaan dit op in een aparte dictionary
            if not hasattr(self, 'person_parent_families'):
                self.person_parent_families = {}
            if child_key not in self.person_parent_families:
                self.person_parent_families[child_key] = []
            self.person_parent_families[child_key].append(fam_id)

        # Stap 2: Voeg kinderen toe aan families (met generatie ID)
        for gen_id in sorted(self.persons.keys()):
            person = self.persons[gen_id]
            person_id = person_id_map[gen_id]

            if person.parent_ref and person.parent_ref in person_id_map:
                parent_person = self.persons.get(person.parent_ref)
                if parent_person and parent_person.marriages:
                    # Gebruik de eerste familie van de ouder
                    if person.parent_ref in person_families and person_families[person.parent_ref]:
                        parent_fam_id = person_families[person.parent_ref][0]
                        # Zoek de familie met dit ID
                        for fam_key, fam_data in families.items():
                            if fam_data["id"] == parent_fam_id:
                                families[fam_key]["children"].append(person_id)
                                break

        # Stap 3: Voeg kinderen zonder generatie ID toe aan families
        for child in self.unnamed_children:
            child_id = person_id_map[child.generation_id]
            parent_ref = child.parent_ref

            if parent_ref and parent_ref in person_families and person_families[parent_ref]:
                # Gebruik de eerste familie van de ouder
                parent_fam_id = person_families[parent_ref][0]
                # Zoek de familie met dit ID
                for fam_key, fam_data in families.items():
                    if fam_data["id"] == parent_fam_id:
                        families[fam_key]["children"].append(child_id)
                        break

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

                    # Split naam maar behoud context van wat binnen/buiten haakjes staat
                    # Zoek het laatste woord buiten haakjes als achternaam
                    # Bijvoorbeeld: "Jan Thomassen (Joannes) (van den Brunckom)" -> achternaam "Thomassen"
                    # Of: "Maria Aben (Abels, Aaben) [33]" -> achternaam "Aben"
                    # Of: "Agnes Rutjes / Rutjens" -> voornaam "Agnes", achternaam "Rutjes / Rutjens"

                    # Verwijder alles binnen haakjes voor achternaam detectie
                    name_without_parens = re.sub(r'\([^)]*\)', '', clean_name).strip()

                    # Check of er een "/" voorkomt in de naam (variant achternamen)
                    # Bijvoorbeeld: "Agnes Rutjes / Rutjens"
                    if " / " in name_without_parens:
                        # Vind de eerste "/" - alles ervoor is voornaam, alles vanaf eerste woord voor "/" is achternaam
                        parts = name_without_parens.split()
                        # Vind eerste niet-voornaam woord (meestal na eerste woord)
                        if len(parts) >= 3:  # Minimaal: voornaam achternaam1 / achternaam2
                            # Eerste woord is voornaam, rest is achternaam
                            given = parts[0]
                            surname = " ".join(parts[1:])
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
                if person.parent_ref and person.parent_ref in person_families:
                    if person_families[person.parent_ref]:
                        # Gebruik de eerste familie van de ouder
                        parent_fam_id = person_families[person.parent_ref][0]
                        f.write(f"1 FAMC {parent_fam_id}\n")

                # Link naar ouders voor partners (FAMC via person_parent_families)
                if hasattr(self, 'person_parent_families') and gen_id in self.person_parent_families:
                    for parent_fam_id in self.person_parent_families[gen_id]:
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
                    # Partner NOTE niet meer nodig - partner is nu een WIFE/HUSB record

            # Trailer
            f.write("0 TRLR\n")


def process_file(doc_file, output_file=None, verbose=True):
    """Process een enkel Word document naar GEDCOM"""
    # Zorg dat gedcom directory bestaat
    gedcom_dir = Path("gedcom")
    gedcom_dir.mkdir(exist_ok=True)

    # Bepaal output bestandsnaam
    if output_file is None:
        # Converteer bijv. "THOMASSEN 16 David.doc" naar "gedcom/THOMASSEN_16_David.ged"
        doc_path = Path(doc_file)
        output_name = doc_path.stem.replace(" ", "_") + ".ged"
        output_file = gedcom_dir / output_name
    else:
        # Als een specifieke output file is opgegeven, plaats die ook in gedcom/
        output_file = gedcom_dir / Path(output_file).name

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
                print(f"    Kinderen: {len(person.children)} (refs: {', '.join(person.children[:3])})")

    # Genereer GEDCOM
    if verbose:
        print(f"\nGenereren van {output_file}...")
    parser.generate_gedcom(output_file)

    if verbose:
        print(f"✓ Klaar! GEDCOM bestand gegenereerd: {output_file}")
        print(f"  - {len(parser.persons)} personen")
        print(f"  - Geschatte families: {sum(len(p.marriages) for p in parser.persons.values())}")

    return True


def main():
    print("Stamboom Word Document naar GEDCOM Converter")
    print("=" * 60)

    # Check command line argumenten
    if len(sys.argv) > 1:
        # Specifiek bestand verwerken
        doc_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None

        if not Path(doc_file).exists():
            print(f"❌ Bestand niet gevonden: {doc_file}")
            return

        process_file(doc_file, output_file, verbose=True)
    else:
        # Verwerk alle .doc bestanden in stambomen directory
        stambomen_dir = Path("stambomen")

        if not stambomen_dir.exists():
            # Fallback naar oude gedrag
            print("\nGeen stambomen directory gevonden. Verwerk standaard bestand...")
            process_file("THOMASSEN 16 David.doc", "stamboom.ged", verbose=True)
            return

        # Vind alle .doc en .docx bestanden
        doc_files = list(stambomen_dir.glob("*.doc")) + list(stambomen_dir.glob("*.docx"))

        if not doc_files:
            print("❌ Geen .doc bestanden gevonden in stambomen directory")
            return

        print(f"\nGevonden {len(doc_files)} stamboom document(en):")
        for doc_file in doc_files:
            print(f"  - {doc_file.name}")

        print(f"\nVerwerken van {len(doc_files)} bestand(en)...\n")

        success_count = 0
        for doc_file in doc_files:
            if process_file(str(doc_file), verbose=True):
                success_count += 1

        print(f"\n{'='*60}")
        print(f"✓ Klaar! {success_count}/{len(doc_files)} bestanden succesvol verwerkt")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
