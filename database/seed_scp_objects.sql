INSERT INTO scp_objects (canonical_number)
SELECT
    'SCP-' ||
    CASE
        WHEN gs < 1000 THEN LPAD(gs::text, 3, '0')
        ELSE gs::text
    END
FROM generate_series(1, 7999) AS gs
ON CONFLICT (canonical_number) DO NOTHING;
