from __future__ import annotations

from contractforge_core.naming import NamingConfig, derive_names, normalize_identifier, normalize_slug


def test_normalize_slug_is_ascii_lowercase_and_path_safe() -> None:
    assert normalize_slug("Customer Credit Limits") == "customer-credit-limits"
    assert normalize_slug("Crédito Cliente!") == "credito-cliente"
    assert normalize_slug("  main.silver.orders  ") == "main-silver-orders"


def test_normalize_identifier_is_python_safe() -> None:
    assert normalize_identifier("Customer Credit Limits") == "customer_credit_limits"
    assert normalize_identifier("2026 Orders") == "n_2026_orders"


def test_derive_names_uses_target_table_as_stable_default() -> None:
    names = derive_names(target_table="s_orders_complex", layer="silver", domain="sales")

    assert names.display_name == "S Orders Complex"
    assert names.logical_name == "s_orders_complex"
    assert names.slug == "s-orders-complex"
    assert names.contract_basename == "s_orders_complex"
    assert names.bundle_name == "cf-sales-silver-s-orders-complex"
    assert names.job_name == "cf_sales_silver_s_orders_complex"
    assert names.task_key == "cf_sales_silver_s_orders_complex"


def test_derive_names_allows_explicit_overrides() -> None:
    names = derive_names(
        target_table="orders",
        layer="silver",
        config=NamingConfig(
            display_name="Orders Current State",
            logical_name="orders_current",
            slug="orders-current",
            contract_basename="orders_contract",
            bundle_name="orders-bundle",
            job_name="Orders Silver Job",
            task_key="orders_silver_task",
        ),
    )

    assert names.display_name == "Orders Current State"
    assert names.contract_basename == "orders_contract"
    assert names.bundle_name == "orders-bundle"
    assert names.job_name == "Orders Silver Job"
    assert names.task_key == "orders_silver_task"
