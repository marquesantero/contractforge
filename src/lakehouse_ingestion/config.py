"""Configuração global, tipos compartilhados e constantes do framework.

Este módulo é folha (não depende de outros do pacote) e é importado por todos
os demais. Define ``Literal``s para narrowing estático e a singleton ``CONFIG``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union

from pyspark.sql import DataFrame

FRAMEWORK_VERSION = "1.0.5"
CTRL_SCHEMA_VERSION = 3

#: Camadas reconhecidas (Medallion Architecture).
Layer = Literal["bronze", "silver", "gold"]

#: Modos oficiais de escrita; ver ``writers.py`` para a semântica de cada um.
WriteMode = Literal[
    "scd0_append",
    "scd0_overwrite",
    "scd1_upsert",
    "scd1_hash_diff",
    "scd2_historical",
    "snapshot_soft_delete",
]

#: Estratégia do MERGE em ``scd1_upsert``.
MergeStrategy = Literal["delta", "delta_by_partition", "replace_partitions"]

#: Política de evolução de schema do destino.
SchemaPolicy = Literal["permissive", "additive_only", "strict"]

#: Ação quando uma regra de qualidade falha.
QualityFailAction = Literal["fail", "warn", "quarantine"]

#: Fonte aceita pelo plano: nome de tabela ou DataFrame em memória.
Source = Union[str, DataFrame]

#: Conjunto usado em validação runtime (Literal só faz tipagem estática).
VALID_WRITE_MODES = {
    "scd0_append",
    "scd0_overwrite",
    "scd1_upsert",
    "scd1_hash_diff",
    "scd2_historical",
    "snapshot_soft_delete",
}

#: Camadas válidas para validação runtime.
VALID_LAYERS = {"bronze", "silver", "gold"}

#: Estratégias de merge válidas para validação runtime.
VALID_MERGE_STRATEGIES = {"delta", "delta_by_partition", "replace_partitions"}

#: Políticas de schema válidas para validação runtime.
VALID_SCHEMA_POLICIES = {"permissive", "additive_only", "strict"}

#: Ações válidas em falha de qualidade para validação runtime.
VALID_QUALITY_FAIL_ACTIONS = {"fail", "warn", "quarantine"}

#: Formatos de explain aceitos por ``DataFrame.explain``.
VALID_EXPLAIN_FORMATS = {"simple", "extended", "codegen", "cost", "formatted"}

#: Colunas gerenciadas pelo framework. Excluídas do hash determinístico em
#: ``schema.hash_columns`` para que mudanças em controle não invalidem
#: ``row_hash``.
CONTROL_COLUMNS = {
    "ingestion_date",
    "ingestion_ts_utc",
    "source_system",
    "__run_id",
    "row_hash",
    "valid_from",
    "valid_to",
    "is_current",
    "is_active",
    "deleted_at",
    "changed_columns",
}


@dataclass(frozen=True)
class FrameworkConfig:
    """Configuração global do framework.

    Imutável. A instância padrão é ``CONFIG``. Para sobrescrever defaults em
    todo o processo, faça monkey-patch antes da primeira chamada:

    >>> import lakehouse_ingestion.config as cfg
    >>> cfg.CONFIG = cfg.FrameworkConfig(ctrl_schema="my_ops")

    Em prática, prefira passar ``ctrl_schema``/etc. no ``IngestionPlan``.

    Attributes:
        default_catalog: Catálogo Unity quando não especificado no plan.
        default_source_system: ``source_system`` quando não informado.
        default_partition_col: Coluna de partição padrão (``ingestion_date``).
        ctrl_schema: Schema onde as ctrl tables vivem.
        ctrl_table_*: Nomes das ctrl tables.
        max_error_len: Tamanho máximo de ``error_message`` em ctrl tables.
        default_lock_ttl_minutes: TTL do lock best-effort em ``acquire_lock``.
        default_retry_attempts: Tentativas em ``with_retry`` para conflitos Delta.
        default_retry_backoff_seconds: Backoff linear entre tentativas.
        max_inline_accepted_values: Limite de itens em ``accepted_values``.
        max_partition_predicate_values: Limite de valores em predicados ``IN``.
    """

    default_catalog: str = "main"
    default_source_system: str = "default"
    default_partition_col: str = "ingestion_date"
    ctrl_schema: str = "ops"
    ctrl_table_runs: str = "ctrl_ingestion_runs"
    ctrl_table_state: str = "ctrl_ingestion_state"
    ctrl_table_quality: str = "ctrl_ingestion_quality"
    ctrl_table_quarantine: str = "ctrl_ingestion_quarantine"
    ctrl_table_locks: str = "ctrl_ingestion_locks"
    ctrl_table_explain: str = "ctrl_ingestion_explain"
    ctrl_table_lineage: str = "ctrl_ingestion_lineage"
    ctrl_table_metadata: str = "ctrl_ingestion_metadata"
    ctrl_table_errors: str = "ctrl_ingestion_errors"
    max_error_len: int = 8000
    default_lock_ttl_minutes: int = 120
    default_retry_attempts: int = 3
    default_retry_backoff_seconds: int = 5
    max_inline_accepted_values: int = 1000
    max_partition_predicate_values: int = 1000


#: Singleton de configuração. Importada por outros módulos.
CONFIG = FrameworkConfig()
