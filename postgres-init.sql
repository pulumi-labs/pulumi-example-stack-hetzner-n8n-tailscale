\set ON_ERROR_STOP on
CREATE ROLE n8n_app LOGIN PASSWORD '@@N8N_PASSWORD@@';
CREATE DATABASE n8n OWNER n8n_app;
REVOKE ALL ON DATABASE n8n FROM PUBLIC;
CREATE ROLE receipt_writer LOGIN PASSWORD '@@RECEIPTS_PASSWORD@@';
CREATE DATABASE receipts;
REVOKE ALL ON DATABASE receipts FROM PUBLIC;
GRANT CONNECT ON DATABASE receipts TO receipt_writer;
\connect receipts
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA automation;
CREATE TABLE automation.receipts (
    order_id text PRIMARY KEY CHECK (length(order_id) BETWEEN 1 AND 80),
    item_count integer NOT NULL CHECK (item_count > 0),
    total_cents integer NOT NULL CHECK (total_cents >= 0),
    recorded_at timestamptz NOT NULL DEFAULT now()
);
GRANT USAGE ON SCHEMA automation TO receipt_writer;
GRANT SELECT, INSERT ON automation.receipts TO receipt_writer;
