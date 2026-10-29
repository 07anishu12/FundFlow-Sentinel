"""Synthetic registry records only; no network access."""
import hashlib
from pathlib import Path
import pytest
import yaml
from fundflow.registry import (REGISTRY_COLUMNS, append_record, file_sha256,
                               read_registry, validate_record, write_registry)

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def record():
    # Genuine provider URL identifies location only; values are synthetic test data.
    return dict(source_name="SYNTHETIC", url="https://www.amfiindia.com/",
        data_type="test", frequency="test", retrieved_at="2020-01-01T00:00:00Z",
        terms_url="https://www.amfiindia.com/terms-of-use", permitted_use="Synthetic test only",
        attribution="SYNTHETIC", redistribution_status="restricted", source_confidence="official",
        sha256=hashlib.sha256(b"synthetic").hexdigest(), last_outcome="success",
        status="restricted", checked_on="2020-01-01")

def test_hash_is_bytes_based_and_changes(tmp_path):
    one, two = tmp_path / "one", tmp_path / "two"
    one.write_bytes(b"synthetic\x00\xff")
    two.write_bytes(one.read_bytes())
    assert file_sha256(one) == file_sha256(two) == hashlib.sha256(one.read_bytes()).hexdigest()
    two.write_bytes(b"different")
    assert file_sha256(one) != file_sha256(two)

def test_round_trip_and_append(tmp_path, record):
    path = tmp_path / "ledger.csv"
    assert read_registry(path) == []
    write_registry(path, [record])
    assert read_registry(path) == [record]
    append_record(path, {**record, "last_outcome":"failed", "sha256":""})
    assert len(read_registry(path)) == 2

def test_invalid_write_preserves_previous(tmp_path, record):
    path = tmp_path / "ledger.csv"
    write_registry(path, [record])
    original = path.read_bytes()
    with pytest.raises(ValueError):
        write_registry(path, [record, {**record, "sha256":"bad"}])
    assert path.read_bytes() == original

def test_failed_replace_preserves_previous(tmp_path, record, monkeypatch):
    path = tmp_path / "ledger.csv"
    write_registry(path, [record])
    original = path.read_bytes()
    def fail(*args): raise OSError("Synthetic failure")
    monkeypatch.setattr("fundflow.registry.os.replace", fail)
    with pytest.raises(OSError): write_registry(path, [])
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]

@pytest.mark.parametrize("field,value", [
    ("url", "https://www.amfiindia.com/?token=synthetic"),
    ("url", "https://synthetic:synthetic@www.amfiindia.com/"),
    ("url", "https://www.amfiindia.com/token/synthetic"),
    ("attribution", "person@example.test"),
    ("permitted_use", "password=synthetic"),
    ("source_name", "=SYNTHETIC()"),
    ("retrieved_at", "2020-01-01T00:00:00+05:30"),
    ("sha256", ""), ("status", "open"), ("last_outcome", "raw exception text"),
])
def test_invalid_record(record, field, value):
    with pytest.raises(ValueError): validate_record({**record, field:value})

def test_bad_header_fails(tmp_path):
    path = tmp_path / "ledger.csv"
    path.write_text("secret,value\n")
    with pytest.raises(ValueError): read_registry(path)

def test_inventory_complete_and_not_permission_by_default():
    cfg = yaml.safe_load((ROOT / "config/sources.yaml").read_text())
    expected = {"amfi_flows", "amfi_nav", "mfapi", "nse_vix", "nifty_indices", "yfinance", "rbi_dbie", "rbi_rss", "fed_rss", "gdelt", "prosus_finbert", "finbert_tone", "vader"}
    assert {s["id"] for s in cfg["sources"]} == expected
    for source in cfg["sources"]:
        validate_record({key:source[key] for key in REGISTRY_COLUMNS})
        assert not source["enabled"]
        assert source["last_outcome"] == "not_attempted"
        assert source["retrieved_at"] == source["sha256"] == ""
        if source["status"] == "unverified":
            assert source["redistribution_status"] == "unknown"
