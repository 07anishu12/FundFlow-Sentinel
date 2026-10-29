from pathlib import Path
import pandas as pd
import pytest
import yaml
from fundflow.contracts import COLUMNS, validate_table
ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize("name", COLUMNS)
def test_fixtures(name):
    validate_table(name, pd.read_csv(ROOT / f"data/snapshots/fixtures/{name}.csv", dtype=str))

@pytest.mark.parametrize("name", COLUMNS)
def test_extra_columns_rejected(name):
    df = pd.DataFrame(columns=[*COLUMNS[name], "private_extension"])
    with pytest.raises(ValueError): validate_table(name, df)

def test_missing_availability_and_duplicates():
    df = pd.read_csv(ROOT / "data/snapshots/fixtures/flows_category_month.csv")
    with pytest.raises(ValueError): validate_table("flows_category_month", df.drop(columns="available_from"))
    with pytest.raises(ValueError): validate_table("flows_category_month", pd.concat([df, df]))
    df.loc[0, "available_from"] = "2020-02-10T00:00:00+05:30"
    with pytest.raises(ValueError): validate_table("flows_category_month", df)

@pytest.mark.parametrize("field,value", [("month", "2020-13"), ("gross_inflow_cr", "inf"), ("available_from", "2020-02-10")])
def test_bad_values(field, value):
    df = pd.read_csv(ROOT / "data/snapshots/fixtures/flows_category_month.csv", dtype=str)
    df.loc[0, field] = value
    with pytest.raises(ValueError): validate_table("flows_category_month", df)

def test_configs():
    for path in (ROOT / "config").glob("*.yaml"):
        assert isinstance(yaml.safe_load(path.read_text()), dict)
    weights = yaml.safe_load((ROOT / "config/ranking.yaml").read_text())["weights"]
    assert sum(weights.values()) == pytest.approx(1)
    mapping = pd.read_csv(ROOT / "config/category_map.csv")
    assert list(mapping) == ["raw_category", "category", "valid_from", "valid_to"]

@pytest.mark.parametrize("name,field,value", [
    ("sentiment_agg", "period", "week 1"),
    ("sentiment_agg", "n_articles", "1.5"),
    ("sentiment_items", "p_pos", "1.1"),
    ("predictions", "is_out_of_sample", "yes"),
    ("predictions", "contrib_json", "[]"),
    ("alerts", "level", "urgent"),
])
def test_contract_value_domains(name, field, value):
    df = pd.read_csv(ROOT / f"data/snapshots/fixtures/{name}.csv", dtype=str)
    df.loc[0, field] = value
    with pytest.raises(ValueError): validate_table(name, df)


def test_fixture_manifest_is_explicitly_synthetic():
    import json
    manifest = json.loads((ROOT / "data/snapshots/fixtures/manifest.json").read_text())
    assert manifest["synthetic"] is True
    assert set(manifest["tables"]) == set(COLUMNS)
    assert "SYNTHETIC DEMO DATA" in manifest["warning"]
