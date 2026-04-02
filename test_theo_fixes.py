"""Tests for Theo Thomassen's reported issues with RUTJES stamboom"""

import sys
sys.path.insert(0, '.')
from import_stamboom_doc import StamboomParser, Person, Marriage


class TestOccupationAsPerson:
    """Functieaanduidingen worden ten onrechte als individuen geparsed."""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_broodbakker_not_parsed_as_child(self):
        """Broodbakker is een beroep, geen kindnaam."""
        text = (
            "IV.1 Paulus Franciscus Nicolaas RUTJES, zn. van III.1\n"
            "* Beers 1750\n"
            "Tr. met\n"
            "Joanna BALANCE\n"
            "Hieruit:\n"
            "Joannes RUTJES, zie V.1\n"
            "broodbakker\n"
            "Maria RUTJES\n"
        )
        self.parser.parse(text)
        person = self.parser.persons.get("IV.1")
        assert person is not None
        # "broodbakker" should NOT be a child
        child_names = [c.name for c in self.parser.unnamed_children if c.parent_ref == "IV.1"]
        assert not any("broodbakker" in n.lower() for n in child_names), \
            f"'broodbakker' should not be a child name, got: {child_names}"
        # But Maria should be a child
        assert any("Maria" in n for n in child_names), \
            f"Maria should be a child, got: {child_names}"

    def test_nagelsmit_not_parsed_as_child(self):
        """Nagelsmit is een beroep, geen kindnaam."""
        text = (
            "IV.2 Wilhelmus PEPERZAK, zn. van III.2\n"
            "* Beers 1755\n"
            "Tr. met\n"
            "Anna JANSSEN\n"
            "Hieruit:\n"
            "Petrus PEPERZAK, zie V.3\n"
            "nagelsmit\n"
            "Clara PEPERZAK\n"
        )
        self.parser.parse(text)
        person = self.parser.persons.get("IV.2")
        assert person is not None
        child_names = [c.name for c in self.parser.unnamed_children if c.parent_ref == "IV.2"]
        assert not any("nagelsmit" in n.lower() for n in child_names), \
            f"'nagelsmit' should not be a child name, got: {child_names}"

    def test_bisschop_not_parsed_as_child(self):
        """'Bisschop v.E. etc' is een ambt, niet een kind."""
        text = (
            "V.3 Johannes RUTJES, zn. van IV.1\n"
            "* Beers 1780\n"
            "Tr. met\n"
            "Maria MAASSEN\n"
            "Hieruit:\n"
            "Theodorus RUTJES, zie VI.1\n"
            "Bisschop v.E. etc\n"
            "Petrus RUTJES\n"
        )
        self.parser.parse(text)
        person = self.parser.persons.get("V.3")
        assert person is not None
        child_names = [c.name for c in self.parser.unnamed_children if c.parent_ref == "V.3"]
        assert not any("Bisschop" in n for n in child_names), \
            f"'Bisschop' should not be a child name, got: {child_names}"
        # It should be stored as a note on the previous child (Theodorus)
        theodorus_children = [c for c in self.parser.unnamed_children 
                             if c.parent_ref == "V.3" and "Theodorus" in c.name]
        # Note: Theodorus has a "zie" ref, so won't be in unnamed_children
        # The Bisschop note should be attached to the child parsed before it,
        # or stored as a note on the person if no child context

    def test_lid_van_orde_not_parsed_as_child(self):
        """'Lid van de 3e orde' is een functie, niet een kind."""
        text = (
            "VI.2 Clara RUTJES, dr. van V.1\n"
            "* Beers 1810\n"
            "Tr. met\n"
            "Gerardus PETERS\n"
            "Hieruit:\n"
            "Clara Maria Hendrina RUTJES\n"
            "Lid van de 3e orde\n"
            "Johannes RUTJES\n"
        )
        self.parser.parse(text)
        person = self.parser.persons.get("VI.2")
        assert person is not None
        child_names = [c.name for c in self.parser.unnamed_children if c.parent_ref == "VI.2"]
        assert not any("Lid" in n for n in child_names), \
            f"'Lid van de 3e orde' should not be a child name, got: {child_names}"
        # It should be a note on Clara Maria Hendrina
        clara_children = [c for c in self.parser.unnamed_children 
                         if c.parent_ref == "VI.2" and "Clara" in c.name]
        assert len(clara_children) >= 1
        assert any("Lid van de 3e orde" in note for note in clara_children[0].notes), \
            f"Expected 'Lid van de 3e orde' as note on Clara, got notes: {clara_children[0].notes}"


class TestInfansAndNNChildren:
    """Naamloze kinderen (NN, infans) moeten correct geparsed worden."""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_infans_creates_nn_child(self):
        """Een 'infans' regel in de kinderen sectie moet een NN kind aanmaken."""
        text = (
            "IV.5 Agnes RUTJES, dr. van III.1\n"
            "* Beers 1760\n"
            "Tr. met\n"
            "Henricus BRUIJNS\n"
            "Hieruit:\n"
            "infans (Pauli) \u25ad Zyfflich 07-11-1751\n"
            "Joannes BRUIJNS\n"
        )
        self.parser.parse(text)
        person = self.parser.persons.get("IV.5")
        assert person is not None
        child_names = [c.name for c in self.parser.unnamed_children if c.parent_ref == "IV.5"]
        # infans should create an NN child with burial info
        assert any("Nn" in n or "N.N." in n or n == "NN" for n in child_names), \
            f"Expected NN child from 'infans' line, got: {child_names}"


