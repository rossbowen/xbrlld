from unittest.mock import patch

import pytest
from click.testing import CliRunner

import xbrlld
from xbrlld.cli import cli


def test_cli_taxonomy():
    runner = CliRunner()
    with patch(
        "xbrlld.taxonomy.convert_taxonomy",
        side_effect=ValueError(
            "Document at fake-taxonomy.xsd is not a valid XBRL taxonomy document"
        ),
    ) as mock_convert:
        result = runner.invoke(
            cli, ["convert", "taxonomy", "fake-taxonomy.xsd", "--output", "out.ttl"]
        )
    assert result.exit_code != 0
    assert (
        "Document at fake-taxonomy.xsd is not a valid XBRL taxonomy document"
        in result.output
    )


def test_cli_instance():
    runner = CliRunner()
    with patch(
        "xbrlld.instance.convert_instance",
        side_effect=ValueError(
            "Document at fake-taxonomy.xml is not a valid XBRL instance document"
        ),
    ) as mock_convert:
        result = runner.invoke(
            cli, ["convert", "instance", "fake-instance.xml", "--output", "out.ttl"]
        )
    assert result.exit_code != 0
    assert (
        "Document at fake-taxonomy.xml is not a valid XBRL instance document"
        in result.output
    )
