-- Oracle staging DDL (reference; mirrors sql/sqlite/01_staging_ddl.sql).
-- Not executed in CI - there is no Oracle instance in the public pipeline.
CREATE TABLE stg_item_data (
    studyoid            VARCHAR2(64)   NOT NULL,
    subjectkey          VARCHAR2(32)   NOT NULL,
    siteoid             VARCHAR2(16)   NOT NULL,
    studyeventoid       VARCHAR2(64)   NOT NULL,
    formoid             VARCHAR2(64)   NOT NULL,
    itemgroupoid        VARCHAR2(64)   NOT NULL,
    itemgrouprepeatkey  NUMBER(6)      NOT NULL,
    itemoid             VARCHAR2(64)   NOT NULL,
    value               VARCHAR2(4000),
    load_run_id         VARCHAR2(64),
    loaded_at           TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT pk_stg_item_data PRIMARY KEY
        (subjectkey, studyeventoid, itemgroupoid, itemgrouprepeatkey, itemoid)
);
