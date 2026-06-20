CREATE OR REPLACE TABLE CONTRACTFORGE_TEST_DB.PUBLIC.CF_HASHDIFF_PROD_SOURCE (
  "customer_id" NUMBER,
  "segment" VARCHAR,
  "status" VARCHAR,
  "balance" NUMBER(18,2),
  "updated_at" TIMESTAMP_NTZ,
  "payload_hash_noise" VARCHAR
);

INSERT INTO CONTRACTFORGE_TEST_DB.PUBLIC.CF_HASHDIFF_PROD_SOURCE (
  "customer_id",
  "segment",
  "status",
  "balance",
  "updated_at",
  "payload_hash_noise"
)
SELECT * FROM VALUES
  (1, 'retail', 'active', 100.00, '2026-06-09T00:00:00'::TIMESTAMP_NTZ, 'a'),
  (2, 'retail', 'active', 250.00, '2026-06-09T00:00:00'::TIMESTAMP_NTZ, 'b'),
  (3, 'enterprise', 'active', 1000.00, '2026-06-09T00:00:00'::TIMESTAMP_NTZ, 'c'),
  (4, 'enterprise', 'inactive', 0.00, '2026-06-09T00:00:00'::TIMESTAMP_NTZ, 'd');
