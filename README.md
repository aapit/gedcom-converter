# Genealogie Data Converters

Deze repository bevat twee scripts voor het converteren van genealogische gegevens naar GEDCOM formaat:

1. **Kwartierstaat Converter** (`import_kwartierstaat.py`) - Converteert een Excel kwartierstaat naar GEDCOM
2. **Stamboom Converter** (`import_stamboom_doc.py`) - Converteert een Word stamboom document naar GEDCOM

---

## Stamboom Word Document Converter

Dit script converteert een Word (.doc) bestand met een gedetailleerde stamboom beschrijving naar GEDCOM formaat.

### Bestandsstructuur

Het Word document moet gestructureerd zijn met:
- **Legenda** bovenin met symbolen en afkortingen
- **Generaties** (Eerste generatie, Tweede generatie, etc.)
- **Personen** genummerd per generatie (I.1, II.1, III.1, etc.)

### Herkende elementen

Het script herkent automatisch:
- ✅ **Personen**: I.1, II.1, III.1, etc.
- ✅ **Geboren**: `*` (sterretje)
- ✅ **Gedoopt**: `△` of `Δ` (delta)
- ✅ **Overleden**: `†` (dagger)
- ✅ **Begraven**: `▭` of "begr."
- ✅ **Huwelijken**: "Otr.", "Tr.", "otr. / tr."
- ✅ **Geslacht**: "zn. van" (zoon) of "dr. van" (dochter)
- ✅ **Kinderen**: "Hieruit:", "Uit (1):", "Uit (2):"
- ✅ **Referenties**: [512], [256], etc.
- ✅ **Notities**: Archief verwijzingen en beschrijvingen

### Gebruik

```bash
# Activeer virtual environment
source venv/bin/activate

# Voer het script uit
python3 import_stamboom_doc.py
```

**Input**: `THOMASSEN 16 David.doc`
**Output**: `stamboom.ged`

### Vereisten

- macOS (gebruikt `textutil` voor .doc conversie)
- Python 3.6+
- Geen extra packages nodig (alleen standaard Python libraries)

### Output voorbeeld

```
Stamboom Word Document naar GEDCOM Converter
============================================================

Lezen van THOMASSEN 16 David.doc...
Document gelezen: 96873 karakters

Parsen van stamboom...
Gevonden: 64 personen

Voorbeeld personen:

  I.1: Joannes Thomissen
    Geboren: ±1645 in ?
    Huwelijken: 1
    Kinderen: 1 (refs: II.1)

Genereren van stamboom.ged...

✓ Klaar! GEDCOM bestand gegenereerd: stamboom.ged
  - 64 personen
  - Geschatte families: 87
```

### Voorbeeld Word structuur

```
Legenda:
uniek nummer    I.1, I.2 e.v.
naam            (voornaam en achternaam) vet gedrukt
geboren         *
gedoopt         △
getrouwd        tr.
overleden       †
begraven        ▭
zoon van        zn. van
dochter van     dr. van
kinderen        Hieruit:

Eerste generatie

I.1 Joannes Thomissen [512]
* ±1645
Tr. met
NN
Hieruit:
Thomas Jans, ±1660, zie II.1

Tweede generatie

II.1 Thomas Jans, zn. van I.1 [256]
* St. Anthonis ±1675
Otr. / tr. NG Beers 23-04 / 07-05-1702 met
Mariken (Maria) Hendricks [257]
Hieruit:
Jan (Joannes) Thomassen, 1703, zie III.1
```

### Wat wordt gegenereerd

Het script maakt een GEDCOM bestand met:
- Alle personen met hun geboorte, doop, huwelijk, overlijden en begrafenis data
- Familierelaties (ouder-kind, huwelijkspartners)
- Notities met extra informatie en bronnen
- Referentienummers voor kruisverwijzingen

---

## Kwartierstaat Converter

