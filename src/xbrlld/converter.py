"""
Module: xbrl_to_rdf.py

This module provides functionality to convert XBRL taxonomies and instance
documents into RDF format. It extracts concepts, labels, relationships, and
facts from XBRL documents and represents them in RDF using SKOS, QB (Data Cube),
and custom XBRL vocabularies.

XBRL (eXtensible Business Reporting Language) is a standard for exchanging
business and financial data. RDF (Resource Description Framework) is a framework
for representing information as a graph of interconnected resources.

The module has two main components:
1. TaxonomyConverter - Converts XBRL taxonomy (schema) to RDF
2. InstanceConverter - Converts XBRL instance documents (facts/data) to RDF

Usage:
    converter = XBRLtoRDFConverter()
    converter.convert_taxonomy(
        "https://example.com/taxonomy.xsd", "taxonomy.trig"
    )
    converter.convert_instance(
        "https://example.com/example-report.html", "facts.trig"
    )
"""

import json
import re
import warnings
from typing import Optional, Union

from arelle import Cntlr, ModelObject, XbrlConst
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateDuplicateFacts import DeduplicationType, getDeduplicatedFacts
from arelle.XbrlConst import (
    qname,
    qnXbrliBooleanItemType,
    qnXbrliDateItemType,
    qnXbrliDurationItemType,
    qnXbrliMonetaryItemType,
)
from rdflib import BNode, Dataset, Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

qnXbrliDecimalItemType = qname(
    "{http://www.xbrl.org/2003/instance}xbrli:decimalItemType"
)
qnXbrliSharesItemType = qname("{http://www.xbrl.org/2003/instance}xbrli:sharesItemType")
qnXbrliPureItemType = qname("{http://www.xbrl.org/2003/instance}xbrli:pureItemType")


class BaseConverter:
    """Base class with common functionality for XBRL converters."""

    def __init__(self) -> None:
        """
        Initialise the base converter with optional persistent storage.
        """
        self.controller = Cntlr.Cntlr()
        self.controller.modelManager.defaultLang = "en"
        self.model_xbrl = None

    def _bind_common_namespaces(self, graph_or_dataset: Union[Graph, Dataset]) -> None:
        """
        Bind commonly used XBRL namespaces to an RDF graph or dataset.

        Args:
            graph_or_dataset: The RDF graph or dataset to bind namespaces to
        """
        self.ARCROLE = Namespace("http://www.xbrl.org/2003/arcrole/")
        self.DIM_ARCROLE = Namespace("http://xbrl.org/int/dim/arcrole/")
        self.LINK = Namespace("http://www.xbrl.org/2003/linkbase#")
        self.ROLE_2003 = Namespace("http://www.xbrl.org/2003/role/")
        self.ROLE_2009 = Namespace("http://www.xbrl.org/2009/role/")
        self.XBRLL = Namespace("https://w3id.org/vocab/xbrll#")
        self.XBRLDT = Namespace("http://xbrl.org/2005/xbrldt#")
        self.XBRLI = Namespace("http://www.xbrl.org/2003/instance#")

        graph_or_dataset.bind("arcrole", self.ARCROLE)
        graph_or_dataset.bind("dimarcrole", self.DIM_ARCROLE)
        graph_or_dataset.bind("link", self.LINK)
        graph_or_dataset.bind("role2003", self.ROLE_2003)
        graph_or_dataset.bind("role2009", self.ROLE_2009)
        graph_or_dataset.bind("xbrll", self.XBRLL)
        graph_or_dataset.bind("xbrldt", self.XBRLDT)
        graph_or_dataset.bind("xbrli", self.XBRLI)

    def load_xbrl(self, xbrl_url: str) -> ModelXbrl:
        """
        Load an XBRL document into memory using Arelle.

        Args:
            xbrl_url: URL or file path of the XBRL document to load

        Raises:
            ValueError: If the document cannot be loaded successfully
        """
        self.model_xbrl = self.controller.modelManager.load(xbrl_url)
        if not self.model_xbrl:
            raise ValueError(f"Failed to load XBRL document: {xbrl_url}")
        return self.model_xbrl

    def concept_uri(self, concept: ModelObject) -> URIRef:
        """
        Generate a URI for an XBRL concept by combining its namespace and local name.

        Args:
            concept: The XBRL concept to generate a URI for

        Returns:
            URIRef: A URI uniquely identifying the concept
        """
        return URIRef(concept.qname.namespaceURI + "#" + concept.qname.localName)

    def normalise_uri(self, uri: URIRef) -> URIRef:
        """
        Strip any date (YYYY-MM-DD) from a URI to create a normalized version.

        This helps establish equivalence between concepts from different versions
        of a taxonomy that only differ by their date component.

        Args:
            uri: The URI to normalise

        Returns:
            URIRef: The normalised URI with any date components removed
        """
        normalised_uri = re.sub(r"/\d{4}-\d{2}-\d{2}/", "/", str(uri))
        return URIRef(normalised_uri)


