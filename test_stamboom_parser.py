"""
Unit tests for stamboom_doc.py parser

Run with: pytest test_stamboom_parser.py -v
"""

import pytest
from import_stamboom_doc import StamboomParser, Person, Marriage


class TestParseSpouseParents:
    """Tests for parse_spouse_parents() function"""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_basic_parent_parsing(self):
        """Test basic parent name extraction"""
        text = "dr. van Benignus Joseph Coppens en Cornelia Francisca Xaveria Story"
        father, mother = self.parser.parse_spouse_parents(text)
        assert father == "Benignus Joseph Coppens"
        assert mother == "Cornelia Francisca Xaveria Story"

    def test_parent_with_profession_filter(self):
        """Test filtering of profession after mother name"""
        text = "dr. van Michael van Breij en Anna Catharina Teeuwen. Winkelierster. Molenstraat 84"
        father, mother = self.parser.parse_spouse_parents(text)
        assert father == "Michael van Breij"
        assert mother == "Anna Catharina Teeuwen"

    def test_parent_with_rk_marker(self):
        """Test filtering of RK (Rooms Katholiek) marker"""
        text = "dr. van Ignatius Aloijsius van der Loop en Johanna Maria Briels. RK"
        father, mother = self.parser.parse_spouse_parents(text)
        assert father == "Ignatius Aloijsius van der Loop"
        assert mother == "Johanna Maria Briels"

    def test_parent_with_bibliothecaris(self):
        """Test filtering of bibliothecaris profession"""
        text = "dr. van John Doe en Jane Smith, bibliothecaris"
        father, mother = self.parser.parse_spouse_parents(text)
        assert father == "John Doe"
        assert mother == "Jane Smith"

    def test_son_of_pattern(self):
        """Test 'zn. van' (son of) pattern"""
        text = "zn. van Peter Jansen en Maria Hendriksen"
        father, mother = self.parser.parse_spouse_parents(text)
        assert father == "Peter Jansen"
        assert mother == "Maria Hendriksen"

    def test_no_parents_found(self):
        """Test when no parent pattern is found"""
        text = "Just some random text without parent info"
        father, mother = self.parser.parse_spouse_parents(text)
        assert father is None
        assert mother is None

    def test_parent_with_multiple_professions(self):
        """Test filtering multiple info pieces after name"""
        text = "dr. van Jan Pietersen en Marie Jansen. Smid. Grote Straat 10. RK"
        father, mother = self.parser.parse_spouse_parents(text)
        assert father == "Jan Pietersen"
        assert mother == "Marie Jansen"


class TestParsePlaceDate:
    """Tests for parse_place_date() function"""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_place_and_date(self):
        """Test parsing place and date together"""
        place, date = self.parser.parse_place_date("Oldenzaal 05-01-1885")
        assert place == "Oldenzaal"
        assert date == "05-01-1885"

    def test_place_and_year_only(self):
        """Test parsing place and year"""
        place, date = self.parser.parse_place_date("Roermond 1932")
        assert place == "Roermond"
        assert date == "1932"

    def test_approximate_year(self):
        """Test parsing approximate year with ± symbol"""
        place, date = self.parser.parse_place_date("Cuijk ±1675")
        assert place == "Cuijk"
        assert date == "±1675"

    def test_date_only(self):
        """Test parsing date without place"""
        place, date = self.parser.parse_place_date("30-06-1703")
        assert place is None
        assert date == "30-06-1703"

    def test_place_only(self):
        """Test parsing place without date"""
        place, date = self.parser.parse_place_date("Amsterdam")
        # Without a date pattern, the whole string becomes the place
        assert place == "Amsterdam"
        assert date is None

    def test_complex_place_name(self):
        """Test parsing complex place name"""
        place, date = self.parser.parse_place_date("Cuijk en St. Agatha 02-02-1852")
        assert place == "Cuijk en St. Agatha"
        assert date == "02-02-1852"