Dit script converteert een kwartierstaat (voorouderlijst) van Excel formaat naar GEDCOM formaat, zodat deze geïmporteerd kan worden in genealogieprogramma's.

## Wat is een kwartierstaat?

Een kwartierstaat (ook wel Ahnentafel genoemd) is een genummerde lijst van voorouders waarbij:
- Persoon 1 = de hoofdpersoon (proband)
- Persoon 2 = vader van persoon 1
- Persoon 3 = moeder van persoon 1
- Persoon 4 = vader van persoon 2 (vadersouder)
- etc.

**Regel:** Voor elke persoon met nummer *n* geldt:
- Vader heeft nummer *2n*
- Moeder heeft nummer *2n + 1*

## Wat is GEDCOM?

GEDCOM (GEnealogical Data COMmunication) is het standaard uitwisselingsformaat voor genealogische gegevens. Het wordt ondersteund door vrijwel alle genealogieprogramma's.

## Installatie

### 1. Maak een virtual environment aan
```bash
cd ~/Lab/_python/gedcom
python3 -m venv venv
source venv/bin/activate
```

### 2. Installeer benodigde packages
```bash
pip install pandas openpyxl
```

## Gebruik

### Excel bestand formaat

Het Excel bestand moet de volgende kolommen bevatten (zonder header rij):

| Kolom 0 | Kolom 1 | Kolom 2 | Kolom 3 | Kolom 4 | Kolom 5 |
|---------|---------|---------|---------|---------|---------|
| Generatie nr | Kwartiernr | Naam | Geboorte | Overlijden | Huwelijk |
| 1.0 | 1.0 | Theo Henri Paul Maria Thomassen | Rotterdam 1950 | | Rotterdam 1989 |
| 2.0 | 2.0 | Theo Albert Maria Thomassen | Rotterdam 1920 | Den Haag 1994 | Rotterdam 1948 |
| | 3.0 | Antoinetta Maria Theresia de Jonge | Oirschot 1926 | Den Haag 2013 | |

**Opmerkingen:**
- **Kolom 0** (Generatie): Optioneel, alleen voor directe mannelijke lijn
- **Kolom 1** (Kwartiernummer): Verplicht, uniek nummer volgens Ahnentafel systeem
- **Kolom 2** (Naam): Volledige naam van de persoon
- **Kolom 3** (Geboorte): Plaats en jaar, bijv. "Rotterdam 1950" of "Geb.Oldenzaal 1888"
- **Kolom 4** (Overlijden): Plaats en jaar van overlijden
- **Kolom 5** (Huwelijk): Plaats en jaar van huwelijk (wordt gekoppeld aan de vader, dus even kwartiernummer)

### Script uitvoeren

```bash
# Activeer virtual environment
source venv/bin/activate

# Voer het script uit
python3 import.py
```

Het script genereert automatisch het bestand `kwartierstaat.ged`.

### Output

```
Kwartierstaat naar GEDCOM Converter
==================================================

Lezen van kwartierstaat TT excel.xlsx...
Gevonden: 6746 personen

Maken van familierelaties...

Genereren van kwartierstaat.ged...

✓ Klaar! GEDCOM bestand gegenereerd: kwartierstaat.ged
  - 6686 personen
  - 2633 families

Hoofdpersoon (1):
  Naam: Theo Henri Paul Maria Thomassen
  Geboren: 1950 in Rotterdam
  Overleden: ? in ?
```

## Gebruik van het GEDCOM bestand

Het gegenereerde `kwartierstaat.ged` bestand kan geïmporteerd worden in:

### Populaire genealogieprogramma's:
- **Gramps** (gratis, open source)
  - Menu: Familie → Import → GEDCOM

- **Family Tree Maker**
  - File → Import → GEDCOM

- **Ancestry.com**
  - Trees → Upload GEDCOM

- **MyHeritage**
  - Family Tree → Import GEDCOM

- **Legacy Family Tree**
  - File → Import → GEDCOM

