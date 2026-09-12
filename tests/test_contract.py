from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from importlib.resources import files
from pathlib import Path

PUBLIC_ACTIVITY_FIELDS = {
    "event_id",
    "occurred_at",
    "operation_id",
    "kind",
    "source",
    "direction",
    "from",
    "to",
    "asset",
    "gross",
    "fee",
    "net",
    "balance_before",
    "balance_after",
    "leg_index",
}


def test_packaged_contract_hash_and_allowlists() -> None:
    contract_dir = files("atraxis._contract")
    payload = contract_dir.joinpath("guild-commerce-v1.json").read_bytes()
    expected = contract_dir.joinpath("guild-commerce-v1.sha256").read_text().strip()
    assert hashlib.sha256(payload).hexdigest() == expected

    spec = json.loads(payload)
    assert set(spec["components"]["schemas"]["WarehouseItem"]["properties"]) == {
        "warehouse_item_id",
        "item_id",
        "name",
        "quantity",
        "durability",
        "max_durability",
        "transfer_restricted",
    }
    assert set(spec["components"]["schemas"]["Activity"]["properties"]) == (
        PUBLIC_ACTIVITY_FIELDS
    )


def test_sync_validator_rejects_unreviewed_schema_field(tmp_path: Path) -> None:
    payload = files("atraxis._contract").joinpath("guild-commerce-v1.json").read_text()
    spec = deepcopy(json.loads(payload))
    spec["components"]["schemas"]["Activity"]["properties"]["unexpected"] = {
        "type": "string"
    }
    source = tmp_path / "contract.json"
    source.write_text(json.dumps(spec), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/sync_openapi.py",
            str(source),
            "--output",
            str(tmp_path / "snapshot.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "reviewed public contract" in result.stderr
    assert "unexpected" not in result.stderr


def test_contract_uses_only_synthetic_credentials() -> None:
    payload = files("atraxis._contract").joinpath("guild-commerce-v1.json").read_text()
    assert "agk_example.redacted" in payload
    assert "Authorization: Bearer agk_" not in payload.replace(
        "Authorization: Bearer agk_example.redacted", ""
    )
