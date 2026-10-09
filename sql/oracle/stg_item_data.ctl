-- SQL*Loader control file for the XSLT-flattened ODM (out/<run>/odm_long.csv)
-- Usage:
--   sqlldr userid=$ORA_USER control=stg_item_data.ctl data=odm_long.csv \
--          log=stg_item_data.log bad=stg_item_data.bad discard=stg_item_data.dsc errors=0
-- errors=0 : any rejected row aborts the load (rows are pre-validated upstream, so a
--            reject here means something changed between validation and load).
OPTIONS (SKIP=1)
LOAD DATA
CHARACTERSET UTF8
APPEND
INTO TABLE stg_item_data
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
TRAILING NULLCOLS
(
    studyoid            CHAR(64),
    subjectkey          CHAR(32),
    siteoid             CHAR(16),
    studyeventoid       CHAR(64),
    formoid             CHAR(64),
    itemgroupoid        CHAR(64),
    itemgrouprepeatkey  INTEGER EXTERNAL,
    itemoid             CHAR(64),
    value               CHAR(4000),
    load_run_id         CONSTANT 'SET_BY_WRAPPER'
)
