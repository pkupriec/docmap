CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =====================================================
-- SCP OBJECTS
-- =====================================================

CREATE TABLE scp_objects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_number TEXT NOT NULL UNIQUE
);

-- =====================================================
-- DOCUMENTS
-- =====================================================

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scp_object_id UUID REFERENCES scp_objects(id),
    url TEXT NOT NULL UNIQUE,
    title TEXT,
    last_checked_at TIMESTAMP DEFAULT now(),
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_documents_scp
ON documents(scp_object_id);

-- =====================================================
-- DOCUMENT SNAPSHOTS
-- =====================================================

CREATE TABLE document_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id),
    raw_html TEXT,
    clean_text TEXT,
    pdf_blob BYTEA,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_snapshots_document
ON document_snapshots(document_id);

CREATE INDEX idx_document_snapshots_document_created_desc
ON document_snapshots(document_id, created_at DESC);

CREATE INDEX idx_document_snapshots_created_at_id
ON document_snapshots(created_at, id);

-- =====================================================
-- EXTRACTION RUNS
-- =====================================================

CREATE TABLE extraction_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id UUID NOT NULL REFERENCES document_snapshots(id),
    model TEXT,
    prompt_version TEXT,
    pipeline_version TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE UNIQUE INDEX uq_extraction_runs_snapshot_id
ON extraction_runs(snapshot_id);

-- =====================================================
-- LOCATION MENTIONS
-- =====================================================

CREATE TABLE location_mentions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES extraction_runs(id),
    mention_text TEXT,
    normalized_location TEXT,
    precision TEXT,
    relation_type TEXT,
    confidence FLOAT,
    evidence_quote TEXT
);

CREATE INDEX idx_mentions_run
ON location_mentions(run_id);

CREATE INDEX idx_mentions_location
ON location_mentions(normalized_location);

-- =====================================================
-- GEO LOCATIONS
-- =====================================================

CREATE TABLE geo_locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    normalized_location TEXT NOT NULL UNIQUE,
    country TEXT,
    region TEXT,
    city TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    precision TEXT,
    geom GEOGRAPHY(Point, 4326)
);

CREATE INDEX idx_geo_geom
ON geo_locations USING GIST(geom);

-- =====================================================
-- DOCUMENT LOCATIONS
-- =====================================================

CREATE TABLE document_locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id),
    location_id UUID NOT NULL REFERENCES geo_locations(id),
    mention_id UUID REFERENCES location_mentions(id)
);

CREATE INDEX idx_doc_locations_doc
ON document_locations(document_id);

CREATE INDEX idx_doc_locations_location
ON document_locations(location_id);

CREATE UNIQUE INDEX uq_document_locations_mention_id
ON document_locations(mention_id)
WHERE mention_id IS NOT NULL;

-- =====================================================
-- BI TABLES
-- =====================================================

CREATE TABLE bi_documents (
    document_id UUID PRIMARY KEY REFERENCES documents(id),
    scp_object_id UUID REFERENCES scp_objects(id),
    canonical_number TEXT,
    url TEXT NOT NULL,
    title TEXT,
    latest_snapshot_id UUID REFERENCES document_snapshots(id),
    latest_snapshot_at TIMESTAMP,
    location_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE bi_locations (
    location_id UUID PRIMARY KEY REFERENCES geo_locations(id),
    normalized_location TEXT NOT NULL,
    country TEXT,
    region TEXT,
    city TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    precision TEXT,
    document_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE bi_document_locations (
    document_id UUID NOT NULL REFERENCES documents(id),
    location_id UUID NOT NULL REFERENCES geo_locations(id),
    mention_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, location_id)
);

CREATE INDEX idx_bi_document_locations_location
ON bi_document_locations(location_id);
