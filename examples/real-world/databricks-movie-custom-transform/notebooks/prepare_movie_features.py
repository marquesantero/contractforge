# Databricks notebook source
from __future__ import annotations

import json

from pyspark.sql import functions as F


def _split_table_name(table_name: str) -> tuple[str, str, str]:
    parts = [part.strip("` ") for part in table_name.split(".") if part.strip("` ")]
    if len(parts) != 3:
        raise ValueError("output_table must use catalog.schema.table format")
    return parts[0], parts[1], parts[2]


dbutils.widgets.text("ratings_table", "workspace.cf_movie_silver.s_movie_ratings")
dbutils.widgets.text("movies_table", "workspace.cf_movie_bronze.b_movie_titles")
dbutils.widgets.text("output_table", "workspace.cf_movie_tmp.movie_feature_engineering_output")
dbutils.widgets.text("min_ratings", "10")

ratings_table = dbutils.widgets.get("ratings_table")
movies_table = dbutils.widgets.get("movies_table")
output_table = dbutils.widgets.get("output_table")
min_ratings = int(dbutils.widgets.get("min_ratings"))

catalog, schema_name, _ = _split_table_name(output_table)
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema_name}`")

ratings = spark.table(ratings_table)
movies = spark.table(movies_table)

joined = (
    ratings.alias("r")
    .join(movies.alias("m"), F.col("r.movie_id") == F.col("m.movie_id"), "inner")
    .select(
        F.col("r.rating_event_id"),
        F.col("r.user_id"),
        F.col("r.movie_id"),
        F.col("r.rating").cast("double").alias("rating"),
        F.col("r.rated_at").cast("timestamp").alias("rated_at"),
        F.col("m.title"),
        F.col("m.release_year").cast("int").alias("release_year"),
        F.explode_outer(F.split(F.coalesce(F.col("m.genres"), F.lit("Unknown")), "\\|")).alias("genre"),
    )
    .withColumn("genre", F.trim(F.col("genre")))
    .withColumn(
        "rating_band",
        F.when(F.col("rating") >= 4.5, F.lit("excellent"))
        .when(F.col("rating") >= 3.5, F.lit("strong"))
        .when(F.col("rating") >= 2.5, F.lit("mixed"))
        .otherwise(F.lit("weak")),
    )
    .withColumn("rating_month", F.date_trunc("month", F.col("rated_at")))
)

features = (
    joined.groupBy("genre", "rating_band")
    .agg(
        F.count("*").alias("rating_count"),
        F.countDistinct("movie_id").alias("movie_count"),
        F.countDistinct("user_id").alias("user_count"),
        F.avg("rating").alias("avg_rating"),
        F.stddev_pop("rating").alias("rating_stddev"),
        F.min("release_year").alias("oldest_release_year"),
        F.max("release_year").alias("newest_release_year"),
        F.max("rated_at").alias("last_rating_at"),
    )
    .filter(F.col("rating_count") >= min_ratings)
    .withColumn("computed_at_utc", F.current_timestamp())
)

(
    features.write.format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(output_table)
)

dbutils.notebook.exit(
    json.dumps(
        {
            "output_table": output_table,
            "rows_written": features.count(),
            "min_ratings": min_ratings,
        },
        sort_keys=True,
    )
)
