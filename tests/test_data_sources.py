import pandas as pd

from fundflow.data_sources import frame_is_observed, unavailable_flows


def test_unconfigured_flow_source_is_empty_and_explicitly_unavailable():
    frame, status = unavailable_flows()
    assert frame.empty
    assert status.status == "unavailable"
    assert "not configured" in status.message.lower()
    assert "gross_redemption_cr" in frame.columns


def test_empty_frame_is_not_observed():
    assert not frame_is_observed(pd.DataFrame())


def test_real_rows_are_detected_as_observed():
    assert frame_is_observed(pd.DataFrame([{"value": 1}]))
