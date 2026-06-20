# ContractForge

## Contratos portáveis para ingestão de dados governada

Uma apresentação técnica sobre a filosofia do projeto, o que já funciona, onde estão os limites e por que a proposta é diferente de um simples framework de conectores.

---

# 1. A tese

O ContractForge parte de uma ideia simples:

> a intenção de ingestão deve ser estável; a execução deve ser nativa.

O contrato descreve **o que precisa acontecer**: fonte, destino, modo de escrita, qualidade, transformação, governança, operação e evidência.

O adapter decide **como preservar isso** em Databricks, AWS, Snowflake, Fabric ou GCP.

---

# 2. O problema que o projeto ataca

Hoje, cada plataforma empurra o time para uma linguagem operacional diferente:

- Databricks fala Delta, Unity Catalog, Jobs, Lakeflow e notebooks.
- AWS fala Glue, Iceberg, S3, Lake Formation, Athena e Step Functions.
- Snowflake fala SQL warehouse, tasks, procedures, stages e policies.
- Fabric fala Lakehouse, notebooks, OneLake, shortcuts e workspace security.
- GCP fala BigQuery, GCS, BigLake, Dataplex, Workflows e Dataflow.

O resultado comum é duplicação de lógica, documentação divergente e migração cara.

---

# 3. A filosofia

ContractForge não tenta esconder que as plataformas são diferentes.

Ele separa três coisas:

1. **Semântica comum**: contrato, intenção, qualidade, transformação, evidência.
2. **Binding nativo**: tabela física, runtime, warehouse, bucket, lakehouse, policy.
3. **Diagnóstico honesto**: suportado, suportado com avisos, requer revisão ou não suportado.

O objetivo não é "fazer funcionar de qualquer jeito".

O objetivo é preservar semântica sem downgrade silencioso.

---

# 4. Arquitetura mental

```text
Contrato YAML
  -> Core semântico
  -> Normalização e validação
  -> Capability planning
  -> Adapter nativo
  -> Runtime da plataforma
  -> Evidência de execução
```

O core não precisa conhecer Spark, boto3, Snowpark, Fabric API ou BigQuery client.

Essas dependências pertencem aos adapters.

---

# 5. O que é um contrato

Um contrato de ingestão declara:

- de onde os dados vêm;
- onde serão escritos;
- qual camada medallion representam;
- qual modo de escrita será usado;
- quais transformações são esperadas;
- quais regras de qualidade bloqueiam, avisam ou mandam para quarentena;
- quais metadados operacionais e de governança devem existir;
- qual evidência precisa ser produzida.

---

# 6. Exemplo: contrato bronze REST

Este contrato é o primeiro passo do exemplo USGS GeoJSON.

```yaml
source:
  type: rest_api
  name: usgs_earthquake_2_5_day_geojson
  request:
    url: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson
    method: GET
  response:
    mode: raw
    raw_column: raw_response

target:
  schema: cf_usgs_rest_bronze
  table: b_usgs_earthquake_geojson

layer: bronze
mode: overwrite
schema_policy: permissive

quality_rules:
  required_columns: [raw_response, response_page_number]
  not_null: [raw_response]
  unique_key: [response_page_number]
```

---

# 7. O que quase não muda entre adapters

No projeto USGS, Databricks, AWS, Snowflake, Fabric e GCP usam a mesma intenção:

| Parte do contrato | Portabilidade |
| --- | --- |
| `source.type: rest_api` | igual |
| URL e método HTTP | iguais |
| `response.mode: raw` | igual |
| `layer: bronze` | igual |
| `mode: overwrite` | igual |
| `schema_policy: permissive` | igual |
| regras de qualidade | iguais |

O que muda é o binding físico: catálogo, schema/database, table e alguns `extensions.<adapter>`.

---

# 8. Diferença real: binding físico

```yaml
# Databricks
target:
  catalog: workspace
  schema: cf_usgs_rest_bronze
  table: b_usgs_earthquake_geojson
extensions:
  databricks:
    delta_properties:
      delta.enableChangeDataFeed: "true"
```