class TestParseDate:
    """Tests for parse_date() function"""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_full_date(self):
        """Test parsing full date DD-MM-YYYY"""
        date = self.parser.parse_date("05-01-1885")
        assert date == "05-01-1885"

    def test_year_only(self):
        """Test parsing year only"""
        date = self.parser.parse_date("1932")
        assert date == "1932"

    def test_approximate_year(self):
        """Test parsing approximate year"""
        date = self.parser.parse_date("±1675")
        assert date == "±1675"

    def test_before_year(self):
        """Test parsing year with < (before) symbol"""
        date = self.parser.parse_date("<1800")
        assert date == "<1800"

    def test_after_year(self):
        """Test parsing year with > (after) symbol"""
        date = self.parser.parse_date(">1900")
        assert date == ">1900"

    def test_circa_with_space(self):
        """Test parsing circa with space after symbol"""
        date = self.parser.parse_date("± 1750")
        assert date == "± 1750"

    def test_date_with_text(self):
        """Test extracting date from text with other content"""
        date = self.parser.parse_date("geboren op 30-06-1703 in Amsterdam")
        assert date == "30-06-1703"

    def test_date_with_text_and_symbol(self):
        """Test extracting date with symbol from text"""
        date = self.parser.parse_date("geboren ±1645 in Delft")
        assert date == "±1645"

    def test_no_date(self):
        """Test when no date pattern is found"""
        date = self.parser.parse_date("geen datum hier")
        assert date is None


class TestNormalizeName:
    """Tests for normalize_name() function"""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_all_caps_to_title_case(self):
        """Test converting ALL-CAPS to Title Case"""
        name = self.parser.normalize_name("JOHANNES THOMASSEN")
        assert name == "Johannes Thomassen"

    def test_dutch_prepositions_lowercase(self):
        """Test Dutch prepositions remain lowercase"""
        name = self.parser.normalize_name("Jan VAN DEN Brunckom")
        assert name == "Jan van den Brunckom"

    def test_multiple_prepositions(self):
        """Test multiple prepositions"""
        name = self.parser.normalize_name("Maria VAN DER Loop")
        assert name == "Maria van der Loop"

    def test_preserve_mixed_case(self):
        """Test preserving already mixed case names"""
        name = self.parser.normalize_name("Jan Thomassen")
        assert name == "Jan Thomassen"

    def test_preserve_nn_abbreviation(self):
        """Test preserving NN abbreviation in caps"""
        name = self.parser.normalize_name("NN THOMASSEN")
        assert name == "NN Thomassen"

    def test_names_with_parentheses(self):
        """Test names with parentheses (nicknames/variants)"""
        name = self.parser.normalize_name("Johannes (Jan) THOMASSEN")
        assert name == "Johannes (Jan) Thomassen"


class TestParsePersonHeader:
    """Tests for parse_person_header() function"""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_basic_person_header(self):
        """Test basic person header parsing"""
        person = self.parser.parse_person_header("I.1 Joannes Thomissen [512]")
        assert person.generation_id == "I.1"
        assert person.ref_num == "512"
        assert "Joannes" in person.name

    def test_person_with_parent_reference(self):
        """Test person header with parent reference"""
        person = self.parser.parse_person_header("VIII.6 Henricus Remigius Maria (Harry) THOMASSEN, zn. van VII.5")
        assert person.generation_id == "VIII.6"
        assert person.parent_ref == "VII.5"
        assert person.sex == "M"  # zn. van = male

    def test_person_daughter_of(self):
        """Test person header with 'dr. van' (daughter of)"""
        person = self.parser.parse_person_header("IX.17 Catharina Maria Josephina (Tini) THOMASSEN, dr. van VIII.4")
        assert person.generation_id == "IX.17"
        assert person.parent_ref == "VIII.4"
        assert person.sex == "F"  # dr. van = female

    def test_generation_id_with_period(self):
        """Test generation ID with trailing period (VII.5.)"""
        person = self.parser.parse_person_header("VII.5. Albertus Hendrikus THOMASSEN, zn. van VI.3")
        assert person.generation_id == "VII.5"  # Period should be stripped
        assert person.parent_ref == "VI.3"

    def test_person_without_reference_number(self):
        """Test person without [ref] number"""
        person = self.parser.parse_person_header("II.1 Thomas Jans, zn. van I.1")
        assert person.generation_id == "II.1"
        assert person.ref_num is None
        assert person.parent_ref == "I.1"

    def test_invalid_header(self):
        """Test invalid header returns None"""
        person = self.parser.parse_person_header("Not a valid header")
        assert person is None

    def test_generation_id_with_space(self):
        """Test generation ID with space like 'IV. 1.' instead of 'IV.1'"""
        line = "IV. 1. Thomas Jans / Janse /Jansen, zn. van III.1 [64]"
        person = self.parser.parse_person_header(line)

        assert person is not None
        assert person.generation_id == "IV.1"  # Space should be removed
        assert person.name == "Thomas Jans / Janse /Jansen"
        assert person.ref_num == "64"
        assert person.parent_ref == "III.1"
        assert person.sex == "M"


