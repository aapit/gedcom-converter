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

    def test_date_with_text(self):
        """Test extracting date from text with other content"""
        date = self.parser.parse_date("geboren op 30-06-1703 in Amsterdam")
        assert date == "30-06-1703"

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
