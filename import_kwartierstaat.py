#!/usr/bin/env python3
"""
Converteer kwartierstaat Excel naar GEDCOM formaat
"""

import pandas as pd
import re
from datetime import datetime
from pathlib import Path


class GedcomGenerator:
    def __init__(self):
        self.individuals = {}
        self.families = {}

    def parse_place_year(self, text):
        """Parse 'Plaats jaar' naar aparte componenten"""
        if pd.isna(text) or not text:
            return None, None

        text = str(text).strip()

        # Probeer jaar te extraheren (4 cijfers met optionele prefix: <, >, ±)
        # Voorbeelden: "1850", "±1850", "<1850", ">1850"
        year_match = re.search(r"([<>±]?\s*\d{4})", text)
        year = year_match.group(1).strip() if year_match else None

        # Plaats is alles voor het jaar (zonder 'Geb.')
        if year_match:
            # Vind de positie van de volledige year match (inclusief prefix)
            place = text[: year_match.start()].strip()
        else:
            place = text

        # Verwijder 'Geb.' prefix
        place = re.sub(r"^Geb\.?\s*", "", place, flags=re.IGNORECASE)
        place = place.strip()

        return place or None, year

    def determine_sex(self, quartier_num, name):
        """Bepaal geslacht op basis van kwartiernummer (even=man, oneven=vrouw)"""
        if quartier_num == 1:
            # Voor persoon 1 kunnen we proberen af te leiden van voornamen
            # maar dit is onbetrouwbaar, laat gebruiker dit handmatig aanpassen
            return "M"  # Standaard M voor persoon 1
        return "M" if quartier_num % 2 == 0 else "F"

    def add_individual(self, quartier_num, name, birth_info, death_info, marriage_info):
        """Voeg een persoon toe aan de database"""
        birth_place, birth_year = self.parse_place_year(birth_info)
        death_place, death_year = self.parse_place_year(death_info)
        marriage_place, marriage_year = self.parse_place_year(marriage_info)

        sex = self.determine_sex(quartier_num, name)

        self.individuals[quartier_num] = {
            "id": f"@I{quartier_num}@",
            "name": name,
            "sex": sex,
            "birth_place": birth_place,
            "birth_year": birth_year,
            "death_place": death_place,
            "death_year": death_year,
            "marriage_place": marriage_place,
            "marriage_year": marriage_year,
        }

    def create_families(self):
        """Maak families op basis van kwartiernummers"""
        # Voor elke persoon: vader = 2n, moeder = 2n+1
        for quartier_num in sorted(self.individuals.keys()):
            father_num = quartier_num * 2
            mother_num = quartier_num * 2 + 1

            if father_num in self.individuals and mother_num in self.individuals:
                family_id = f"@F{quartier_num}@"

                # Haal huwelijksinfo van vader (even nummer)
                marriage_place = self.individuals[father_num]["marriage_place"]
                marriage_year = self.individuals[father_num]["marriage_year"]

                self.families[family_id] = {
                    "id": family_id,
                    "husband": self.individuals[father_num]["id"],
                    "wife": self.individuals[mother_num]["id"],
                    "children": [self.individuals[quartier_num]["id"]],
                    "marriage_place": marriage_place,
                    "marriage_year": marriage_year,
                }

                # Link persoon aan zijn/haar ouders
                self.individuals[quartier_num]["famc"] = family_id

                # Link ouders aan hun familie
                self.individuals[father_num].setdefault("fams", []).append(family_id)
                self.individuals[mother_num].setdefault("fams", []).append(family_id)

    def generate_gedcom(self, output_file="output.ged"):
        """Genereer GEDCOM bestand"""
        with open(output_file, "w", encoding="utf-8") as f:
            # Header
            f.write("0 HEAD\n")
            f.write("1 SOUR Kwartierstaat Converter\n")
            f.write("2 VERS 1.0\n")
            f.write("2 NAME Kwartierstaat naar GEDCOM\n")
            f.write("1 DEST ANY\n")
            f.write("1 DATE " + datetime.now().strftime("%d %b %Y").upper() + "\n")
            f.write("1 GEDC\n")
            f.write("2 VERS 5.5.1\n")
            f.write("2 FORM LINEAGE-LINKED\n")
            f.write("1 CHAR UTF-8\n")
            f.write("1 LANG Dutch\n")

            # Individuen
            for quartier_num in sorted(self.individuals.keys()):
                person = self.individuals[quartier_num]

                f.write(f"0 {person['id']} INDI\n")

                # Format naam als GEDCOM: voornaam /achternaam/
                name = person['name']
                if name and isinstance(name, str):
                    name_parts = name.split()
                    if len(name_parts) > 1:
                        # Laatste woord is achternaam (tenzij het een tussenvoegsel is)
                        # Voor Nederlandse namen: check of laatste woord een achternaam is
                        surname_idx = len(name_parts) - 1

                        # Check voor afkortingen a/d en v/d (aan de/van de)
                        # Deze komen meestal na een familienaam en voor een plaatsnaam
                        # Bijvoorbeeld: "Willems a/d Rooijendijk" -> achternaam start bij "Willems"
                        for i, part in enumerate(name_parts):
                            if part.lower() in ['a/d', 'v/d', 'a/de', 'v/de']:
                                # Achternaam start bij het woord voor de afkorting
                                if i > 0:
                                    surname_idx = i - 1
                                    break

                        # Anders: check voor tussenvoegsels die bij achternaam horen
                        if surname_idx == len(name_parts) - 1:
                            while surname_idx > 0 and name_parts[surname_idx - 1].lower() in ['van', 'de', 'den', 'der', 'van den', 'van de', 'ter', 'te', "'t"]:
                                surname_idx -= 1

                        given = " ".join(name_parts[:surname_idx])
                        surname = " ".join(name_parts[surname_idx:])

                        # Verwijder "/" uit voornamen (GEDCOM gebruikt / als surname delimiter)
                        # Vervang "/" door "or" voor variant voornamen
                        # Bijvoorbeeld: "Willemina / Maria" -> "Willemina or Maria"
                        given = given.replace(" / ", " or ").replace("/", " or ")

                        f.write(f"1 NAME {given} /{surname}/\n")
                    else:
                        # Alleen achternaam
                        f.write(f"1 NAME /{name}/\n")
                elif name:
                    # Naam is niet een string (bijv. nummer), converteer naar string
                    f.write(f"1 NAME /{str(name)}/\n")
                else:
                    f.write(f"1 NAME /Onbekend/\n")

                f.write(f"1 SEX {person['sex']}\n")

                # Geboorte
                if person["birth_year"] or person["birth_place"]:
                    f.write("1 BIRT\n")
                    if person["birth_year"]:
                        f.write(f"2 DATE {person['birth_year']}\n")
                    if person["birth_place"]:
                        f.write(f"2 PLAC {person['birth_place']}\n")

                # Overlijden
                if person["death_year"] or person["death_place"]:
                    f.write("1 DEAT\n")
                    if person["death_year"]:
                        f.write(f"2 DATE {person['death_year']}\n")
                    if person["death_place"]:
                        f.write(f"2 PLAC {person['death_place']}\n")

                # Link naar ouders (child in family)
                if "famc" in person:
                    f.write(f"1 FAMC {person['famc']}\n")

                # Link naar eigen gezin (spouse in family)
                if "fams" in person:
                    for fam in person["fams"]:
                        f.write(f"1 FAMS {fam}\n")

            # Families
            for family_id in sorted(self.families.keys()):
                family = self.families[family_id]

                f.write(f"0 {family['id']} FAM\n")
                f.write(f"1 HUSB {family['husband']}\n")
                f.write(f"1 WIFE {family['wife']}\n")

                for child in family["children"]:
                    f.write(f"1 CHIL {child}\n")

                # Huwelijk
                if family["marriage_year"] or family["marriage_place"]:
                    f.write("1 MARR\n")
                    if family["marriage_year"]:
                        f.write(f"2 DATE {family['marriage_year']}\n")
                    if family["marriage_place"]:
                        f.write(f"2 PLAC {family['marriage_place']}\n")

            # Trailer
            f.write("0 TRLR\n")


