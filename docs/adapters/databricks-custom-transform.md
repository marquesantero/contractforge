# Databricks Custom Transform Example

This page documents a real-world Databricks pattern where ContractForge keeps
the contract boundary and Databricks executes a native notebook for complex
treatment before the final governed write.

The complete example lives in
[`examples/real-world/databricks-movie-custom-transform`](../../examples/real-world/databricks-movie-custom-transform/README.md).
It is based on the movie and ratings data shape used during ContractForge
maturity testing.

## When To Use It

Use `source.type: custom_transform` when the transformation is too specific for
portable declarative YAML but the output still needs ContractForge controls:

- multiple input tables;
- joins and windowed metrics;
- feature engineering;
- external libraries;
- business logic that is clearer in reviewed code.

The notebook is not a workaround. It is an explicit adapter binding. The
contract still declares source inputs, expected output, target, write mode,
quality rules, annotations, operations and evidence behavior.

## Runtime Flow

```text
bronze_movie_ratings contract
bronze_movie_titles contract
        |
silver_movie_ratings contract
        |
Databricks notebook: prepare_movie_features.py
        |
gold_movie_feature_summary custom_transform contract
        |
ContractForge validation, write, evidence and deployment versioning
```

The Databricks Asset Bundle contains a native notebook task:

```yaml
- task_key: prepare_movie_features
  notebook_task:
    notebook_path: ./notebooks/prepare_movie_features.py
    base_parameters:
      ratings_table: workspace.cf_movie_silver.s_movie_ratings
      movies_table: workspace.cf_movie_bronze.b_movie_titles
      output_table: workspace.cf_movie_tmp.movie_feature_engineering_output
      min_ratings: "10"
```

The gold ContractForge task depends on that notebook task. At runtime,
ContractForge reads the reviewed output table and applies normal schema,
quality, write and evidence handling.

## Gold Contract

```yaml
source:
  type: custom_transform
  intent: custom_treatment
  inputs:
    - alias: ratings
      table: workspace.cf_movie_silver.s_movie_ratings
    - alias: movies
      table: workspace.cf_movie_bronze.b_movie_titles

target:
  table: g_movie_feature_summary

layer: gold
mode: overwrite

transform:
  custom:
    name: movie_genre_feature_engineering
    output: workspace.cf_movie_tmp.movie_feature_engineering_output
    expected_columns:
      - genre
      - rating_band
      - rating_count
      - movie_count
      - user_count
      - avg_rating
      - rating_stddev
      - computed_at_utc
    parameters:
      min_ratings: 10

quality_rules:
  not_null: [genre, rating_band, rating_count, avg_rating]
  expressions:
    - name: positive_rating_count
      expression: rating_count > 0
      severity: abort
      message: Gold feature rows must represent at least one rating.
    - name: valid_average_rating
      expression: avg_rating BETWEEN 0 AND 5
      severity: abort
      message: Average rating must stay in the source rating scale.

extensions:
  databricks:
    custom_transform:
      notebook_path: ./notebooks/prepare_movie_features.py
      task_key: prepare_movie_features
      output_table: workspace.cf_movie_tmp.movie_feature_engineering_output
      base_parameters:
        ratings_table: workspace.cf_movie_silver.s_movie_ratings
        movies_table: workspace.cf_movie_bronze.b_movie_titles
        output_table: workspace.cf_movie_tmp.movie_feature_engineering_output
        min_ratings: "10"
    delta_properties:
      delta.enableChangeDataFeed: "true"
```

## Native Notebook Boundary

The notebook writes the reviewed output table:

```python
features = (
    ratings.alias("r")
    .join(movies.alias("m"), F.col("r.movie_id") == F.col("m.movie_id"), "inner")
    .select(
        F.col("r.rating_event_id"),
        F.col("r.user_id"),
        F.col("r.movie_id"),
        F.col("r.rating").cast("double").alias("rating"),
        F.col("r.rated_at").cast("timestamp").alias("rated_at"),
        F.col("m.release_year").cast("int").alias("release_year"),
        F.explode_outer(F.split(F.coalesce(F.col("m.genres"), F.lit("Unknown")), "\\|")).alias("genre"),
    )
    .withColumn(
        "rating_band",
        F.when(F.col("rating") >= 4.5, F.lit("excellent"))
        .when(F.col("rating") >= 3.5, F.lit("strong"))
        .when(F.col("rating") >= 2.5, F.lit("mixed"))
        .otherwise(F.lit("weak")),
    )
    .groupBy("genre", "rating_band")
    .agg(
        F.count("*").alias("rating_count"),
        F.countDistinct("movie_id").alias("movie_count"),
        F.countDistinct("user_id").alias("user_count"),
        F.avg("rating").alias("avg_rating"),
        F.stddev_pop("rating").alias("rating_stddev"),
        F.max("rated_at").alias("last_rating_at"),
    )
)
```

The notebook owns only the treatment output. It must not bypass ContractForge
quality, access, write-mode or evidence semantics.

## Deploy

The example uses PyPI dependencies in the Databricks Asset Bundle:

```yaml
dependencies:
  - contractforge-core
  - contractforge-databricks
```

Run it with Databricks Asset Bundles:

```bash
databricks bundle validate
databricks bundle deploy
databricks bundle run movie_custom_transform
```

If the workspace cannot install from PyPI, replace the dependencies with
workspace wheel paths produced by the release artifacts.
