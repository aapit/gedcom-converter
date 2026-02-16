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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
