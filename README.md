# xbrlld – XBRL to RDF

**xbrlld** is a Python library and command-line tool for converting **XBRL taxonomies** and **instance documents** into **RDF** (Resource Description Framework).

It is designed to make XBRL data interoperable with Linked Data technologies.

---

## Installation 📦

```bash
pip install xbrlld
````

---

## Usage 🚀

### Python API

```python
from xbrlld.taxonomy import convert_taxonomy, write_taxonomy_to_rdf
from xbrlld.instance import convert_instance, write_instance_to_rdf

# Convert a taxonomy and return an RDF Dataset
dataset = convert_taxonomy("https://xbrl.frc.org.uk/FRS-102/2025-01-01/FRS-102-2025-01-01.xsd")

# Write taxonomy RDF to file (default: Turtle format)
write_taxonomy_to_rdf(
    "https://xbrl.frc.org.uk/FRS-102/2025-01-01/FRS-102-2025-01-01.xsd",
    "FRS-102-2025-01-01.ttl"
)

# Convert an instance document and return an RDF Dataset
dataset = convert_instance("https://www.sec.gov/Archives/edgar/data/1326801/000162828025036791/meta-20250630.htm")

# Write instance RDF to file (default: Turtle format)
write_instance_to_rdf(
    "https://www.sec.gov/Archives/edgar/data/320193/000032019325000073/aapl-20250628.htm",
    "aapl-20250628.ttl",
)
```

### Command line

```bash
# Convert a taxonomy
xbrlld convert taxonomy https://example.com/taxonomy.xsd -o taxonomy.ttl

# Convert an instance document
xbrlld convert instance https://example.com/report.html -o facts.ttl
```

👉 If conversion fails, error messages are printed and the process exits with code `1`.

---

## Output 📄

The converter produces RDF in **Turtle (TTL)** format by default, with other serialisations (such as TriG) available through the API.

In the generated RDF you will find:

- **From taxonomies**:
  - Concepts, dimensions, and relationships between them expressed as RDF classes and properties
  - Linkbases (e.g. presentation, calculation, definition) translated into RDF
  - Labels (across all available languages) and references

- **From instances**:  
  - Each reported fact represented as an RDF resource
  - Links from facts to their corresponding taxonomy concepts
  - Context information (entity, reporting period, units) captured as RDF properties
  - Values stored in a consistent, machine-readable format


### Example from an instance ([Apple Inc.](https://www.sec.gov/Archives/edgar/data/320193/000032019325000073/aapl-20250628.htm))

```ttl
@prefix iso4217: <http://www.xbrl.org/2003/iso4217#> .
@prefix xbrll: <https://w3id.org/vocab/xbrll#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

[] a xbrll:Fact ;
    xbrll:concept <http://fasb.org/us-gaap/2024#NetIncomeLoss> ;
    xbrll:decimals -6 ;
    xbrll:hasEntity <http://www.sec.gov/CIK0000320193> ;
    xbrll:period [
        xbrll:endPeriod "2024-06-30"^^xsd:date ;
        xbrll:startPeriod "2024-03-31"^^xsd:date
    ] ;
    xbrll:unitRef iso4217:USD ;
    xbrll:value 21448000000.0 .
```

### Example from a taxonomy ([US GAAP 2024](https://xbrl.fasb.org/us-gaap/2024/elts/us-gaap-all-2024.xsd))

```ttl
@prefix ns1: <http://www.xbrl.org/2003/arcrole/> .
@prefix ns2: <http://www.xbrl.org/2003/role/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xbrli: <http://www.xbrl.org/2003/instance#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://fasb.org/us-gaap/2024#BusinessAcquisitionsProFormaNetIncomeLoss> a xbrli:monetaryItemType,
        ns2:link ;
    rdfs:label "Business Acquisition, Pro Forma Net Income (Loss)",
        "Business Acquisition, Pro Forma Net Income (Loss)"@en-US ;
    rdfs:isDefinedBy <http://fasb.org/us-gaap/2024> ;
    xsd:abstract false ;
    xsd:id "us-gaap_BusinessAcquisitionsProFormaNetIncomeLoss" ;
    xsd:nillable true ;
    xsd:substitutionGroup xbrli:item ;
    owl:sameAs <http://fasb.org/us-gaap#BusinessAcquisitionsProFormaNetIncomeLoss> ;
    ns1:concept-label _:N5de19bd23b4e4cf7b46d67f753b315e8,
        _:N7f02a5e2fc0a46c4bab65ad80e738791 ;
    ns1:concept-reference _:N20a938bdba54444dad13a4609668fe80,
        _:N42a547447db348e08e5567bfc1484740 ;
    xbrli:balance "credit" ;
    xbrli:periodType "duration" ;
    ns2:documentation "The pro forma net Income or Loss for the period as if the business combination or combinations had been completed at the beginning of a period.",
        "The pro forma net Income or Loss for the period as if the business combination or combinations had been completed at the beginning of a period."@en-US ;
    ns2:label "Business Acquisition, Pro Forma Net Income (Loss)",
        "Business Acquisition, Pro Forma Net Income (Loss)"@en-US .

_:N5de19bd23b4e4cf7b46d67f753b315e8 a link:label ;
    rdf:value "The pro forma net Income or Loss for the period as if the business combination or combinations had been completed at the beginning of a period."@en-US ;
    xlink:role ns2:documentation .

_:N20a938bdba54444dad13a4609668fe80 a link:reference ;
    rdf:value "805 10 Accounting Standards Codification 50 2 (h)(3) FASB" ;
    xlink:role ns2:disclosureRef .
```

---

## References 📚

* [Adopting Semantic Technologies for Effective Corporate Transparency](https://research-information.bris.ac.uk/en/publications/adopting-semantic-technologies-for-efective-corporate-transparenc)
* The **xbrll vocabulary**: [`https://w3id.org/vocab/xbrll#`](https://w3id.org/vocab/xbrll#)
* [Making XBRL and Linked Data interoperable (Kaempgen, 2012)](https://www.w3.org/2011/gld/wiki/images/c/c3/Kaempgen_QB-XBRL_2012-05-17.pdf)
* [Harvesting RDF Statements from XLinks](https://www.w3.org/TR/2000/NOTE-xlink2rdf-20000929/)

---

## Licence ⚖️

This project is released under the [MIT Licence](LICENCE).