class TestBirthDeathSameLineIntegration:
    """Integration tests for birth and death on same line"""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_birth_and_death_same_line(self):
        """Test parsing birth and death from same line"""
        # Create a person first
        person = self.parser.parse_person_header("VIII.4 Theodorus Albertus Maria (Theo) THOMASSEN, zn. van VII.5")
        self.parser.current_person = person
        self.parser.persons[person.generation_id] = person

        # Parse birth and death line
        self.parser.parse_line("* Oldenzaal 05-01-1885, † Venray 09-12-1978")

        assert person.birth_date == "05-01-1885"
        assert person.birth_place == "Oldenzaal"
        assert person.death_date == "09-12-1978"
        assert person.death_place == "Venray"

    def test_birth_death_marriage_same_line(self):
        """Test parsing birth, death, and marriage on same line"""
        person = self.parser.parse_person_header("VIII.8 Wilhelmus Antonius THOMASSEN, zn. van VII.6")
        self.parser.current_person = person
        self.parser.persons[person.generation_id] = person

        # Parse line with birth, death, and marriage
        self.parser.parse_line("* Breda 24-09-1893, † Breda 02-07-1946. RK Tr. 's-Hertogenbosch 27-11-1917 met")

        assert person.birth_date == "24-09-1893"
        assert person.birth_place == "Breda"
        assert person.death_date == "02-07-1946"
        assert person.death_place == "Breda"
        assert len(person.marriages) == 1
        assert person.marriages[0].marriage_date == "27-11-1917"
        assert person.marriages[0].marriage_place == "'s-Hertogenbosch"


class TestGedcomGeneration:
    """Tests for GEDCOM generation and ID assignment"""

    def test_no_duplicate_ids_with_ref_nums(self):
        """Test that persons without ref_num don't get duplicate IDs"""
        parser = StamboomParser()

        # Create persons with ref_num (like V.1 with [32])
        person1 = Person("V.1", "32")
        person1.name = "Jo(h)annes (Jan) Thomassen"
        parser.persons["V.1"] = person1

        # Create many persons without ref_num (like IX.5)
        # This simulates having 32+ persons without ref_num
        for i in range(1, 35):
            person = Person(f"IX.{i}", None)
            person.name = f"Test Person {i}"
            parser.persons[f"IX.{i}"] = person

        # Generate GEDCOM to a temporary string
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ged') as f:
            temp_path = f.name

        try:
            parser.generate_gedcom(temp_path)

            # Read the generated GEDCOM and check for duplicate IDs
            with open(temp_path, 'r') as f:
                content = f.read()

            # Extract all INDI IDs
            import re
            indi_ids = re.findall(r'0 (@I\d+@) INDI', content)

            # Check for duplicates
            unique_ids = set(indi_ids)
            assert len(indi_ids) == len(unique_ids), f"Found duplicate IDs: {len(indi_ids)} total, {len(unique_ids)} unique"

            # Verify person with ref_num 32 has ID @I32@
            assert '@I32@' in indi_ids, "Person with ref_num [32] should have ID @I32@"

            # Verify no other person has @I32@
            assert indi_ids.count('@I32@') == 1, "Only one person should have ID @I32@"

        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestMarriageClass:
    """Tests for Marriage class structure"""

    def test_marriage_initialization(self):
        """Test Marriage class initialization"""
        marriage = Marriage()
        assert marriage.marriage_num == 1
        assert marriage.spouse_name == ""
        assert marriage.spouse_father_name is None
        assert marriage.spouse_mother_name is None
        assert marriage.marriage_date is None
        assert marriage.marriage_place is None

    def test_marriage_with_spouse_parents(self):
        """Test Marriage can store spouse parent info"""
        marriage = Marriage()
        marriage.spouse_name = "Jacinta Lucia Maria Coppens"
        marriage.spouse_father_name = "Benignus Joseph Coppens"
        marriage.spouse_mother_name = "Cornelia Francisca Xaveria Story"

        assert marriage.spouse_father_name == "Benignus Joseph Coppens"
        assert marriage.spouse_mother_name == "Cornelia Francisca Xaveria Story"


