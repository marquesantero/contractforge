import pytest

from contractforge_core.partitioning import distinct_partition_values


def test_core_distinct_partition_values_deduplicates_in_order() -> None:
    assert distinct_partition_values(["BR", "US", "BR"]) == ("BR", "US")


def test_core_distinct_partition_values_rejects_empty_values() -> None:
    with pytest.raises(ValueError, match="at least one value"):
        distinct_partition_values([])


def test_core_distinct_partition_values_enforces_limit() -> None:
    with pytest.raises(ValueError, match="above limit"):
        distinct_partition_values([1, 2, 3], max_values=2)