class TaxonomyConverter(BaseConverter):
    """
    Converts XBRL taxonomy into RDF format.
    """

    def __init__(self, xbrl_url: Optional[str] = None) -> None:
        """
        Initialize the taxonomy converter.

        Args:
            xbrl_url: Optional URL of the XBRL taxonomy to load immediately
        """

        super().__init__()
        self.dataset = Dataset(store="Oxigraph")

        self._bind_common_namespaces(self.dataset)

        if xbrl_url:
            self.load_xbrl(xbrl_url)
            self.convert()

    def add_xbrl_role(self, linkrole: str) -> None:
        """
        Extract and add XBRL roles as RDF resources to the dataset.

        This method processes an XBRL role and adds it to the RDF dataset with
        the following properties:
        - `rdf:type` as `rdfs:Class` (per XLink to RDF [mapping rules](https://www.w3.org/TR/2000/NOTE-xlink2rdf-20000929))
        - `rdf:type` as `xbrl:Role`
        - `xsd:id` with the role's original identifier
        - `rdfs:isDefinedBy` linking to the role's namespace
        - `link:definition` containing the role's human-readable definition

        Args:
            arcrole (str): The arcrole URI that defines the type of relationship
                (e.g., parent-child, dimension-domain)
            linkrole (str): The linkrole URI that defines the role being
                processed

        The method maps XLink roles to RDF following the standard mapping rules
        defined in the XLink to RDF transformation specification.
        """

        linkrole_object = self.model_xbrl.roleTypes.get(linkrole)[0]
        role_uri = URIRef(linkrole)

        # Harvesting software that uses the facilities of the RDF Schema
        # specification may generate an additional statement whose subject is
        # the value of the xlink:role attribute, whose predicate is "rdf:type"
        # and whose object is "rdfs:Class".
        self.dataset.add((role_uri, RDF.type, RDFS.Class))

        self.dataset.add((role_uri, RDF.type, self.XBRLL.Role))

        # Ignore a warning for id not being in the XSD namespace
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.dataset.add((role_uri, XSD.id, Literal(linkrole_object.id)))

        self.dataset.add(
            (
                role_uri,
                RDFS.isDefinedBy,
                URIRef(linkrole_object.modelDocument.targetNamespace),
            )
        )
        self.dataset.add(
            (
                role_uri,
                self.LINK.definition,
                Literal(linkrole_object.definition, lang="en"),
            )
        )

    def add_xbrl_concepts(self, arcrole: str, linkrole: str) -> None:
        """Extract and add XBRL concepts to the RDF graph."""
        ignored_namespaces = {
            XbrlConst.link,
            XbrlConst.xbrldt,
            XbrlConst.xbrli,
            XbrlConst.xl,
            XbrlConst.xlink,
            XbrlConst.xsd,
            "http://www.xbrl.org/2004/ref",
            "http://www.xbrl.org/2006/ref",
        }

        relationship_set = self.model_xbrl.relationshipSet(arcrole, linkrole)
        concepts = (
            relationship_set.fromModelObjects().keys()
            | relationship_set.toModelObjects().keys()
        )
        role_uri = URIRef(linkrole)

        for concept in concepts:
            if concept.modelDocument.targetNamespace in ignored_namespaces:
                continue

            concept_uri = self.concept_uri(concept)

            # If the locator element provides an xlink:role attribute, one
            # additional statement shall be added to the model. The value of the
            # locator's xlink:href attribute shall be mapped to the subject of
            # the statement. The value of the xlink:role attribute shall be
            # mapped to the object, and the predicate shall be "rdf:type".
            self.dataset.add((concept_uri, RDF.type, role_uri))

            self.dataset.add((concept_uri, OWL.sameAs, self.normalise_uri(concept_uri)))
            self.dataset.add((concept_uri, XSD.id, Literal(concept.id)))
            self.dataset.add(
                (
                    concept_uri,
                    RDFS.isDefinedBy,
                    URIRef(concept.modelDocument.targetNamespace),
                )
            )
            self.dataset.add((concept_uri, RDF.type, self.XBRLL.Concept))
            self.dataset.add((concept_uri, RDF.type, self.concept_uri(concept.type)))

            # Ignore warnings for abstract, nullable and substitutionGroup not
            # being in the XSD namespace.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.dataset.add(
                    (
                        concept_uri,
                        XSD.abstract,
                        Literal(concept.abstract, datatype=XSD.boolean),
                    )
                )
                self.dataset.add(
                    (
                        concept_uri,
                        XSD.nillable,
                        Literal(concept.nillable, datatype=XSD.boolean),
                    )
                )

                # This must explicitly test "is not None"; there's a bug or
                # weird behaviour in arelle which means testing truth-ness
                # doesn't work as intended with substitution groups.
                if concept.substitutionGroup is not None:
                    self.dataset.add(
                        (
                            concept_uri,
                            XSD.substitutionGroup,
                            self.concept_uri(concept.substitutionGroup),
                        )
                    )

            if concept.typedDomainRef:
                self.dataset.add(
                    (
                        concept_uri,
                        self.XBRLI.typedDomainRef,
                        self.concept_uri(concept.typedDomainElement),
                    )
                )
            if concept.periodType:
                self.dataset.add(
                    (concept_uri, self.XBRLI.periodType, Literal(concept.periodType))
                )
            if concept.balance:
                self.dataset.add(
                    (concept_uri, self.XBRLI.balance, Literal(concept.balance))
                )

            self.add_xbrl_labels(concept)

    def add_xbrl_labels(self, concept) -> None:
        """
        Extract and add labels for a given XBRL concept to the RDF graph.

        For each combination of label role and language found in the taxonomy,
        adds the corresponding label as a literal with language tag if one exists.

        Args:
            concept: The XBRL concept to extract labels from
        """
        concept_uri = self.concept_uri(concept)
        for label_role in self.model_xbrl.labelroles:
            for lang in self.model_xbrl.langs:
                label = concept.label(label_role, fallbackToQname=False, lang=lang)
                if label:
                    self.dataset.add(
                        (
                            concept_uri,
                            URIRef(label_role),
                            Literal(label, lang=lang),
                        )
                    )
                    if label_role == XbrlConst.standardLabel:
                        self.dataset.add(
                            (concept_uri, RDFS.label, Literal(label, lang=lang))
                        )

    def add_xbrl_relationships(self, arcrole: str, linkrole: str) -> None:
        """
        Extract and add relationships between XBRL concepts to an RDF dataset.

        This method processes the relationships defined in an XBRL taxonomy and
        converts them to RDF triples. Each relationship is added to a named
        graph identified by the linkrole.

        Args:
            arcrole (str): The arcrole URI that defines the type of relationship
                (e.g., `parent-child`, `dimension-domain`, `hypercube-dimension`)
            linkrole (str): The linkrole URI that groups related concepts
                together in a specific context
        """

        role_uri = URIRef(linkrole)
        relationship_set = self.model_xbrl.relationshipSet(arcrole, linkrole)

        for relationship in relationship_set.modelRelationships:
            from_concept = self.concept_uri(relationship.fromModelObject)
            to_concept = self.concept_uri(relationship.toModelObject)
            self.dataset.add((from_concept, URIRef(arcrole), to_concept, role_uri))

            arc_bnode = BNode()
            # TODO: capture the order metadata attached to arcs, such as the order.

            if arcrole in (XbrlConst.all, XbrlConst.notAll):
                self.dataset.add((from_concept, RDF.type, self.XBRLL.PrimaryItem))
                self.dataset.add((to_concept, RDF.type, self.XBRLL.Hypercube))

            if arcrole == XbrlConst.hypercubeDimension:
                self.dataset.add((to_concept, RDF.type, self.XBRLL.Dimension))

            if arcrole == XbrlConst.dimensionDomain:
                self.dataset.add((to_concept, RDF.type, self.XBRLL.DimensionDomain))

            if arcrole == XbrlConst.dimensionDefault:
                self.dataset.add((to_concept, RDF.type, self.XBRLL.DimensionDefault))

            if arcrole == XbrlConst.domainMember:
                self.dataset.add((to_concept, RDF.type, self.XBRLL.DomainMember))

    def construct_skos(self) -> None:
        """
        Construct SKOS relationships from XBRL parent-child relationships.

        This method transforms XBRL parent-child arcrole relationships into SKOS
        concept relationships.

        The transformation is performed using a SPARQL INSERT on the dataset.
        """

        self.dataset.update(
            """
            PREFIX arcrole: <http://www.xbrl.org/2003/arcrole/>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

            INSERT {
                GRAPH ?g {
                    ?s a skos:Concept ;
                        skos:narrower ?o ;
                        skos:inScheme ?g .

                    ?o a skos:Concept ;
                        skos:broader ?s ;
                        skos:inScheme ?g .
                }
            }
            WHERE {
                GRAPH ?g {
                    ?s arcrole:parent-child ?o
                }
            }
            """
        )

    def construct_qb(self) -> None:
        """
        Construct RDF Data Cube relationships from XBRL dimensional relationships.
        """
        self.dataset.update(
            """
            PREFIX dimarcrole: <http://xbrl.org/int/dim/arcrole/>
            PREFIX qb: <http://purl.org/linked-data/cube#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

            INSERT {
                GRAPH ?g {
                    ?hypercube a qb:DataSet ;
                        qb:structure [ 
                            a qb:DataStructureDefinition ;
                            qb:component [ qb:measure ?measure ] ;
                        ] .
                }

                ?measure a qb:MeasureProperty .
            }
            WHERE {
                GRAPH ?g {
                    ?primaryItem dimarcrole:all ?hypercube ;
                        dimarcrole:domain-member ?measure .
                }
            }
            """
        )
        self.dataset.update(
            """
            PREFIX dimarcrole: <http://xbrl.org/int/dim/arcrole/>
            PREFIX qb: <http://purl.org/linked-data/cube#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

            INSERT {
                GRAPH ?g {
                    ?dsd qb:component [ qb:dimension ?dimension ] .
                }

                ?dimension a qb:DimensionProperty ;
                    qb:codeList ?domain .

                ?domain a skos:ConceptScheme .
            }
            WHERE {
                GRAPH ?g {
                    ?primaryItem dimarcrole:all ?hypercube .

                    ?hypercube qb:structure ?dsd ;
                        dimarcrole:hypercube-dimension ?dimension .
                }
                GRAPH ?g2 {
                    ?dimension dimarcrole:dimension-domain ?domain .
                }
            }
           """
        )
        self.dataset.update(
            """
            PREFIX dimarcrole: <http://xbrl.org/int/dim/arcrole/>
            PREFIX qb: <http://purl.org/linked-data/cube#>
            PREFIX xbrll: <https://w3id.org/vocab/xbrll#>

            INSERT {
                GRAPH ?g {
                    ?dsd qb:component
                        [ qb:dimension qb:measureType ],
                        [ qb:dimension xbrll:concept ], 
                        [ qb:dimension xbrll:hasEntity ], 
                        [ qb:dimension xbrll:period ],
                        [ qb:attribute xbrll:unitRef ] ,
                        [ qb:attribute xbrll:decimals ] .
                }

                qb:measureType a qb:DimensionProperty .
                xbrll:concept a qb:DimensionProperty .
                xbrll:hasEntity a qb:DimensionProperty .
                xbrll:period a qb:DimensionProperty .
                xbrll:unitRef a qb:AttributeProperty .
                xbrll:decimals a qb:AttributeProperty .
            }
            WHERE {
                GRAPH ?g {
                    ?primaryItem dimarcrole:all ?hypercube .

                    ?hypercube qb:structure ?dsd ;
                }
            }
            """
        )

    def create_context(self, output_file: str) -> None:
        """
        Create a JSON-LD context file for the XBRL taxonomy.

        Args:
            output_file: Path where the JSON-LD context should be written
        """
        context = {
            "@vocab": "https://xbrl.org/CR/2021-07-07/xbrl-json#",
        }
        for namespace, uri in self.dataset.namespaces():
            context[namespace] = str(uri)

        context = context | {
            "facts": {"@container": "@index"},
            "dimensions": "@nest",
            "unit": {"@type": "@id", "@nest": "dimensions"},
            "concept": {
                "@id": "http://purl.org/linked-data/cube#measureType",
                "@type": "@id",
                "@nest": "dimensions",
            },
            "entity": {"@type": "@id", "@nest": "dimensions"},
            "period": {
                "@type": "http://www.w3.org/2006/time#Interval",
                "@nest": "dimensions",
            },
            "value": {"@id": "http://purl.org/linked-data/cube#obsValue"},
        }

        query = """
            SELECT ?dimension WHERE {
                ?dimension <http://www.w3.org/2001/XMLSchema#substitutionGroup> <http://xbrl.org/2005/xbrldt#dimensionItem> .
            }
        """

        results = self.dataset.query(query)
        context = context | {str(row.dimension): {"@type": "@id"} for row in results}

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(context, f, indent=2)

    def convert(self) -> Dataset:
        """
        Run the full conversion process from XBRL to RDF.

        Warns if notAll arcroles are encountered as these have complex semantics.
        """
        for arcrole in (*self.model_xbrl.arcroleTypes.keys(), XbrlConst.parentChild):
            relationship_set = self.model_xbrl.relationshipSet(arcrole)

            # notAll arcoles are a bit weird but the UK taxonomies don't (currently) use them.
            # If they were introduced we would need to evaluate how to represent them as RDF.
            if arcrole == XbrlConst.notAll and relationship_set.modelRelationships:
                warnings.warn(
                    "This taxonomy uses a notAll arcrole. notAll arcroles have complex semantics "
                    "which have not been fully considered in the conversion to RDF.",
                    UserWarning,
                )

            for linkrole in relationship_set.linkRoleUris:
                self.add_xbrl_role(linkrole)
                self.add_xbrl_concepts(arcrole, linkrole)
                self.add_xbrl_relationships(arcrole, linkrole)

        self.construct_skos()
        self.construct_qb()
        return self.dataset

    def serialise(self, output_file: str) -> None:
        """
        Save the RDF graph to a file.

        Args:
            output_file: Path where the RDF serialisation should be written.
        """
        self.dataset.serialize(format="trig", destination=output_file)