def main():
    print("Kwartierstaat naar GEDCOM Converter")
    print("=" * 50)

    # Lees Excel bestand
    excel_file = "kwartierstaat TT excel.xlsx"
    print(f"\nLezen van {excel_file}...")

    df = pd.read_excel(excel_file, header=None)

    # Kolommen: 0=generatie, 1=kwartiernr, 2=naam, 3=geboorte, 4=overlijden, 5=huwelijk
    df.columns = [
        "generatie",
        "kwartiernr",
        "naam",
        "geboorte",
        "overlijden",
        "huwelijk",
    ]

    # Verwijder lege rijen
    df = df.dropna(subset=["kwartiernr"])

    print(f"Gevonden: {len(df)} personen")

    # Genereer GEDCOM
    gedcom = GedcomGenerator()

    for _, row in df.iterrows():
        quartier_num = int(row["kwartiernr"])
        name = row["naam"] if pd.notna(row["naam"]) else "Onbekend"

        gedcom.add_individual(
            quartier_num, name, row["geboorte"], row["overlijden"], row["huwelijk"]
        )

    # Maak familierelaties
    print("\nMaken van familierelaties...")
    gedcom.create_families()

    # Zorg dat gedcom directory bestaat
    gedcom_dir = Path("gedcom")
    gedcom_dir.mkdir(exist_ok=True)

    # Genereer output
    output_file = gedcom_dir / "kwartierstaat.ged"
    print(f"\nGenereren van {output_file}...")
    gedcom.generate_gedcom(str(output_file))

    print(f"\n✓ Klaar! GEDCOM bestand gegenereerd: {output_file}")
    print(f"  - {len(gedcom.individuals)} personen")
    print(f"  - {len(gedcom.families)} families")

    # Toon eerste persoon als voorbeeld
    if 1 in gedcom.individuals:
        person = gedcom.individuals[1]
        print(f"\nHoofdpersoon (1):")
        print(f"  Naam: {person['name']}")
        print(
            f"  Geboren: {person['birth_year'] or '?'} in {person['birth_place'] or '?'}"
        )
        print(
            f"  Overleden: {person['death_year'] or '?'} in {person['death_place'] or '?'}"
        )


if __name__ == "__main__":
    main()
