"""Build a CDISC ODM 1.3.2 snapshot (ClinicalData + minimal metadata) for EDC import."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from lxml import etree

ODM_NS = "http://www.cdisc.org/ns/odm/v1.3"
NSMAP = {None: ODM_NS}
XP_NS = {"odm": ODM_NS}

ODM_TYPES = {"text": "text", "code": "text", "integer": "integer", "float": "float",
             "date": "date", "datetime": "datetime"}


def _e(parent, tag, **attrs):
    return etree.SubElement(parent, f"{{{ODM_NS}}}{tag}", {k: str(v) for k, v in attrs.items()})


def build_odm(spec: dict, accepted: dict[str, list], file_oid: str, created: datetime) -> etree._ElementTree:
    st = spec["study"]
    root = etree.Element(f"{{{ODM_NS}}}ODM", nsmap=NSMAP, attrib={
        "FileOID": file_oid,
        "FileType": "Snapshot",
        "ODMVersion": "1.3.2",
        "CreationDateTime": created.strftime("%Y-%m-%dT%H:%M:%S"),
        "SourceSystem": st["source_system"],
    })

    # --- metadata: one ItemDef per mapped item, generated from the spec
    study = _e(root, "Study", OID=st["oid"])
    gv = _e(study, "GlobalVariables")
    _e(gv, "StudyName").text = st["name"]
    _e(gv, "StudyDescription").text = st["description"]
    _e(gv, "ProtocolName").text = st["name"]
    mdv = _e(study, "MetaDataVersion", OID=st["metadata_version_oid"],
             Name=f"Transfer spec v{st['spec_version']}")
    for ds in spec["datasets"].values():
        for item in ds["items"]:
            _e(mdv, "ItemDef", OID=item["oid"], Name=item["source"], DataType=ODM_TYPES[item["type"]])

    # --- clinical data, grouped subject -> event -> form
    cd = _e(root, "ClinicalData", StudyOID=st["oid"], MetaDataVersionOID=st["metadata_version_oid"])
    tree: dict = defaultdict(lambda: {"site": None, "events": defaultdict(lambda: defaultdict(list))})
    for ds_name, recs in accepted.items():
        ds = spec["datasets"][ds_name]
        for r in recs:
            tree[r.subject]["site"] = r.site
            tree[r.subject]["events"][r.event_oid][ds["form_oid"]].append((ds, r))

    for subject in sorted(tree):
        sd = _e(cd, "SubjectData", SubjectKey=subject)
        _e(sd, "SiteRef", LocationOID=tree[subject]["site"])
        for event_oid in sorted(tree[subject]["events"]):
            se = _e(sd, "StudyEventData", StudyEventOID=event_oid)
            for form_oid in sorted(tree[subject]["events"][event_oid]):
                fd = _e(se, "FormData", FormOID=form_oid)
                for ds, r in tree[subject]["events"][event_oid][form_oid]:
                    ig = _e(fd, "ItemGroupData", ItemGroupOID=ds["item_group_oid"],
                            ItemGroupRepeatKey=r.repeat_key)
                    for item in ds["items"]:       # spec order -> stable diffs
                        if item["oid"] in r.items:
                            _e(ig, "ItemData", ItemOID=item["oid"], Value=r.items[item["oid"]])
    return etree.ElementTree(root)


def validate_xsd(tree: etree._ElementTree, xsd_path: str) -> list[str]:
    schema = etree.XMLSchema(etree.parse(xsd_path))
    if schema.validate(tree):
        return []
    return [f"line {e.line}: {e.message}" for e in schema.error_log]


def count_records(tree: etree._ElementTree, item_group_oid: str) -> int:
    """Independent XPath count used for reconciliation (does not reuse builder state)."""
    return int(tree.xpath(f"count(//odm:ItemGroupData[@ItemGroupOID='{item_group_oid}'])",
                          namespaces=XP_NS))
