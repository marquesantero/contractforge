# Databricks notebook source
from typing import Any, Callable, cast

from contractforge import ingest_bundle, load_contract_bundle

dbutils_obj = globals().get("dbutils")
if dbutils_obj is None:
    raise RuntimeError("This notebook must run on Databricks with dbutils available")

dbutils_typed = cast(Any, dbutils_obj)
dbutils_typed.widgets.text("contract", "")
contract = dbutils_typed.widgets.get("contract")

if not contract:
    raise ValueError("Widget 'contract' is required")

bundle = load_contract_bundle(contract)
result = ingest_bundle(bundle)

display_fn = cast(Callable[[object], None], globals().get("display", print))
display_fn(result)