class TestChildrenWithMarriages:
    """Tests for parsing children who themselves have marriages"""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_child_marriage_spouse_not_parsed_as_child(self):
        """Test that spouse names of children are not parsed as children themselves"""
        # Simulate parsing a parent and their children where one child gets married
        text = """V.1. Johannes THOMASSEN, zn. van IV.1 [32]
* Heeswijk 1757, † Cuyk 08-10-1829
Tr. RK Cuyk 11-05-1794 met
Maria ABEN [33]
Hieruit:
Thomas THOMASSEN
Δ RK Cuyk 04-06-1795
Anna Maria THOMASSEN
* Cuijk 28-05-1799, † Cuijk 15-12-1847
Tr. Cuijk 01-05-1829 met
Franciscus VAN LOTTUM
* Cuijk 28-05-1799
Gertruda THOMASSEN
* Cuijk 10-12-1812
Tr. Cuijk 07-05-1849 met
Joannes TIESSEN
* Cuijk 22-12-1810
"""
        self.parser.parse(text)

        # V.1 should exist
        assert "V.1" in self.parser.persons
        person = self.parser.persons["V.1"]

        # Should have exactly 3 named children (Thomas, Anna Maria, Gertruda)
        # The spouses (Franciscus VAN LOTTUM, Joannes TIESSEN) should NOT be counted as children
        unnamed_children_count = len([c for c in self.parser.unnamed_children if c.parent_ref == "V.1"])
        assert unnamed_children_count == 3, f"Expected 3 unnamed children, got {unnamed_children_count}"

        # Verify the child names
        child_names = [c.name for c in self.parser.unnamed_children if c.parent_ref == "V.1"]
        assert "Thomas Thomassen" in child_names
        assert "Anna Maria Thomassen" in child_names
        assert "Gertruda Thomassen" in child_names

        # Spouse names should NOT be in children
        assert "Franciscus Van Lottum" not in child_names
        assert "Joannes Tiessen" not in child_names


class TestPersonClass:
    """Tests for Person class structure"""

    def test_person_initialization(self):
        """Test Person class initialization"""
        person = Person("I.1", "512")
        assert person.generation_id == "I.1"
        assert person.ref_num == "512"
        assert person.name == ""
        assert person.marriages == []
        assert person.children == []

    def test_person_add_marriage(self):
        """Test adding marriage to person"""
        person = Person("I.1", "512")
        marriage = Marriage()
        person.marriages.append(marriage)

        assert len(person.marriages) == 1
        assert person.marriages[0] == marriage

    def test_person_add_children(self):
        """Test adding children references to person"""
        person = Person("I.1", "512")
        person.children.append("II.1")
        person.children.append("II.2")

        assert len(person.children) == 2
        assert "II.1" in person.children
        assert "II.2" in person.children


class TestSpouseNameCleaning:
    """Tests for cleaning spouse names from marriage number markers"""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_remove_marriage_number_prefix(self):
        """Test that (1), (2), etc. are removed from spouse names"""
        text = """III.1 Jan THOMASSEN [128]
Tr. RK Beers 11-05-1727 met
(1) Jenneken EBBEN [129]
"""
        self.parser.parse(text)
        
        assert "III.1" in self.parser.persons
        person = self.parser.persons["III.1"]
        
        # Should have one marriage
        assert len(person.marriages) == 1
        
        # Spouse name should NOT have (1) prefix
        assert person.marriages[0].spouse_name == "Jenneken Ebben"
        assert not person.marriages[0].spouse_name.startswith("(1)")

    def test_remove_marriage_number_and_reference(self):
        """Test that both (1) and [xxx] are removed"""
        text = """III.1 Jan THOMASSEN [128]
Tr. RK Beers 11-05-1727 met
(2) Maria JANSEN [256]
"""
        self.parser.parse(text)
        
        person = self.parser.persons["III.1"]
        
        # Spouse name should have neither (2) nor [256]
        assert person.marriages[0].spouse_name == "Maria Jansen"
        assert "(2)" not in person.marriages[0].spouse_name
        assert "[256]" not in person.marriages[0].spouse_name


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestURLFiltering:
    """Tests for filtering URLs from being parsed as names"""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_url_after_marriage_not_parsed_as_spouse(self):
        """Test that URLs after marriage 'met' are not parsed as spouse names"""
        text = """III.1 Jan RUTJES [128]
Tr. RK Zyfflich 08-05-1770 met
http://members.multimania.nl/fkroesarts/huwelijken_zyfflich_1745-1802.htm
Theodora VOS
"""
        self.parser.parse(text)
        
        assert "III.1" in self.parser.persons
        person = self.parser.persons["III.1"]
        
        # Should have one marriage
        assert len(person.marriages) == 1
        
        # Spouse should be Theodora VOS, not the URL
        assert person.marriages[0].spouse_name == "Theodora Vos"
        assert "multimania" not in person.marriages[0].spouse_name.lower()

    def test_url_with_www_filtered(self):
        """Test that URLs starting with www. are filtered"""
        text = """III.1 Jan RUTJES [128]
Tr. RK Zyfflich 08-05-1770 met
www.example.com/genealogy
Maria JANSSEN
"""
        self.parser.parse(text)
        
        person = self.parser.persons["III.1"]
        
        # Spouse should be Maria, not the URL
        assert person.marriages[0].spouse_name == "Maria Janssen"
        assert "example.com" not in person.marriages[0].spouse_name.lower()

    def test_long_text_not_parsed_as_child(self):
        """Test that long descriptive text is not parsed as child name"""
        text = """III.1 Jan RUTJES [128]
Tr. met Maria JANSSEN
Hieruit:
Zo'n 200 brieven van hem gericht aan zijn familie bevinden zich in het missiehuis te Nijmegen.
"""
        self.parser.parse(text)

        # No unnamed children with "brieven" or "200" in name
        all_child_names = [c.name for c in self.parser.unnamed_children]
        assert not any("brieven" in name.lower() for name in all_child_names)
        assert not any("200" in name for name in all_child_names)


