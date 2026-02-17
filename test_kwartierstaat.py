#!/usr/bin/env python3
"""Unit tests for kwartierstaat converter"""

import pytest
from import_kwartierstaat import GedcomGenerator


class TestParsePlaceYear:
    """Test parse_place_year method with various date formats"""

    def setup_method(self):
        self.gedcom = GedcomGenerator()

    def test_year_with_circa_symbol(self):
        """Test that ± symbol is preserved in year"""
        place, year = self.gedcom.parse_place_year("Amsterdam ±1850")
        assert place == "Amsterdam"
        assert year == "±1850"

    def test_year_with_before_symbol(self):
        """Test that < symbol is preserved in year"""
        place, year = self.gedcom.parse_place_year("Utrecht <1800")
        assert place == "Utrecht"
        assert year == "<1800"

    def test_year_with_after_symbol(self):
        """Test that > symbol is preserved in year"""
        place, year = self.gedcom.parse_place_year("Den Haag >1900")
        assert place == "Den Haag"
        assert year == ">1900"

    def test_year_with_space_after_symbol(self):
        """Test year with space after symbol"""
        place, year = self.gedcom.parse_place_year("Rotterdam ± 1750")
        assert place == "Rotterdam"
        assert year == "± 1750"

    def test_regular_year_without_symbol(self):
        """Test regular year without special characters"""
        place, year = self.gedcom.parse_place_year("Delft 1850")
        assert place == "Delft"
        assert year == "1850"

    def test_year_only(self):
        """Test with only year, no place"""
        place, year = self.gedcom.parse_place_year("±1850")
        assert place is None
        assert year == "±1850"

    def test_place_only(self):
        """Test with only place, no year"""
        place, year = self.gedcom.parse_place_year("Amsterdam")
        assert place == "Amsterdam"
        assert year is None

    def test_with_geb_prefix(self):
        """Test that 'Geb.' prefix is removed from place"""
        place, year = self.gedcom.parse_place_year("Geb. Rotterdam 1850")
        assert place == "Rotterdam"
        assert year == "1850"


class TestNameParsing:
    """Test name parsing with Dutch prepositions and abbreviations"""

    def setup_method(self):
        self.gedcom = GedcomGenerator()

    def test_name_with_a_d_abbreviation(self):
        """Test that a/d (aan de) is part of surname"""
        # Add a person to test name formatting
        self.gedcom.add_individual(2, "Arnoldus Willems a/d Rooijendijk", None, None, None)

        # Generate GEDCOM to a string
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ged', delete=False) as f:
            temp_file = f.name

        try:
            self.gedcom.generate_gedcom(temp_file)

            # Read and check the GEDCOM
            with open(temp_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Should have "Arnoldus" as given name and "Willems a/d Rooijendijk" as surname
            assert "1 NAME Arnoldus /Willems a/d Rooijendijk/" in content

        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_name_with_v_d_abbreviation(self):
        """Test that v/d (van de) is part of surname"""
        self.gedcom.add_individual(2, "Jan Jansen v/d Berg", None, None, None)

        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ged', delete=False) as f:
            temp_file = f.name

        try:
            self.gedcom.generate_gedcom(temp_file)

            with open(temp_file, 'r', encoding='utf-8') as f:
                content = f.read()

            assert "1 NAME Jan /Jansen v/d Berg/" in content

        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_name_with_regular_preposition(self):
        """Test regular prepositions still work"""
        self.gedcom.add_individual(2, "Maria van den Brink", None, None, None)

        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ged', delete=False) as f:
            temp_file = f.name

        try:
            self.gedcom.generate_gedcom(temp_file)

            with open(temp_file, 'r', encoding='utf-8') as f:
                content = f.read()

            assert "1 NAME Maria /van den Brink/" in content

        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_simple_name_without_preposition(self):
        """Test simple name without prepositions"""
        self.gedcom.add_individual(2, "Pieter Janssen", None, None, None)

        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ged', delete=False) as f:
            temp_file = f.name

        try:
            self.gedcom.generate_gedcom(temp_file)

            with open(temp_file, 'r', encoding='utf-8') as f:
                content = f.read()

            assert "1 NAME Pieter /Janssen/" in content

        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_variant_first_names_with_slash(self):
        """Test variant first names separated by slash"""
        self.gedcom.add_individual(2, "Willemina / Maria Daniels", None, None, None)

        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ged', delete=False) as f:
            temp_file = f.name

        try:
            self.gedcom.generate_gedcom(temp_file)

            with open(temp_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Should have "Willemina / Maria" as given names and "Daniels" as surname
            assert "1 NAME Willemina / Maria /Daniels/" in content

        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
