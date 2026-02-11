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
        self.witnesses = []


class StamboomParser:
    """Parser voor stamboom Word document"""

    def __init__(self):
        self.persons = {}  # generation_id -> Person
        self.current_person = None
        self.current_marriage = None
        self.in_children_section = False
        self.current_marriage_num = 0

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
        """Lees .doc bestand en converteer naar tekst met textutil (macOS)"""
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

        # Extract generation ID
        gen_match = re.match(r"^([IVX]+\.\d+)\s+(.+)$", line)
        if not gen_match:
            return None

        gen_id = gen_match.group(1)
        rest = gen_match.group(2)

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

    def parse_line(self, line):
        """Parse een enkele regel"""
        line = line.strip()
        if not line:
            return

        # Check of dit een nieuwe persoon is
        if re.match(r"^[IVX]+\.\d+\s+", line):
            # Sla vorige persoon op
            if self.current_person:
                self.persons[self.current_person.generation_id] = self.current_person

            # Parse nieuwe persoon
            self.current_person = self.parse_person_header(line)
            self.current_marriage = None
            self.in_children_section = False
            self.current_marriage_num = 0
            return

        if not self.current_person:
            return

        # Parse geboren (*)
        if line.startswith("*"):
            rest = line[1:].strip()
            # Split op komma als er een doop symbool in staat
            if "," in rest and ("△" in rest or "Δ" in rest):
                parts = rest.split(",")
                place, date = self.parse_place_date(parts[0])
            else:
                place, date = self.parse_place_date(rest)
            self.current_person.birth_place = place
            self.current_person.birth_date = date

        # Parse gedoopt (△ of Δ)
        elif line.startswith("△") or line.startswith("Δ"):
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
            self.current_person.death_place = place
            self.current_person.death_date = date

        # Parse begraven (▭)
        elif "begr." in line.lower() or line.startswith("▭"):
            # "begr. RK Beers 14-02-1731"
            rest = re.sub(r"begr\.?\s*", "", line, flags=re.IGNORECASE).strip()
            rest = rest.lstrip("▭").strip()
            place, date = self.parse_place_date(rest)
            self.current_person.burial_place = place
            self.current_person.burial_date = date

        # Parse huwelijk
        elif (re.search(r"^(Otr?\.|Tr\.)", line) or
              re.search(r"\b(otr|ot)\.\s*/?\s*(tr\.?)", line, re.IGNORECASE)) and \
             not self.in_children_section:
            # Alleen als het aan het begin van de regel staat of een duidelijk patroon heeft
            # en we niet in de kinderen sectie zitten
            self.current_marriage_num += 1
            self.current_marriage = Marriage()
            self.current_marriage.marriage_num = self.current_marriage_num
            self.current_person.marriages.append(self.current_marriage)
            self.in_children_section = False

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
            # Dit zou de partner kunnen zijn
            # Simpele heuristiek: als het geen andere keyword bevat
            if not any(
                keyword in line.lower()
                for keyword in ["hieruit:", "uit (", "arch.", "beers", "cuijk", "wanroij", "schepenbanken"]
            ):
                self.current_marriage.spouse_name = self.normalize_name(line)
                self.current_marriage.spouse_info = line

        # Parse kinderen sectie
        elif line.startswith("Hieruit:") or re.match(r"^Uit\s+\(\d+\)", line):
            self.in_children_section = True
            # Extract huwelijksnummer
            marriage_num_match = re.search(r"Uit\s+\((\d+)\)", line)
            if marriage_num_match:
                self.current_marriage_num = int(marriage_num_match.group(1))

        # Parse kind
        elif self.in_children_section:
            # Kijk of het een verwijzing naar een kind is
            # "Jan (Joannes) Thomassen, 1703, zie III.1"
            # "Jenneke (Joanna) Thomassen"
            child_match = re.search(r"zie\s+([IVX]+\.\d+)", line)
            if child_match:
                child_ref = child_match.group(1)
                self.current_person.children.append(child_ref)
            elif re.match(r"^[A-Z]", line) and not any(
                keyword in line
                for keyword in ["Arch.", "Beers", "Cuijk", "Wanroij", "Ibid", "Error"]
            ):
                # Mogelijk een kind zonder zie-verwijzing
                # Bewaar als notitie
                pass

        # Anders: notitie
        else:
            # Lange beschrijvingen, archiefverwijzingen etc.
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
        next_id = 1

        for gen_id in sorted(self.persons.keys()):
            person = self.persons[gen_id]
            # Gebruik referentienummer als ID indien beschikbaar
            if person.ref_num:
                person_id_map[gen_id] = f"@I{person.ref_num}@"
            else:
                # Fallback naar sequentieel nummer
                person_id_map[gen_id] = f"@I{next_id}@"
                next_id += 1

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
                families[fam_key] = {
                    "id": fam_id,
                    "parent": person_id,
                    "parent_sex": person.sex,
                    "parent_gen_id": gen_id,
                    "children": [],
                    "marriage": marriage,
                }
                person_families[gen_id].append(fam_id)

        # Stap 2: Voeg kinderen toe aan families
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

            # Individuen
            for gen_id in sorted(self.persons.keys()):
                person = self.persons[gen_id]
                person_id = person_id_map[gen_id]

                f.write(f"0 {person_id} INDI\n")

                # Naam
                if person.name:
                    # GEDCOM format: voornaam /achternaam/
                    # Verwijder extra haakjes en slashes uit achternaam
                    clean_name = person.name.replace("/(", "/").replace(")/", "/").rstrip("/")
                    name_parts = clean_name.split()
                    if len(name_parts) > 1:
                        given = " ".join(name_parts[:-1])
                        surname = name_parts[-1].strip("/()")
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
                    if parent_sex == "M":
                        f.write(f"1 HUSB {parent_id}\n")
                    elif parent_sex == "F":
                        f.write(f"1 WIFE {parent_id}\n")
                    else:
                        # Als geslacht onbekend, probeer het alsnog
                        f.write(f"1 HUSB {parent_id}\n")
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
                    if marriage.spouse_name:
                        f.write(f"1 NOTE Partner: {marriage.spouse_name}\n")

            # Trailer
            f.write("0 TRLR\n")


