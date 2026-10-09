-- Each query returns ZERO rows when the load is consistent.
-- check_name is returned so a failing row says which check broke.

-- R1: ItemGroup records in staging match the accepted count per dataset
SELECT 'R1_record_count' AS check_name, r.dataset, r.accepted AS expected, COALESCE(s.n, 0) AS actual
FROM stg_reconciliation r
LEFT JOIN (
    SELECT substr(itemgroupoid, 4) AS dataset,
           COUNT(DISTINCT subjectkey || '|' || studyeventoid || '|' || itemgrouprepeatkey) AS n
    FROM stg_item_data GROUP BY itemgroupoid
) s ON s.dataset = r.dataset
WHERE r.accepted <> COALESCE(s.n, 0);

-- R2: no subject in clinical data without an accepted DM record
SELECT 'R2_orphan_subject' AS check_name, d.subjectkey, d.itemgroupoid, NULL, NULL
FROM (SELECT DISTINCT subjectkey, itemgroupoid FROM stg_item_data WHERE itemgroupoid <> 'IG.DM') d
WHERE d.subjectkey NOT IN (SELECT subjectkey FROM stg_item_data WHERE itemgroupoid = 'IG.DM');

-- R3: subject prefix agrees with site
SELECT DISTINCT 'R3_site_mismatch' AS check_name, subjectkey, siteoid, NULL, NULL
FROM stg_item_data WHERE substr(subjectkey, 1, 3) <> siteoid;

-- R4: source = accepted + rejected for every dataset
SELECT 'R4_balance' AS check_name, dataset, source_records, accepted + rejected, NULL
FROM stg_reconciliation WHERE source_records <> accepted + rejected;