class TestOccupationFiltering:
    """Test that Dutch occupations are not parsed as person names"""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_occupation_timmerman_not_parsed_as_child(self):
        """Test that 'Timmerman' (carpenter) is not parsed as a child name"""
        text = """VI.9 Antonie RUTJES [100]
Tr. Renkum 11-05-1861 met
Hermina PELGRIM
* Steenderen 1838/1839
Hieruit:
	•	Theodorus Joseph RUTJES
* Renkum 09-07-1862, † Renkum 14-05-1922
Timmerman
Tr. Renkum 12-05-1894 met
Petronella DEEGENS
"""
        self.parser.parse(text)

        # Check that Theodorus is parsed correctly
        assert "VI.9" in self.parser.persons
        person = self.parser.persons["VI.9"]

        # Should have unnamed children for Theodorus Joseph Rutjes
        # but NOT for "Timmerman" (which is his occupation)
        child_names = [c.name for c in self.parser.unnamed_children if c.parent_ref == "VI.9"]

        # Should have exactly 1 child: Theodorus Joseph Rutjes
        assert len(child_names) == 1
        assert "Theodorus Joseph Rutjes" in child_names[0]

        # Should NOT have "Timmerman" as a child
        assert not any("timmerman" in name.lower() for name in child_names)

    def test_occupation_with_year_filtered(self):
        """Test that occupation with year like 'Timmerman (1938)' is filtered"""
        text = """V.1 Jan RUTJES [50]
Tr. Ewijk 28-12-1922 met
Maria LELIVELD
* Beuningen 1895/1896, zn. van Willem Lelivelt en Hendri±Mulders. Timmerman (1938).
Hieruit:
	•	Piet RUTJES
"""
        self.parser.parse(text)

        # Check unnamed children - should only have Piet, not "Timmerman"
        child_names = [c.name for c in self.parser.unnamed_children if c.parent_ref == "V.1"]
        assert len(child_names) == 1
        assert "Piet Rutjes" in child_names[0]
        assert not any("timmerman" in name.lower() for name in child_names)

    def test_surname_timmerman_still_recognized(self):
        """Test that 'Timmerman' as a surname (with first name) is still parsed"""
        text = """V.1 Jan RUTJES [50]
Tr. met
Hermina PELGRIM
Hieruit:
	•	Gillis TIMMERMAN
* Delft 1800
"""
        self.parser.parse(text)

        # "Gillis Timmerman" should be parsed as a child (has first name)
        child_names = [c.name for c in self.parser.unnamed_children if c.parent_ref == "V.1"]
        assert len(child_names) == 1
        assert "Gillis Timmerman" in child_names[0]

    def test_occupation_with_trailing_period_filtered(self):
        """Test that occupation with trailing period like 'Landbouwer.' is filtered"""
        text = """VI.1 Johannes BRUIJNS [100]
* Zevenaar 1832, † Zevenaar 10-02-1874.
Landbouwer.
Tr. Zevenaar 08-07-1871 met
Helena ROSS
Hieruit:
	•	Bernardus BRUIJNS
"""
        self.parser.parse(text)

        # Should NOT have "Landbouwer" or "Landbouwer." as a child
        child_names = [c.name for c in self.parser.unnamed_children if c.parent_ref == "VI.1"]
        assert len(child_names) == 1
        assert "Bernardus Bruijns" in child_names[0]
        assert not any("landbouwer" in name.lower() for name in child_names)