```yaml
# AWS
target:
  catalog: contractforge
  schema: cf_usgs_rest_bronze
  table: b_usgs_earthquake_geojson
extensions:
  aws:
    iceberg:
      warehouse: s3://.../warehouse/usgs-rest/
```

---

# 9. Mesma intenção em Snowflake, Fabric e GCP

```yaml
# Snowflake
target:
  catalog: CONTRACTFORGE_TEST_DB
  schema: PUBLIC
  table: CF_USGS_REST_BRONZE
```

```yaml
# Fabric
target:
  catalog: workspace
  schema: cf_usgs_rest_bronze
  table: b_usgs_earthquake_geojson
```

```yaml
# GCP BigQuery
target:
  catalog: midyear-system-499521-p3
  schema: contractforge_gcp_usgs_rest_bronze
  table: b_usgs_earthquake_geojson
```

O contrato muda onde precisa mudar: no endereço físico da plataforma.

---

# 10. Projeto, não arquivo solto

O `project.yaml` organiza ambientes, ordem de execução e contratos por adapter.

```yaml
execution_order:
  - name: bronze_usgs_geojson
    layer: bronze
    depends_on: []
    contracts:
      databricks: contracts/databricks/bronze/bronze_usgs_geojson/...
      aws: contracts/aws/bronze/bronze_usgs_geojson/...
      snowflake: contracts/snowflake/bronze/bronze_usgs_geojson/...
      fabric: contracts/fabric/bronze/bronze_usgs_geojson/...
      gcp: contracts/gcp/bronze/bronze_usgs_geojson/...

  - name: silver_usgs_events
    layer: silver
    depends_on: [bronze_usgs_geojson]

  - name: gold_usgs_daily_summary
    layer: gold
    depends_on: [silver_usgs_events]
```

---

# 11. Medallion completo

O exemplo USGS não é apenas um smoke de fonte REST.

Ele cobre:

- bronze: captura raw do GeoJSON;
- silver: normalização e explosão dos eventos;
- gold: resumo diário;
- gold: bandas de magnitude;
- qualidade;
- evidência;
- execução end-to-end por adapter.

---

# 12. O que já funciona

| Área | Estado |
| --- | --- |
| Core | modelo semântico, validação, planejamento e evidência |
| Databricks | adapter de referência |
| AWS | superfície estável Glue/Iceberg |
| Snowflake | superfície estável SQL warehouse/Snowpark procedure |
| Fabric | superfície estável Lakehouse/notebook |
| GCP | superfície estável BigQuery/BigLake |
| ContractForge AI | geração, revisão, validação e enriquecimento com crivo determinístico |

"Stable supported surface" não significa tudo que a plataforma oferece.

Significa que a superfície documentada tem evidência, limites e semântica preservada.

---

# 13. Adapter não é tradutor cego

Cada adapter precisa responder:

- esta fonte existe de forma equivalente?
- este modo de escrita preserva semântica?
- a regra de qualidade é executável?
- a governança pode ser aplicada ou só revisada?
- a evidência pode ser registrada?
- existe risco de downgrade?

Se a resposta não for segura, o adapter deve avisar, exigir revisão ou bloquear.

---

# 14. Exemplo JDBC: contrato mais rico

```yaml
source:
  type: connection
  connection_path: project://connections/supabase.yaml
  table: cf_supabase_newcore_demo.product_movements
  read:
    partition_column: id
    num_partitions: 16

layer: bronze
mode: upsert
schema_policy: additive_only
merge_keys: [movement_uid]
on_quality_fail: quarantine

transform:
  composite_keys:
    movement_uid: [product_id, movement_seq]
  derive:
    movement_value: quantity * unit_cost
    movement_date: to_date(event_ts)
  deduplicate:
    keys: [movement_uid]
```

---

# 15. Qualidade como parte do contrato

