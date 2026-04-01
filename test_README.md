# Unit Tests voor Stamboom Parser

## Overzicht

Deze test suite bevat 37 unit tests voor de `import_stamboom_doc.py` parser.

## Tests Uitvoeren

```bash
# Activeer virtual environment
source venv/bin/activate

# Run alle tests
pytest test_stamboom_parser.py -v

# Run specifieke test class
pytest test_stamboom_parser.py::TestParseSpouseParents -v

# Run met coverage
pytest test_stamboom_parser.py --cov=import_stamboom_doc --cov-report=html
```

## Test Coverage

### Kern Functionaliteit (37 tests)

#### 1. **parse_spouse_parents()** - 7 tests
- Basis ouder extractie (vader en moeder)
- Filtering van beroepen (bibliothecaris, winkelierster, bakker, etc.)
- Filtering van religieuze markers (RK, NG, Hervormd)
- Filtering van meerdere info stukken (beroep + adres + religie)
- "zn. van" en "dr. van" patronen

#### 2. **parse_place_date()** - 6 tests
- Plaats en datum samen
- Alleen plaats of alleen datum
- Complexe plaatsnamen (Cuijk en St. Agatha)
- Jaar met ± symbool

#### 3. **parse_date()** - 5 tests
- Volledige datum (DD-MM-YYYY)
- Alleen jaar
- Geschatte jaren (±YYYY)
- Datum extractie uit tekst

#### 4. **normalize_name()** - 6 tests
- ALL-CAPS naar Title Case conversie
- Nederlandse tussenvoegsels (van, de, den, der) lowercase
- Meerdere tussenvoegsels
- NN abbreviatie behouden
- Namen met haakjes (bijnamen)

#### 5. **parse_person_header()** - 6 tests
- Basis persoon header parsing
- Generatie IDs met optionele punt (VII.5 en VII.5.)
- Ouder referenties (zn. van / dr. van)
- Referentie nummers [xxx]
- Geslacht detectie uit patronen

#### 6. **Integratie Tests** - 2 tests
- Geboorte en sterfte op dezelfde regel
- Geboorte, sterfte EN huwelijk op dezelfde regel

#### 7. **Class Structure Tests** - 5 tests
- Marriage class initialisatie en velden
- Person class initialisatie en velden
- Toevoegen van huwelijken en kinderen

## Belangrijke Test Cases

### Ouder Parsing met Filtering
```python
# Input:
"dr. van Michael van Breij en Anna Catharina Teeuwen. Winkelierster. Molenstraat 84"

# Output:
father = "Michael van Breij"
mother = "Anna Catharina Teeuwen"  # Beroep en adres gefilterd
```

### Generatie ID met Punt
```python
# Input:
"VII.5. Albertus Hendrikus BAKKER, zn. van VI.3"

# Output:
generation_id = "VII.5"  # Punt correct verwijderd
parent_ref = "VI.3"
```

### Geboorte en Sterfte op Zelfde Regel
```python
# Input:
"* Oldenzaal 05-01-1885, † Venray 09-12-1978"

# Output:
birth_date = "05-01-1885"
birth_place = "Oldenzaal"
death_date = "09-12-1978"
death_place = "Venray"
```

## Toevoegen van Nieuwe Tests

Bij het toevoegen van nieuwe functionaliteit:

1. Voeg tests toe aan de relevante test class
2. Gebruik descriptive test namen: `test_<wat>_<verwacht_resultaat>`
3. Voeg docstrings toe die uitleggen wat de test doet
4. Test zowel normale cases als edge cases
5. Run alle tests om regressies te voorkomen

## Continuous Integration

Deze tests kunnen worden geïntegreerd in een CI/CD pipeline:

```yaml
# Voorbeeld voor GitHub Actions
- name: Run tests
  run: |
    source venv/bin/activate
    pytest test_stamboom_parser.py -v --junitxml=test-results.xml
```

## Bekende Beperkingen

- Tests gebruiken mock data, niet de echte Word documenten
- GEDCOM generatie wordt niet getest (alleen parsing)
- File I/O operaties worden niet getest
- Volledige integratie tests ontbreken nog