class TestBSReferenceFiltering:
    """Test that BS (burgerlijke stand / civil registry) references are filtered from parent names"""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_bs_reference_removed_from_mother_name(self):
        """Test that BS reference is removed from mother's name in spouse parent info"""
        text = """V.1 Jan RUTJES [100]
Tr. Bemmel 12-11-1890 met
Bernardina KIEVITS
* Doornenburg 20-07-1867, dr. van Antoon Kievits en Johanna Janssen (BS Bemmel 1923 O 69).
"""
        self.parser.parse(text)

        person = self.parser.persons["V.1"]
        assert len(person.marriages) == 1
        marriage = person.marriages[0]

        # Mother name should be "Johanna Janssen" without the BS reference
        assert marriage.spouse_mother_name == "Johanna Janssen"
        assert "BS" not in marriage.spouse_mother_name
        assert "O 69" not in marriage.spouse_mother_name

    def test_bs_reference_removed_from_father_name(self):
        """Test that BS reference is removed from father's name"""
        text = """V.1 Jan RUTJES [100]
Tr. met
Maria KRIJNEN
* Beuningen 1835/1836, dr. van Leonardus Krijnen (BS Beuningen 1911 O 45) en Hendrica Kouweberg.
"""
        self.parser.parse(text)

        person = self.parser.persons["V.1"]
        marriage = person.marriages[0]

        # Father name should be "Leonardus Krijnen" without the BS reference
        assert marriage.spouse_father_name == "Leonardus Krijnen"
        assert "BS" not in marriage.spouse_father_name

    def test_bs_reference_both_parents(self):
        """Test BS reference removal when both parents have references"""
        text = """V.1 Jan RUTJES [100]
Tr. met
Anna GEURTS
* Huissen 23-04-1859, dr. van Albertus Geurts (BS Huissen 1920 O 5) en Johanna Koenen (BS Bemmel 1924 O 3).
"""
        self.parser.parse(text)

        person = self.parser.persons["V.1"]
        marriage = person.marriages[0]

        assert marriage.spouse_father_name == "Albertus Geurts"
        assert marriage.spouse_mother_name == "Johanna Koenen"
        assert "BS" not in marriage.spouse_father_name
        assert "BS" not in marriage.spouse_mother_name


class TestMarriagePatterns:
    """Test various marriage patterns (Tr., Otr., Ondertr.)"""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_ondertr_marriage_pattern(self):
        """Test that 'Ondertr. / tr.' (full ondertrouw/trouwen) is recognized as marriage"""
        text = """I.1 Paulus RUTGERS [288]
* ±1672. ▭ Kekerdom 18-04-1723.
Ondertr. / tr. Gendt 01-08/22-08-1697 met Maria VAN BERCK [289]
△ Zyfflich 16-11-1679
Hieruit:
	•	Joannes RUTJES
* 1699/1700
	•	Aldegondis RUTJES, ±1700, zie II.1
"""
        self.parser.parse(text)

        person = self.parser.persons["I.1"]

        # Should have recognized the marriage
        assert len(person.marriages) == 1

        # Should have parsed the marriage date and place
        marriage = person.marriages[0]
        assert marriage.marriage_date == "22-08-1697"
        assert marriage.marriage_place == "Gendt 01-08/"

        # Should have parsed the spouse
        assert marriage.spouse_name == "Maria van Berck"

        # Should have children linked
        assert len(person.children) >= 1  # At least the "zie II.1" reference

    def test_relatie_met_pattern(self):
        """Test that 'Relatie met' (relationship with) is recognized as partnership"""
        text = """IV.1 Philippus WEETELING [80]
† Delft 1778-1783.
Relatie met
Johanna (Hendrina) DE JONG(H) [81]
Hieruit:
	•	Philippus WEETELING, 1779, zie V.1
"""
        self.parser.parse(text)

        person = self.parser.persons["IV.1"]

        # Should have recognized the relationship as a marriage/partnership
        assert len(person.marriages) == 1

        # Should have parsed the partner name
        marriage = person.marriages[0]
        assert marriage.spouse_name == "Johanna (Hendrina) de Jong(h)"

        # Should have the child reference (as tuple with marriage_num)
        assert ("V.1", 1) in person.children

    def test_nn_nomen_nescio_spouse(self):
        """Test that 'NN' (nomen nescio = unknown name) is recognized as valid spouse name"""
        text = """I.1 Joannes Thomissen [512]
* ±1645
Tr. met
NN
Hieruit:
Thomas Jans, ±1660, zie II.1
"""
        self.parser.parse(text)

        person = self.parser.persons["I.1"]

        # Should have recognized the marriage
        assert len(person.marriages) == 1

        # Should have parsed "NN" as spouse name, not "Thomas Jans"
        marriage = person.marriages[0]
        assert marriage.spouse_name == "NN"
        assert marriage.spouse_name != "Thomas Jans"

        # Should have the child reference (as tuple with marriage_num)
        assert ("II.1", 1) in person.children


