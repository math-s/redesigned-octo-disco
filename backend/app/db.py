from __future__ import annotations

from typing import Any


def get_table(table_name: str) -> Any:
    # Lazy import so unit tests can run without AWS deps installed.
    import boto3  # type: ignore

    ddb = boto3.resource("dynamodb")
    return ddb.Table(table_name)

