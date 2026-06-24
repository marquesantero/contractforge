# Databricks Movie Custom Transform

This example shows how to keep ContractForge contracts as the control surface while allowing a Databricks notebook to perform a complex, platform-native treatment step.

It is based on the movie and ratings data shape used in the real cross-platform maturity tests. The important pattern is not the specific movie dataset; it is the boundary:

- bronze and silver contracts load and normalize source tables;
- a Databricks notebook joins multiple curated inputs and performs richer feature engineering;
- a gold `custom_transform` contract reads the reviewed notebook output and still applies ContractForge validation, write semantics, evidence and deployment versioning.

## Why this pattern exists

Some gold datasets need treatment that should not be forced into contract YAML:

- joins across multiple tables;
- windowed metrics;
- feature engineering;
- external libraries;
- model-specific preparation;
- business rules that are easier to review in code.

ContractForge should not hide that code. The contract declares the inputs, the expected output and the downstream controls. The Databricks adapter binds that declaration to a native notebook task.

## Runtime flow

1. `bronze_movie_ratings` reads raw ratings from a source table and writes bronze Delta.
2. `bronze_movie_titles` reads movie metadata and writes bronze Delta.
3. `silver_movie_ratings` standardizes ratings, derives event dates and deduplicates by rating event.
4. `prepare_movie_features` runs a Databricks notebook that joins ratings and titles, explodes genres and builds genre/rating-band metrics.
5. `gold_movie_feature_summary` uses `source.type: custom_transform` to read the notebook output table and write the governed gold table.

## Deploy

The example is designed for Databricks Asset Bundles.

```bash
databricks bundle validate
databricks bundle deploy
databricks bundle run movie_custom_transform
```

The bundle uses PyPI packages by default:

```yaml
dependencies:
  - contractforge-core
  - contractforge-databricks
```

If your workspace policy requires wheels, replace those dependency entries with workspace wheel paths.

## Source prerequisites

Create or load these source tables before running the job:

- `workspace.cf_movie_source.raw_ratings`
- `workspace.cf_movie_source.raw_movies`

Expected source columns:

`raw_ratings`

| Column | Meaning |
| --- | --- |
| rating_event_id | Stable event identifier |
| user_id | User identifier |
| movie_id | Movie identifier |
| rating | Numeric rating |
| rated_at | Rating timestamp |

`raw_movies`

| Column | Meaning |
| --- | --- |
| movie_id | Movie identifier |
| title | Movie title |
| genres | Pipe-delimited genre list, for example `Drama|Thriller` |
| release_year | Movie release year |

## Contract boundary

The gold contract does not embed the transformation logic. It records the reviewed notebook boundary:

```yaml
source:
  type: custom_transform
  inputs:
    - alias: ratings
      table: workspace.cf_movie_silver.s_movie_ratings
    - alias: movies
      table: workspace.cf_movie_bronze.b_movie_titles

transform:
  custom:
    name: movie_genre_feature_engineering
    output: workspace.cf_movie_tmp.movie_feature_engineering_output
    expected_columns:
      - genre
      - rating_band
      - rating_count
      - avg_rating
```

The notebook writes `workspace.cf_movie_tmp.movie_feature_engineering_output`. The ContractForge runtime then reads that table, validates the gold contract and writes `workspace.cf_movie_gold.g_movie_feature_summary`.

## Files

- `project.yaml` describes the full project and execution order.
- `databricks.yml` is the deployable Databricks Asset Bundle.
- `notebooks/run_contractforge.py` executes a contract from the deployed bundle.
- `notebooks/prepare_movie_features.py` performs the reviewed custom treatment.
- `contracts/databricks/**` contains separated ingestion, annotation and operation contracts.
