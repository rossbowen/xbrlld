# xbrlld - XBRL to RDF

A Python library for converting XBRL taxonomies and instance documents to RDF (Resource Description Framework).

## Installation

```bash
pip install xbrlld
```

## Usage

```python
from xbrlld.converter import XBRLtoRDFConverter

converter = XBRLtoRDFConverter()

# Convert taxonomy
converter.convert_taxonomy(
    "https://example.com/taxonomy.xsd",
    "taxonomy.trig"
)

# Convert instance document
converter.convert_instance(
    "https://example.com/report.html",
    "facts.trig",
    with_taxonomy=True
)
```

Or from the command line:

```bash
xbrlld convert taxonomy https://example.com/taxonomy.xsd -o taxonomy.trig
xbrlld convert instance https://example.com/report.html -o facts.trig --with-taxonomy
```

## Output format

The converter produces RDF in TriG format, which supports named graphs. The output includes:

- SKOS concepts and relationships for taxonomy elements
- RDF Data Cube observations for facts
- Dimensional relationships preserved as RDF properties
- Context information (entity, period, units) as RDF properties

Once converted, a typical fact looks like:

```ttl
_:Ne675618720094136a2caa1bdad2f6c86 a qb:Observation,
        xbrll:Fact ;
    qb:measureType <http://xbrl.frc.org.uk/fr/2023-01-01/core#Equity> ;
    <http://xbrl.frc.org.uk/fr/2023-01-01/core#Equity> 40288.0 ;
    xbrll:concept <http://xbrl.frc.org.uk/fr/2023-01-01/core#Equity> ;
    xbrll:decimals 0 ;
    xbrll:hasEntity <http://data.companieshouse.gov.uk/doc/company/03886530> ;
    xbrll:period "2024-04-01"^^xsd:date ;
    xbrll:unitRef <http://www.xbrl.org/2003/iso4217#GBP> ;
    xbrll:value 40288.0 .
```

## License

This project is licensed under the [MIT License](LICENSE).

## References

- [Adopting Semantic Technologies for Efective Corporate Transparency](https://research-information.bris.ac.uk/en/publications/adopting-semantic-technologies-for-efective-corporate-transparenc)
    - The `xbrll` vocabulary: [`https://w3id.org/vocab/xbrll#`](https://w3id.org/vocab/xbrll#)

- [Making XBRL and Linked Data interoperable](https://www.w3.org/2011/gld/wiki/images/c/c3/Kaempgen_QB-XBRL_2012-05-17.pdf)

- [Harvesting RDF Statements from XLinks](https://www.w3.org/TR/2000/NOTE-xlink2rdf-20000929/)