```yaml
quality_rules:
  not_null:
    - movement_uid
    - product_id
    - movement_seq
    - movement_type
    - event_ts
  unique_key:
    - movement_uid
  accepted_values:
    movement_type: [inbound, outbound, adjustment]
  expressions:
    - name: non_zero_quantity
      expression: quantity <> 0
      severity: quarantine
```

As regras não são comentário: elas entram no plano, no runtime e na evidência.

---

# 16. Streaming com fronteira clara

```yaml
source:
  type: kafka_available_now
  system: confluent_cloud
  bootstrap_servers: pkc-619z3.us-east1.gcp.confluent.cloud:9092
  topic: cf-databricks-orders
  checkpoint_location: /Volumes/.../checkpoints/...
  starting_offsets: earliest

layer: bronze
mode: append
schema_policy: additive_only
```

AWS, Databricks, Fabric e GCP possuem caminhos validados em superfícies específicas.

Snowflake mantém Kafka/Snowpipe/Streams como decisão separada de maturidade.

---

# 17. Evidence como superfície de produto

O ContractForge não termina quando escreve a tabela.

Ele registra:

- execução;
- erros;
- qualidade;
- quarentena;
- mudanças de schema;
- lineage;
- governança;
- custo quando a plataforma expõe sinais úteis.

Isso transforma ingestão em algo auditável, não apenas executável.

---

# 18. ContractForge AI

O `contractforge-ai` não deve "inventar contratos finais".

A filosofia correta é:

1. a IA interpreta intenção;
2. a parte determinística transforma intenção em parâmetros aceitáveis;
3. o core e os adapters validam;
4. o resultado vira projeto revisável;
5. o `AI_REVIEW.html` mostra decisões, avisos, evidências e próximos passos.

A IA ajuda. O crivo determinístico governa.

---

# 19. O review oficial

O `AI_REVIEW.html` é pensado para aprovação técnica.

Ele deve responder:

- o que foi pedido;
- o que foi gerado;
- quais decisões ainda existem;
- quais validações passaram;
- quais warnings permanecem;
- quais arquivos foram usados como evidência;
- onde a IA opinou e onde o sistema determinístico decidiu.

---

# 20. Onde o projeto é diferente de dbt, Airbyte e Fivetran

| Ferramenta | Foco | Diferença do ContractForge |
| --- | --- | --- |
| dbt | transformação depois que o dado chegou | ContractForge governa chegada, escrita, qualidade e evidência |
| Airbyte | conectores e replicação | ContractForge foca semântica portável e execução nativa |
| Fivetran | ELT gerenciado | ContractForge preserva contrato e runtime do cliente |
| Ferramentas de catálogo | metadados | ContractForge usa metadados como parte da execução governada |

---

# 21. Onde ele é forte hoje

- Projetos multi-adapter.
- Migração entre plataformas.
- Consultorias que precisam reutilizar contratos.
- Times de plataforma que querem padronizar ingestão.
- Data products que precisam provar qualidade e lineage.
- Ambientes em que segurança e governança são parte do fluxo.

---

# 22. Onde exige cuidado

- Não é a ferramenta mais simples para uma carga descartável.
- Não deve prometer equivalência onde a plataforma não oferece a mesma semântica.
- "Stable supported surface" deve ser explicado sempre.
- Cada adapter precisa continuar com evidências reais.
- A documentação deve separar claramente: suportado, suportado com avisos, review-required e unsupported.

---

# 23. Mensagem final

ContractForge é uma tentativa pragmática de resolver um problema recorrente:

> como manter uma intenção de ingestão governada enquanto cada plataforma exige execução nativa diferente?

A resposta do projeto é:

- contrato como fonte da verdade;
- core semântico neutro;
- adapters responsáveis por runtime nativo;
- evidência como primeira classe;
- IA como apoio, nunca como bypass da validação.

---

# 24. Frase de fechamento

Defina a intenção uma vez.

Preserve a semântica.

Execute nativamente.

Registre evidência.

E nunca esconda o que precisa de revisão.