## Functionaliteit

### Wat het script doet:
✅ Leest Excel bestand met kwartierstaat
✅ Parseert naam, geboorte-, overlijdens- en huwelijksinformatie
✅ Bepaalt automatisch geslacht op basis van kwartiernummer (even=man, oneven=vrouw)
✅ Creëert familie-relaties (ouders, kinderen, huwelijken)
✅ Genereert geldig GEDCOM 5.5.1 bestand
✅ UTF-8 encoding voor Nederlandse karakters

### Automatische verwerking:
- **Geslachtsbepaling**: Even nummers (2, 4, 6...) = man, oneven (3, 5, 7...) = vrouw
- **Datum parsing**: Haalt jaar (4 cijfers) uit tekst
- **Plaats parsing**: Haalt plaats uit tekst, verwijdert "Geb." prefix
- **Familie relaties**: Koppelt automatisch ouders (2n, 2n+1) aan kind (n)
- **Huwelijk**: Huwelijksinformatie van vader wordt gebruikt voor het echtpaar

## Beperkingen en opmerkingen

⚠️ **Belangrijk:**
- Het script gaat ervan uit dat de huwelijksinformatie bij de **vader** (even kwartiernummer) staat
- Geslacht wordt automatisch bepaald, controleer dit in je genealogieprogramma
- Voor persoon 1 wordt standaard "M" (man) aangenomen
- Alleen jaar wordt geëxtraheerd, geen exacte datum (dag/maand)
- Het script verwerkt alleen directe voorouders (Ahnentafel), geen broers/zussen of andere familieleden

## Structuur GEDCOM bestand

Het gegenereerde GEDCOM bestand bevat:

```gedcom
0 HEAD
1 SOUR Kwartierstaat Converter
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8

0 @I1@ INDI
1 NAME Theo Henri Paul Maria Thomassen
1 SEX M
1 BIRT
2 DATE 1950
2 PLAC Rotterdam
1 FAMC @F1@

0 @F1@ FAM
1 HUSB @I2@
1 WIFE @I3@
1 CHIL @I1@
1 MARR
2 DATE 1948
2 PLAC Rotterdam

0 TRLR
```

## Aanpassingen

### Excel bestandsnaam wijzigen
Wijzig regel 174 in `import.py`:
```python
excel_file = 'jouw_bestand.xlsx'
```

### Output bestandsnaam wijzigen
Wijzig regel 207 in `import.py`:
```python
output_file = 'mijn_stamboom.ged'
```

### Geslacht van hoofdpersoon aanpassen
Wijzig regel 44 in `import.py`:
```python
return 'F'  # Voor vrouw
```

## Technische details

### Python versie
- Python 3.6 of hoger

### Dependencies
- **pandas**: Excel bestanden inlezen
- **openpyxl**: Excel backend voor pandas
- **re**: Reguliere expressies voor parsing

### GEDCOM versie
- GEDCOM 5.5.1 (LINEAGE-LINKED)
- Encoding: UTF-8
- Taal: Dutch

## Troubleshooting

### "ModuleNotFoundError: No module named 'pandas'"
```bash
source venv/bin/activate
pip install pandas openpyxl
```

### "FileNotFoundError: kwartierstaat TT excel.xlsx"
Zorg dat je in de juiste directory bent:
```bash
cd ~/Lab/_python/gedcom
```

### Lege GEDCOM bestand
Controleer of je Excel bestand de juiste structuur heeft (zie boven).

### Incorrecte datum formaten
Het script verwacht formaat "Plaats jaar" (bijv. "Rotterdam 1950"). Andere formaten worden mogelijk niet correct geparsed.

## Licentie

Vrij te gebruiken voor persoonlijk en commercieel gebruik.

## Contact

Voor vragen of verbeteringen, open een issue op GitHub of neem contact op.

---

**Veel succes met je genealogisch onderzoek! 🌳**
