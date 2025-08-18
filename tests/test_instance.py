from unittest.mock import patch

import pytest

from xbrlld.instance import convert_instance


def test_convert_instance_function():
    with patch("xbrlld.instance.Cntlr") as mock_cntlr:
        mock_controller = mock_cntlr.return_value
        mock_controller.modelManager.load.return_value = type(
            "MockXbrl", (), {"modelDocument": type("MockDoc", (), {"type": 0})}
        )()
        with pytest.raises(
            ValueError,
            match="Document at fake-instance.xml is not a valid XBRL instance document",
        ):
            convert_instance("fake-instance.xml")


INSTANCES = [
    "https://www.sec.gov/Archives/edgar/data/320193/000032019325000073/aapl-20250628.htm"
]


@pytest.mark.parametrize("instance_url", INSTANCES)
def test_convert_instance(instance_url):
    try:
        ds = convert_instance(instance_url)
        assert ds is not None
    except Exception as e:
        pytest.fail(f"convert_instance failed for {instance_url}: {e}")