def main():
    print("Stamboom Word Document naar GEDCOM Converter")
    print("=" * 60)

    # Input en output files
    doc_file = "THOMASSEN 16 David.doc"
    output_file = "stamboom.ged"

    print(f"\nLezen van {doc_file}...")
    parser = StamboomParser()

    # Lees document
    text = parser.read_doc_file(doc_file)
    print(f"Document gelezen: {len(text)} karakters")

    # Parse document
    print("\nParsen van stamboom...")
    parser.parse(text)
    print(f"Gevonden: {len(parser.persons)} personen")

    # Toon eerste paar personen
    print("\nVoorbeeld personen:")
    for i, (gen_id, person) in enumerate(list(parser.persons.items())[:3]):
        print(f"\n  {gen_id}: {person.name}")
        if person.birth_date or person.birth_place:
            print(f"    Geboren: {person.birth_date or '?'} in {person.birth_place or '?'}")
        if person.marriages:
            print(f"    Huwelijken: {len(person.marriages)}")
        if person.children:
            print(f"    Kinderen: {len(person.children)} (refs: {', '.join(person.children[:3])})")

    # Genereer GEDCOM
    print(f"\nGenereren van {output_file}...")
    parser.generate_gedcom(output_file)

    print(f"\n✓ Klaar! GEDCOM bestand gegenereerd: {output_file}")
    print(f"  - {len(parser.persons)} personen")
    print(f"  - Geschatte families: {sum(len(p.marriages) for p in parser.persons.values())}")


if __name__ == "__main__":
    main()
