from unittest.mock import patch

import pytest
from rdflib import URIRef

from xbrlld.taxonomy import convert_taxonomy, normalise_uri


def test_normalise_uri_removes_year_and_trailing_slash():
    uri = URIRef("http://fasb.org/us-gaap/2024#NetIncomeLoss")
    expected = URIRef("http://fasb.org/us-gaap#NetIncomeLoss")
    assert normalise_uri(uri) == expected


def test_normalise_uri_removes_date_in_path():
    uri = URIRef("http://example.com/2024-01-01/foo#Bar")
    expected = URIRef("http://example.com/foo#Bar")
    assert normalise_uri(uri) == expected


def test_normalise_uri_removes_trailing_slash_before_fragment():
    uri = URIRef("http://example.com/foo/#Bar")
    expected = URIRef("http://example.com/foo#Bar")
    assert normalise_uri(uri) == expected


def test_normalise_uri_removes_year_from_fragment():
    uri = URIRef("http://example.com/foo#Bar2024")
    expected = URIRef("http://example.com/foo#Bar")
    assert normalise_uri(uri) == expected


def test_normalise_uri_no_change_needed():
    uri = URIRef("http://example.com/foo#Bar")
    expected = URIRef("http://example.com/foo#Bar")
    assert normalise_uri(uri) == expected


SCHEMAS = {
    "FRS102": "https://xbrl.frc.org.uk/FRS-102/2025-01-01/FRS-102-2025-01-01.xsd",
    "ESEF": "https://www.esma.europa.eu/taxonomy/2024-03-27/esef_all.xsd",
    "USGAAP": "https://xbrl.fasb.org/us-gaap/2025/elts/us-gaap-all-2025.xsd",
}


@pytest.mark.parametrize("name,url", SCHEMAS.items())
def test_convert_taxonomy_schema(name, url):
    try:
        ds = convert_taxonomy(url)
        assert ds is not None
    except Exception as e:
        pytest.fail(f"convert_taxonomy failed for {name}: {e}")


def test_convert_taxonomy_function():
    with patch("xbrlld.taxonomy.Cntlr") as mock_cntlr:
        mock_controller = mock_cntlr.return_value
        mock_controller.modelManager.load.return_value = type(
            "MockXbrl", (), {"modelDocument": type("MockDoc", (), {"type": 0})}
        )()
        with pytest.raises(
            ValueError,
            match="Document at fake-taxonomy.xsd is not a valid XBRL taxonomy document",
        ):
            convert_taxonomy("fake-taxonomy.xsd")