class TestSurnameWithPreposition:
    """Test surname detection when name has slashes AND Dutch prepositions"""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_given_name_variants_with_surname_preposition(self):
        """Test that 'Walravius / Walramus VAN BENTHUM' correctly identifies van Benthum as surname"""
        text = """II.1 Aldegondis RUTJES [128]
Tr. RK Leuth 25-04-1736 met
(2) Walravius / Walramus (Walramen) VAN BENTHUM
* en △ Kekerdom 04-05-1709, † en ▭ Kekerdom 18-11 / 22-11-1753
"""
        self.parser.parse(text)

        # Generate GEDCOM to check name formatting
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ged', delete=False) as f:
            temp_file = f.name

        try:
            self.parser.generate_gedcom(temp_file)

            # Read GEDCOM and check name formatting
            with open(temp_file, 'r', encoding='utf-8') as f:
                gedcom_content = f.read()

            # Should have "Walravius of Walramus" as given name and "van Benthum" as surname
            # "/" in given name replaced by "of" to avoid GEDCOM surname delimiter conflict
            assert "1 NAME Walravius of Walramus /van Benthum/" in gedcom_content

            # Should NOT have the old incorrect format where "/" is in surname
            assert "1 NAME Walravius // Walramus van Benthum/" not in gedcom_content

        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_surname_variants_without_preposition(self):
        """Test that 'Agnes Rutjes / Rutjens' still works (surname variants without preposition)"""
        text = """V.10 AGNES RUTJES / RUTJENS
* Millingen 1803
"""
        self.parser.parse(text)

        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ged', delete=False) as f:
            temp_file = f.name

        try:
            self.parser.generate_gedcom(temp_file)

            with open(temp_file, 'r', encoding='utf-8') as f:
                gedcom_content = f.read()

            # Should have "Agnes" as given name and "Rutjes / Rutjens" as surname
            assert "1 NAME Agnes /Rutjes / Rutjens/" in gedcom_content

        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)


class TestTrailingPunctuation:
    """Test that trailing punctuation in source lines does not end up as a person's surname"""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_child_with_trailing_period_not_punctuation_surname(self):
        """Test that 'PELT (Vaals).' does not produce '.' as surname in GEDCOM"""
        text = """VIII.7 Johannes PELT
* Vijlen 15-02-1891
Tr. Vaals 10-04-1920 met
Maria THOMASSEN
Hieruit:
Theodorus Jozef Maria (Theo) PELT (Vaals).
Remigius Jozef Maria PELT, zie IX.30
"""
        self.parser.parse(text)

        import tempfile
        import os
        import re
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ged', delete=False) as f:
            temp_file = f.name

        try:
            self.parser.generate_gedcom(temp_file)

            with open(temp_file, 'r', encoding='utf-8') as f:
                gedcom_content = f.read()

            name_lines = [line for line in gedcom_content.splitlines() if line.startswith("1 NAME")]

            # No person should have a punctuation-only surname (no letters between /.../)
            for name_line in name_lines:
                surname_match = re.search(r'/([^/]+)/', name_line)
                if surname_match:
                    surname = surname_match.group(1)
                    assert re.search(r'[A-Za-z]', surname), \
                        f"Surname '{surname}' contains no letters in: {name_line}"

            # Theo Pelt should have 'Pelt' as surname, not '.'
            assert any("Theo" in line and "/Pelt/" in line for line in name_lines), \
                "Expected Theo Pelt to have surname 'Pelt'"

        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_child_name_trailing_period_stripped(self):
        """Test that trailing period is stripped from child name during parsing"""
        text = """I.1 Jan JANSEN
Tr. 1900 met
Maria SMIT
Hieruit:
Pieter JANSEN.
"""
        self.parser.parse(text)
        child_names = [c.name for c in self.parser.unnamed_children if c.parent_ref == "I.1"]
        assert len(child_names) == 1
        assert not child_names[0].endswith("."), \
            f"Child name should not end with '.': {child_names[0]}"
        assert "Pieter" in child_names[0]


