# %%
from datetime import datetime

from arelle import Cntlr
from arelle.ModelDocument import Type
from arelle.ValidateDuplicateFacts import DeduplicationType, getDeduplicatedFacts
from arelle.XbrlConst import (
    qname,
    qnXbrliBooleanItemType,
    qnXbrliDateItemType,
    qnXbrliDurationItemType,
    qnXbrliMonetaryItemType,
)
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from xbrlld import NAMESPACES
from xbrlld.taxonomy import convert_taxonomy

qnXbrliDecimalItemType = qname(
    "{http://www.xbrl.org/2003/instance}xbrli:decimalItemType"
)
qnXbrliSharesItemType = qname("{http://www.xbrl.org/2003/instance}xbrli:sharesItemType")
qnXbrliPureItemType = qname("{http://www.xbrl.org/2003/instance}xbrli:pureItemType")


def convert_instance(file: str, with_taxonomy: bool = False) -> Graph:
    """
    Convert an XBRL instance document to RDF and return a Dataset.

    :param file: Path to the XBRL instance document.
    :param with_taxonomy: If True, include the taxonomy in the conversion.
    :return: A Graph containing the RDF representation of the instance.
    """
    controller = Cntlr.Cntlr()
    model_xbrl = controller.modelManager.load(file)

    if not model_xbrl:
        raise ValueError(f"Failed to load XBRL document: {file}")
    if model_xbrl.modelDocument is None or model_xbrl.modelDocument.type not in [
        Type.INSTANCE,
        Type.INLINEXBRL,
    ]:
        raise ValueError(f"Document at {file} is not a valid XBRL instance document")

    dataset = Graph()
    for prefix, uri in NAMESPACES.items():
        dataset.namespace_manager.bind(prefix, uri)

    dedup_facts = getDeduplicatedFacts(model_xbrl, DeduplicationType.COMPLETE)
    if not dedup_facts:
        raise ValueError("No facts found within XBRL document")

    report = URIRef(model_xbrl.modelDocument.uri)
    dataset.add((report, RDF.type, URIRef("https://w3id.org/vocab/xbrll#Report")))

    for fact in dedup_facts:
        fact_bnode = BNode()
        dataset.add((fact_bnode, RDF.type, URIRef("https://w3id.org/vocab/xbrll#Fact")))
        dataset.add(
            (report, URIRef("https://w3id.org/vocab/xbrll#hasFact"), fact_bnode)
        )
        dataset.add(
            (
                fact_bnode,
                URIRef("https://w3id.org/vocab/xbrll#concept"),
                URIRef(fact.concept.qname.expandedName),
            )
        )

        if not fact.isNil:
            type_map = {
                qnXbrliBooleanItemType: (lambda v: v == "true", XSD.boolean),
                qnXbrliMonetaryItemType: (float, XSD.decimal),
                qnXbrliDateItemType: (
                    lambda v: datetime.fromisoformat(str(v)).strftime("%Y-%m-%d"),
                    XSD.date,
                ),
                qnXbrliDurationItemType: (str, XSD.duration),
                qnXbrliDecimalItemType: (float, XSD.decimal),
                qnXbrliSharesItemType: (float, XSD.decimal),
                qnXbrliPureItemType: (float, XSD.decimal),
            }

            value, datatype = fact.value, None
            if fact.concept is not None:
                for item_type, (converter, rdf_type) in type_map.items():
                    if fact.concept.instanceOfType(item_type):
                        try:
                            value = converter(fact.value)
                        except Exception:
                            value = fact.value
                        datatype = rdf_type
                        break

            if value is not None:
                dataset.add(
                    (
                        fact_bnode,
                        URIRef("https://w3id.org/vocab/xbrll#value"),
                        Literal(value, datatype=datatype),
                    )
                )

        if fact.decimals:
            decimals_value = fact.decimals
            decimals_type = XSD.string if decimals_value == "INF" else XSD.integer
            dataset.add(
                (
                    fact_bnode,
                    URIRef("https://w3id.org/vocab/xbrll#decimals"),
                    Literal(decimals_value, datatype=decimals_type),
                )
            )

        context = fact.context
        if context is not None:
            for qname, dim in context.qnameDims.items():
                predicate = URIRef(qname.expandedName)
                obj = (
                    URIRef(dim.memberQname.expandedName)
                    if dim.isExplicit
                    else Literal(dim.typedMember.stringValue)
                )
                dataset.add((fact_bnode, predicate, obj))

            if context.entityIdentifier:
                scheme, identifier = context.entityIdentifier
                dataset.add(
                    (
                        fact_bnode,
                        URIRef("https://w3id.org/vocab/xbrll#hasEntity"),
                        URIRef(scheme.strip() + identifier.strip()),
                    )
                )

            if context.isStartEndPeriod:
                start = datetime.fromisoformat(str(context.startDatetime)).strftime(
                    "%Y-%m-%d"
                )
                end = datetime.fromisoformat(str(context.endDatetime)).strftime(
                    "%Y-%m-%d"
                )
                period_bnode = BNode()
                dataset.add(
                    (
                        fact_bnode,
                        URIRef("https://w3id.org/vocab/xbrll#period"),
                        period_bnode,
                    )
                )
                dataset.add(
                    (
                        period_bnode,
                        URIRef("https://w3id.org/vocab/xbrll#startPeriod"),
                        Literal(start, datatype=XSD.date),
                    )
                )
                dataset.add(
                    (
                        period_bnode,
                        URIRef("https://w3id.org/vocab/xbrll#endPeriod"),
                        Literal(end, datatype=XSD.date),
                    )
                )
            elif context.isInstantPeriod:
                instant = datetime.fromisoformat(str(context.instantDatetime)).strftime(
                    "%Y-%m-%d"
                )
                dataset.add(
                    (
                        fact_bnode,
                        URIRef("https://w3id.org/vocab/xbrll#period"),
                        Literal(instant, datatype=XSD.date),
                    )
                )

            unit = fact.unit
            if unit is not None:
                numerators, denominators = unit.measures
                if denominators:
                    unit_bnode = BNode()
                    dataset.add(
                        (
                            fact_bnode,
                            URIRef("https://w3id.org/vocab/xbrll#unitRef"),
                            unit_bnode,
                        )
                    )
                    for measure in numerators:
                        dataset.add(
                            (
                                unit_bnode,
                                URIRef("https://w3id.org/vocab/xbrll#numerator"),
                                URIRef(measure.expandedName),
                            )
                        )
                    for measure in denominators:
                        dataset.add(
                            (
                                unit_bnode,
                                URIRef("https://w3id.org/vocab/xbrll#denominator"),
                                URIRef(measure.expandedName),
                            )
                        )
                else:
                    for measure in numerators:
                        dataset.add(
                            (
                                fact_bnode,
                                URIRef("https://w3id.org/vocab/xbrll#unitRef"),
                                URIRef(measure.expandedName),
                            )
                        )

    if with_taxonomy:
        for schema_ref in model_xbrl.modelDocument.referencesDocument.keys():
            taxonomy = convert_taxonomy(schema_ref.uri)
            dataset += taxonomy

    return dataset


def write_instance_to_rdf(file: str, destination: str, format: str = "turtle"):
    """
    Convert an XBRL instance document and write the RDF Dataset to a file.
    """
    dataset = convert_instance(file)
    dataset.serialize(destination, format=format)