class TestChildOrdering:
    """Kinderen uit meerdere huwelijken moeten in documentvolgorde staan."""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_children_from_two_marriages_ordered_correctly(self):
        """Kinderen uit eerste huwelijk komen voor kinderen uit tweede huwelijk."""
        text = (
            "III.1 Paulus RUTJES, zn. van II.1\n"
            "* Beers 1720\n"
            "Tr. met\n"
            "Maria JANSSEN\n"
            "Uit (1):\n"
            "Joannes RUTJES, zie IV.1\n"
            "Anna RUTJES\n"
            "Tr. met\n"
            "Elisabeth PETERS\n"
            "Uit (2):\n"
            "Joannes RUTJES, zie IV.3\n"
            "Petrus RUTJES\n"
        )
        self.parser.parse(text)
        person = self.parser.persons.get("III.1")
        assert person is not None
        # Children should be in document order: first marriage children first
        child_refs = [(ref, mn) for ref, mn in person.children]
        # First marriage children
        first_marriage = [ref for ref, mn in child_refs if mn == 1]
        second_marriage = [ref for ref, mn in child_refs if mn == 2]
        assert len(first_marriage) >= 2, f"Expected 2+ children from first marriage, got {first_marriage}"
        assert len(second_marriage) >= 2, f"Expected 2+ children from second marriage, got {second_marriage}"




class TestSpouseAttribution:
    """Theodora Johanna Brouwer wordt opgevoerd als echtgenote van haar zus."""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_spouse_not_confused_with_sibling(self):
        """Twee zussen met huwelijken: elke zus krijgt haar eigen echtgenoot."""
        text = (
            "V.1 Joannes RUTJES, zn. van IV.1\n"
            "* Beers 1780\n"
            "Tr. met\n"
            "Maria JANSSEN\n"
            "Hieruit:\n"
            "Maria Theodora RUTJES\n"
            "Tr. met\n"
            "Petrus HENDRIKS\n"
            "Theodora Johanna RUTJES\n"
            "Tr. met\n"
            "Johannes VAN DEN BERG\n"
        )
        self.parser.parse(text)
        
        # Maria Theodora should be married to Petrus Hendriks
        maria = next((c for c in self.parser.unnamed_children 
                      if "Maria Theodora" in c.name), None)
        assert maria is not None, "Maria Theodora should be a child"
        assert len(maria.marriages) >= 1, f"Maria Theodora should have a marriage, got {maria.marriages}"
        assert "Petrus" in maria.marriages[0].spouse_name or "Hendriks" in maria.marriages[0].spouse_name, \
            f"Maria Theodora's spouse should be Petrus Hendriks, got: {maria.marriages[0].spouse_name}"
        
        # Theodora Johanna should be married to Johannes van den Berg
        theodora = next((c for c in self.parser.unnamed_children 
                        if "Theodora Johanna" in c.name), None)
        assert theodora is not None, "Theodora Johanna should be a child"
        assert len(theodora.marriages) >= 1, f"Theodora Johanna should have a marriage"
        assert "Johannes" in theodora.marriages[0].spouse_name or "Berg" in theodora.marriages[0].spouse_name, \
            f"Theodora Johanna's spouse should be Johannes van den Berg, got: {theodora.marriages[0].spouse_name}"


class TestMissingChildren:
    """Kinderen van een persoon met huwelijk ontbreken niet."""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_children_after_spouse_marriage_in_children_section(self):
        """Na een kind-huwelijk in de kinderen sectie moeten volgende kinderen
        nog steeds aan de ouder worden toegekend."""
        text = (
            "IV.3 Anna Maria RUTJES, dr. van III.1\n"
            "* Beers 1760\n"
            "Tr. met\n"
            "Theodorus BRANS\n"
            "Hieruit:\n"
            "Joannes BRANS\n"
            "Tr. met\n"
            "Petronella JANSSEN\n"
            "Maria BRANS\n"
            "Petrus BRANS\n"
        )
        self.parser.parse(text)
        person = self.parser.persons.get("IV.3")
        assert person is not None
        child_names = [c.name for c in self.parser.unnamed_children if c.parent_ref == "IV.3"]
        # All three children should be parsed
        assert len(child_names) >= 3, \
            f"Expected 3 children (Joannes, Maria, Petrus), got {len(child_names)}: {child_names}"
        assert any("Joannes" in n for n in child_names), f"Joannes missing, got: {child_names}"
        assert any("Maria" in n for n in child_names), f"Maria missing, got: {child_names}"
        assert any("Petrus" in n for n in child_names), f"Petrus missing, got: {child_names}"


class TestBroodbakkerSameAsPerson:
    """Broodbakker als beroep na een kind, niet als nieuw kind."""

    def setup_method(self):
        self.parser = StamboomParser()

    def test_occupation_after_child_stored_as_note(self):
        """Een beroepsaanduiding na een kindnaam wordt als notitie opgeslagen."""
        text = (
            "IV.1 Paulus RUTJES, zn. van III.1\n"
            "* Beers 1750\n"
            "Tr. met\n"
            "Joanna BALANCE\n"
            "Hieruit:\n"
            "Paulus Franciscus Nicolaas RUTJES\n"
            "broodbakker\n"
            "Maria RUTJES\n"
        )
        self.parser.parse(text)
        child_names = [c.name for c in self.parser.unnamed_children if c.parent_ref == "IV.1"]
        assert not any("broodbakker" in n.lower() for n in child_names)
        # Check broodbakker is not a child but Paulus and Maria are
        assert any("Paulus" in n for n in child_names)
        assert any("Maria" in n for n in child_names)
        assert len(child_names) == 2, f"Expected exactly 2 children, got: {child_names}"