class TestBaptismOnBirthLine:
    """Tests voor doop-info (△) op dezelfde regel als geboorte (*)"""

    def setup_method(self):
        self.parser = StamboomParser()
        person = self.parser.parse_person_header("III.1 Joannes RUTJES, zn. van II.1")
        self.parser.current_person = person
        self.parser.persons[person.generation_id] = person

    def test_birth_then_baptism_separate_place(self):
        """'* Erlecom, △ Kekerdom 10-04-1712' → aparte geboorte- en doopplaats"""
        self.parser.parse_line("* Erlecom, △ Kekerdom 10-04-1712")
        p = self.parser.current_person
        assert p.birth_place == "Erlecom"
        assert p.birth_date is None
        assert p.baptism_place == "Kekerdom"
        assert p.baptism_date == "10-04-1712"

    def test_birth_then_baptism_same_place_and_date(self):
        """'* en △ Kekerdom 04-05-1709' → zelfde plaats en datum voor geboorte en doop"""
        self.parser.parse_line("* en △ Kekerdom 04-05-1709")
        p = self.parser.current_person
        assert p.birth_place == "Kekerdom"
        assert p.birth_date == "04-05-1709"
        assert p.baptism_place == "Kekerdom"
        assert p.baptism_date == "04-05-1709"

    def test_birth_slash_baptism_same_date(self):
        """'* / △ Delft 22-05-1814' → zelfde datum en plaats voor geboorte en doop"""
        self.parser.parse_line("* / △ Delft 22-05-1814")
        p = self.parser.current_person
        assert p.birth_place == "Delft"
        assert p.birth_date == "22-05-1814"
        assert p.baptism_place == "Delft"
        assert p.baptism_date == "22-05-1814"

    def test_birth_slash_baptism_same_place_different_dates(self):
        """'* / △ Appeldorn 14-05 / 26-05-1816' → zelfde plaats, geboorte 14-05, doop 26-05"""
        self.parser.parse_line("* / △ Appeldorn 14-05 / 26-05-1816")
        p = self.parser.current_person
        assert p.birth_place == "Appeldorn"
        assert p.birth_date == "14-05-1816"
        assert p.baptism_place == "Appeldorn"
        assert p.baptism_date == "26-05-1816"

    def test_birth_slash_baptism_both_full_dates(self):
        """'* / △ Kekerdom 04-05-1709 / 12-05-1709' → beide volledige data"""
        self.parser.parse_line("* / △ Kekerdom 04-05-1709 / 12-05-1709")
        p = self.parser.current_person
        assert p.birth_place == "Kekerdom"
        assert p.birth_date == "04-05-1709"
        assert p.baptism_place == "Kekerdom"
        assert p.baptism_date == "12-05-1709"

    def test_birth_baptism_and_death_same_line(self):
        """'* Erlecom, △ Kekerdom 10-04-1712, gett. X, † Ooij 1827' → alle drie opgeslagen"""
        self.parser.parse_line("* Erlecom, △ Kekerdom 10-04-1712, gett. Arnoldus Schippereijn en Wendel Sondagh, † Ooij 23-08-1827")
        p = self.parser.current_person
        assert p.birth_place == "Erlecom"
        assert p.baptism_place == "Kekerdom"
        assert p.baptism_date == "10-04-1712"
        assert p.death_place == "Ooij"
        assert p.death_date == "23-08-1827"

    def test_baptism_witnesses_on_birth_line(self):
        """'* Vierlingsbeek, △ RK Overloon 06-03-1742, gett. Thijs Thomesen en Jenneke Roeffen'"""
        self.parser.parse_line("* Vierlingsbeek, △ RK Overloon 06-03-1742, gett. Thijs Thomesen en Jenneke Roeffen")
        p = self.parser.current_person
        assert p.birth_place == "Vierlingsbeek"
        assert p.baptism_place == "RK Overloon"
        assert p.baptism_date == "06-03-1742"
        assert "Thijs Thomesen" in p.baptism_witnesses

    def test_only_birth_no_baptism(self):
        """'* Rotterdam 15-03-1850' → alleen geboorte, geen doop"""
        self.parser.parse_line("* Rotterdam 15-03-1850")
        p = self.parser.current_person
        assert p.birth_place == "Rotterdam"
        assert p.birth_date == "15-03-1850"
        assert p.baptism_place is None
        assert p.baptism_date is None

    def test_child_birth_and_baptism_same_line(self):
        """Doop op geboortegel wordt ook voor naamloze kinderen opgeslagen"""
        child = Person("child_1", None)
        child.name = "Jan RUTJES"
        self.parser.in_children_section = True
        self.parser.current_child = child
        self.parser.parse_line("* Zeeland, △ Leuth 24-10-1736, gett. Henricus van Colck en Aleidis Huijsman")
        assert child.birth_place == "Zeeland"
        assert child.baptism_place == "Leuth"
        assert child.baptism_date == "24-10-1736"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