class InstanceConverter(BaseConverter):
    """
    Converts XBRL instance documents (facts) into RDF format.
    """

    def __init__(self, xbrl_url: Optional[str] = None) -> None:
        """
        Initialize the instance converter.

        Args:
            xbrl_url: Optional URL of the XBRL instance document to load immediately
        """

        super().__init__()
        self.dataset = Dataset(store="Oxigraph")

        self._bind_common_namespaces(self.dataset)

        if xbrl_url:
            self.load_xbrl(xbrl_url)
            self.convert()

    def process_fact(self, fact: ModelFact, report_bnode: BNode) -> None:
        """
        Process and convert a single XBRL fact into RDF triples.

        Args:
            fact (ModelFact): The XBRL fact to convert to RDF

        Companies House identifiers are given special treatment and converted
        to data.companieshouse.gov.uk URIs.
        """

        fact_bnode = BNode()
        self.dataset.add((fact_bnode, RDF.type, self.XBRLL.Fact))
        self.dataset.add((report_bnode, self.XBRLL.hasFact, fact_bnode))
        self.dataset.add(
            (fact_bnode, self.XBRLL.concept, URIRef(fact.concept.qname.expandedName))
        )

        if not fact.isNil:
            type_map = {
                qnXbrliBooleanItemType: (lambda v: v == "true", XSD.boolean),
                qnXbrliMonetaryItemType: (float, XSD.decimal),
                qnXbrliDateItemType: (str, XSD.date),
                qnXbrliDurationItemType: (str, XSD.duration),
                qnXbrliDecimalItemType: (float, XSD.decimal),
                qnXbrliSharesItemType: (float, XSD.decimal),
                qnXbrliPureItemType: (float, XSD.decimal),
            }
            value, datatype = fact.value, None

            for item_type, (converter, rdf_type) in type_map.items():
                if fact.concept.instanceOfType(item_type):
                    value, datatype = converter(fact.value), rdf_type
                    break

            if value is not None:
                self.dataset.add(
                    (fact_bnode, self.XBRLL.value, Literal(value, datatype=datatype))
                )

        if fact.decimals:
            if fact.decimals == "INF":
                self.dataset.add(
                    (
                        fact_bnode,
                        self.XBRLL.decimals,
                        Literal(fact.decimals, datatype=XSD.string),
                    )
                )
            else:
                self.dataset.add(
                    (
                        fact_bnode,
                        self.XBRLL.decimals,
                        Literal(fact.decimals, datatype=XSD.integer),
                    )
                )

        if fact.context is not None:
            for dim_qname, dim in fact.context.qnameDims.items():
                predicate = URIRef(dim_qname.expandedName)
                if dim.isExplicit:
                    obj = URIRef(dim.memberQname.expandedName)
                else:
                    obj = Literal(dim.typedMember.stringValue)
                self.dataset.add((fact_bnode, predicate, obj))

            if fact.context.entityIdentifier:
                if (
                    fact.context.entityIdentifier[0]
                    == "http://www.companieshouse.gov.uk/"
                ):
                    prefix = "http://data.companieshouse.gov.uk/doc/company/"
                else:
                    prefix = fact.context.entityIdentifier[0]
                self.dataset.add(
                    (
                        fact_bnode,
                        self.XBRLL.hasEntity,
                        URIRef(prefix + fact.context.entityIdentifier[1]),
                    )
                )

            if fact.context.isStartEndPeriod or fact.context.isInstantPeriod:
                if fact.context.isStartEndPeriod:
                    start, end = fact.context.startDatetime, fact.context.endDatetime
                    period_bnode = BNode()
                    self.dataset.add((fact_bnode, self.XBRLL.period, period_bnode))
                    self.dataset.add(
                        (
                            period_bnode,
                            self.XBRLL.startPeriod,
                            Literal(start, datatype=XSD.date),
                        )
                    )
                    self.dataset.add(
                        (
                            period_bnode,
                            self.XBRLL.endPeriod,
                            Literal(end, datatype=XSD.date),
                        )
                    )
                else:
                    start = fact.context.instantDatetime
                    self.dataset.add(
                        (
                            fact_bnode,
                            self.XBRLL.period,
                            Literal(start, datatype=XSD.date),
                        )
                    )

            if fact.unit is not None:
                numerators, denominators = fact.unit.measures
                if denominators:
                    unit_bnode = BNode()
                    self.dataset.add((fact_bnode, self.XBRLL.unitRef, unit_bnode))
                    for measure in numerators:
                        self.dataset.add(
                            (
                                unit_bnode,
                                self.XBRLL.numerator,
                                URIRef(measure.expandedName),
                            )
                        )
                    for measure in denominators:
                        self.dataset.add(
                            (
                                unit_bnode,
                                self.XBRLL.denominator,
                                URIRef(measure.expandedName),
                            )
                        )
                else:
                    for measure in numerators:
                        self.dataset.add(
                            (
                                fact_bnode,
                                self.XBRLL.unitRef,
                                URIRef(measure.expandedName),
                            )
                        )

    def construct_qb(self) -> None:
        """
        Construct RDF Data Cube relationships from XBRL instance facts.
        """
        self.dataset.update(
            """
            PREFIX qb: <http://purl.org/linked-data/cube#>

            INSERT {
                ?fact a qb:Observation ;
                    qb:measureType ?concept ;
                    ?concept ?value .
            }
            WHERE {
                ?fact a xbrll:Fact ;
                    xbrll:concept ?concept ;
                    xbrll:value ?value .
            }
            """
        )

    def convert(self, with_taxonomy: bool = True) -> Dataset:
        """Convert an XBRL instance document to RDF.

        Args:
            with_taxonomy (bool): If True, includes all referenced taxonomy definitions
                        in the output dataset. Defaults to True.

        Returns:
            Dataset: RDFlib Dataset containing the converted instance document
                    and optionally taxonomy data in named graphs.
        """

        if getDeduplicatedFacts(self.model_xbrl, DeduplicationType.COMPLETE):
            report_bnode = BNode()
            self.dataset.add((report_bnode, RDF.type, self.XBRLL.Report))

            for fact in getDeduplicatedFacts(
                self.model_xbrl, DeduplicationType.COMPLETE
            ):
                self.process_fact(fact, report_bnode)

            self.construct_qb()

            if with_taxonomy:
                for (
                    referenced_doc
                ) in self.model_xbrl.modelDocument.referencesDocument.keys():
                    if referenced_doc.type == 2:  # 2 = SCHEMA
                        taxonomy_converter = TaxonomyConverter()
                        taxonomy_converter.load_xbrl(referenced_doc.uri)
                        taxonomy_dataset = taxonomy_converter.convert()
                        for quad in taxonomy_dataset:
                            self.dataset.add(quad)

        else:
            raise ValueError(f"No facts found within XBRL document.")

        return self.dataset

    def serialise(self, output_file: str) -> None:
        """
        Save the RDF graph to a file.

        Args:
            output_file (str): Path where the RDF serialisation should be written.
        """
        self.dataset.serialize(format="trig", destination=output_file)


class XBRLtoRDFConverter:
    """
    Unified interface for converting both XBRL taxonomies and instance documents to RDF.
    """

    def __init__(self) -> None:
        """Initialise the converter."""
        self.taxonomy_converter = TaxonomyConverter()
        self.instance_converter = InstanceConverter()

    def convert_taxonomy(self, xbrl_url: str, output_file: str) -> None:
        """
        Convert an XBRL taxonomy to RDF.

        Args:
            xbrl_url (str): URL of the XBRL taxonomy
            output_file (str): File path to save the RDF output
        """
        self.taxonomy_converter.load_xbrl(xbrl_url)
        self.taxonomy_converter.convert()
        self.taxonomy_converter.serialise(output_file)

    def convert_instance(
        self, xbrl_url: str, output_file: str, with_taxonomy: Optional[bool] = False
    ) -> None:
        """
        Convert an XBRL instance document to RDF.

        Args:
            xbrl_url (str): URL of the XBRL instance document
            output_file (str): File path to save the RDF output
        """
        self.instance_converter.load_xbrl(xbrl_url)
        self.instance_converter.convert(with_taxonomy=with_taxonomy)
        self.instance_converter.serialise(output_file)
