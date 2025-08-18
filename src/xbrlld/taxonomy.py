import re

from arelle import Cntlr, XbrlConst
from arelle.ModelDocument import Type
from arelle.ModelDtsObject import ModelConcept
from arelle.ModelValue import QName
from rdflib import OWL, RDF, RDFS, XSD, BNode, Dataset, Literal, URIRef

from xbrlld import NAMESPACES


def normalise_uri(uri: URIRef) -> URIRef:
    """
    Strip any date of the form `/YYYY/`, `/YYYY-MM/`, or `/YYYY-MM-DD/` from a
    URI to create a normalised version.
    """
    # Remove year/date from path (handles /YYYY, /YYYY-MM, /YYYY-MM-DD, and /YYYY before fragment)
    normalised_uri = re.sub(r"/(\d{4}(?:-\d{2})?(?:-\d{2})?)", "", str(uri))
    # Remove year from fragment if present (e.g., .../2024#NetIncomeLoss)
    normalised_uri = re.sub(r"(#[A-Za-z]+)(\d{4})$", r"\1", normalised_uri)
    # Remove trailing slash before fragment or end
    normalised_uri = re.sub(r"/(?=#|$)", "", normalised_uri)
    return URIRef(normalised_uri)


def convert_taxonomy(file: str) -> Dataset:
    """
    Convert an XBRL taxonomy document to RDF and return a Dataset.
    """
    controller = Cntlr.Cntlr()
    model_xbrl = controller.modelManager.load(file)

    if not model_xbrl:
        raise ValueError(f"Failed to load XBRL document: {file}")
    if model_xbrl.modelDocument is None or model_xbrl.modelDocument.type not in [
        Type.SCHEMA,
        Type.LINKBASE,
    ]:
        raise ValueError(f"Document at {file} is not a valid XBRL taxonomy document")

    dataset = Dataset()
    for prefix, uri in NAMESPACES.items():
        dataset.namespace_manager.bind(prefix, uri)

    EXCLUDED_NAMESPACES = XbrlConst.ixbrlAll.union(
        (
            XbrlConst.xbrli,
            XbrlConst.link,
            XbrlConst.xlink,
            XbrlConst.xl,
            XbrlConst.xbrldt,
            XbrlConst.xhtml,
        )
    )

    for concept in model_xbrl.qnameConcepts.values():
        if concept.modelDocument.targetNamespace not in EXCLUDED_NAMESPACES:
            concept_uri = URIRef(concept.qname.expandedName)
            dataset.add((concept_uri, OWL.sameAs, normalise_uri(concept_uri)))
            dataset.add(
                (
                    concept_uri,
                    URIRef("http://www.w3.org/2001/XMLSchema#id"),
                    Literal(concept.id),
                )
            )
            dataset.add(
                (
                    concept_uri,
                    RDFS.isDefinedBy,
                    URIRef(concept.qname.namespaceURI),
                )
            )

            if isinstance(concept, ModelConcept):
                if hasattr(concept, "type") and concept.type is not None:
                    dataset.add(
                        (
                            concept_uri,
                            RDF.type,
                            URIRef(concept.type.qname.expandedName),
                        )
                    )
                dataset.add(
                    (
                        concept_uri,
                        URIRef("http://www.w3.org/2001/XMLSchema#abstract"),
                        Literal(concept.abstract, datatype=XSD.boolean),
                    )
                )
                dataset.add(
                    (
                        concept_uri,
                        URIRef("http://www.w3.org/2001/XMLSchema#nillable"),
                        Literal(concept.nillable, datatype=XSD.boolean),
                    )
                )
                if (
                    hasattr(concept, "substitutionGroup")
                    and concept.substitutionGroup is not None
                ):
                    dataset.add(
                        (
                            concept_uri,
                            URIRef(
                                "http://www.w3.org/2001/XMLSchema#substitutionGroup"
                            ),
                            URIRef(concept.substitutionGroup.qname.expandedName),
                        )
                    )
                if concept.periodType:
                    dataset.add(
                        (
                            concept_uri,
                            URIRef("http://www.xbrl.org/2003/instance#periodType"),
                            Literal(concept.periodType),
                        )
                    )
                if concept.balance:
                    dataset.add(
                        (
                            concept_uri,
                            URIRef("http://www.xbrl.org/2003/instance#balance"),
                            Literal(concept.balance),
                        )
                    )

                for label_role in model_xbrl.labelroles:
                    for lang in model_xbrl.langs:
                        label = concept.label(
                            label_role, fallbackToQname=False, lang=lang
                        )
                        if label:
                            dataset.add(
                                (
                                    concept_uri,
                                    URIRef(label_role),
                                    Literal(label, lang=lang),
                                )
                            )
                            if label_role == XbrlConst.standardLabel:
                                dataset.add(
                                    (
                                        concept_uri,
                                        RDFS.label,
                                        Literal(label, lang=lang),
                                    )
                                )

    STANDARD_ARCROLES = [
        "http://www.w3.org/1999/xlink/properties/linkbase",
        "http://www.xbrl.org/2003/arcrole/concept-label",
        "http://www.xbrl.org/2003/arcrole/concept-reference",
        "http://www.xbrl.org/2003/arcrole/fact-footnote",
        "http://www.xbrl.org/2003/arcrole/parent-child",
        "http://www.xbrl.org/2003/arcrole/summation-item",
        "http://www.xbrl.org/2003/arcrole/general-special",
        "http://www.xbrl.org/2003/arcrole/essence-alias",
        "http://www.xbrl.org/2003/arcrole/similar-tuples",
        "http://www.xbrl.org/2003/arcrole/requires-element",
    ]

    for arcrole in set([*STANDARD_ARCROLES, *model_xbrl.arcroleTypes.keys()]):
        relationship_set = model_xbrl.relationshipSet(arcrole)

        for linkrole in relationship_set.linkRoleUris:
            role_types = model_xbrl.roleTypes.get(linkrole, [])
            dataset.add((URIRef(linkrole), RDF.type, RDFS.Class))
            for role_type in role_types:
                dataset.add(
                    (URIRef(linkrole), RDF.type, URIRef(role_type.qname.expandedName))
                )
                dataset.add(
                    (
                        URIRef(linkrole),
                        URIRef("http://www.xbrl.org/2003/linkbase#definition"),
                        Literal(role_type.definition),
                    )
                )
                dataset.add(
                    (
                        URIRef(linkrole),
                        URIRef("http://www.w3.org/2001/XMLSchema#id"),
                        Literal(role_type.id),
                    )
                )
                for used_on in role_type.usedOns:
                    if isinstance(used_on, QName):
                        dataset.add(
                            (
                                URIRef(linkrole),
                                URIRef("http://www.xbrl.org/2003/linkbase#usedOn"),
                                URIRef(used_on.expandedName),
                            )
                        )

            rels = model_xbrl.relationshipSet(arcrole, linkrole)
            if rels:
                for rel in rels.modelRelationships:

                    # Labels and references usually have structured values in
                    # the taxonomy, so we qualify their relationships.
                    if arcrole in [
                        "http://www.xbrl.org/2003/arcrole/concept-label",
                        "http://www.xbrl.org/2003/arcrole/concept-reference",
                    ]:
                        qualified_label_or_reference = BNode()
                        dataset.add(
                            (
                                qualified_label_or_reference,
                                RDF.type,
                                URIRef(rel.toModelObject.qname.expandedName),
                            )
                        )
                        dataset.add(
                            (
                                qualified_label_or_reference,
                                URIRef("http://www.w3.org/1999/xlink#role"),
                                URIRef(rel.toModelObject.role),
                            )
                        )
                        dataset.add(
                            (
                                qualified_label_or_reference,
                                RDF.value,
                                Literal(
                                    rel.toModelObject.viewText().strip(),
                                    lang=rel.toModelObject.xmlLang,
                                ),
                            )
                        )

                        dataset.add(
                            (
                                URIRef(rel.fromModelObject.qname.expandedName),
                                URIRef(arcrole),
                                qualified_label_or_reference,
                            )
                        )

                    else:
                        dataset.add(
                            (
                                URIRef(rel.fromModelObject.qname.expandedName),
                                URIRef(arcrole),
                                URIRef(rel.toModelObject.qname.expandedName),
                            )
                        )

                    # Similarly, arcrole relationships have metadata, such as
                    # an order, which we qualify.
                    qualified_arcrole = BNode()

                    dataset.add(
                        (
                            qualified_arcrole,
                            RDF.type,
                            URIRef(rel.linkQname.expandedName),
                        )
                    )
                    dataset.add(
                        (
                            qualified_arcrole,
                            URIRef("http://www.w3.org/1999/xlink#arcrole"),
                            URIRef(arcrole),
                        )
                    )
                    dataset.add(
                        (
                            qualified_arcrole,
                            URIRef("http://www.w3.org/1999/xlink#from"),
                            URIRef(rel.fromModelObject.qname.expandedName),
                        )
                    )

                    if arcrole in [
                        "http://www.xbrl.org/2003/arcrole/concept-label",
                        "http://www.xbrl.org/2003/arcrole/concept-reference",
                    ]:
                        dataset.add(
                            (
                                qualified_arcrole,
                                URIRef("http://www.w3.org/1999/xlink#to"),
                                qualified_label_or_reference,
                            )
                        )
                    else:
                        dataset.add(
                            (
                                qualified_arcrole,
                                URIRef("http://www.w3.org/1999/xlink#to"),
                                URIRef(rel.toModelObject.qname.expandedName),
                            )
                        )

                    dataset.add(
                        (
                            qualified_arcrole,
                            URIRef("http://www.xbrl.org/2003/linkbase#order"),
                            Literal(
                                rel.order,
                                datatype=URIRef(
                                    "http://www.w3.org/2001/XMLSchema#decimal"
                                ),
                            ),
                        )
                    )

                    if hasattr(rel, "preferredLabel") and rel.preferredLabel:
                        dataset.add(
                            (
                                qualified_arcrole,
                                URIRef("http://www.w3.org/1999/xlink#preferredLabel"),
                                URIRef(rel.preferredLabel),
                            )
                        )

                    for concept in (rel.fromModelObject, rel.toModelObject):
                        concept_uri = URIRef(concept.qname.expandedName)
                        dataset.add((concept_uri, RDF.type, URIRef(linkrole)))

    return dataset


def write_taxonomy_to_rdf(file: str, destination: str, format: str = "turtle"):
    """
    Convert an XBRL taxonomy document and write the RDF Dataset to a file.
    """
    dataset = convert_taxonomy(file)
    dataset.serialize(destination, format=format)
