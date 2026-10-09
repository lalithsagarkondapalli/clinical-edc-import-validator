-- Staging tables for one import run (SQLite; same shape as sql/oracle/01_staging_ddl.sql)
DROP TABLE IF EXISTS stg_item_data;
DROP TABLE IF EXISTS stg_discrepancy;
DROP TABLE IF EXISTS stg_reconciliation;

CREATE TABLE stg_item_data (
    studyoid            TEXT NOT NULL,
    subjectkey          TEXT NOT NULL,
    siteoid             TEXT NOT NULL,
    studyeventoid       TEXT NOT NULL,
    formoid             TEXT NOT NULL,
    itemgroupoid        TEXT NOT NULL,
    itemgrouprepeatkey  INTEGER NOT NULL,
    itemoid             TEXT NOT NULL,
    value               TEXT,
    PRIMARY KEY (subjectkey, studyeventoid, itemgroupoid, itemgrouprepeatkey, itemoid)
);

CREATE TABLE stg_discrepancy (
    dataset TEXT, record_no TEXT, subject TEXT, record_key TEXT, item TEXT,
    rule_id TEXT, severity TEXT, value TEXT, message TEXT
);

CREATE TABLE stg_reconciliation (
    dataset TEXT PRIMARY KEY, source_records INTEGER, accepted INTEGER,
    rejected INTEGER, odm_xpath_count INTEGER, status TEXT
);
