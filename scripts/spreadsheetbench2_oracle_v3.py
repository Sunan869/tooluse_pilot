"""Evidence-tiered, three-axis scoring for real XLSX fault-injection studies.

No Excel recalculation is performed. Human annotations are advisory and must
match both the submitted file and the baseline before being applied. Keep this
module and private inputs outside the model's isolated workspace.
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from spreadsheetbench2_fault_factory import workbook, norm, sha
from spreadsheetbench2_financial_constraints import evaluate_business_constraints, classify_extra_business_rule

M = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"m": M}
GOLDEN_SHA = "4ea318ac60b4266a0b752d92d8174c7e526c99570d987764e20bcacfde68c151"


def additive_terms(formula):
    """Conservative equivalence: ref+ref and SUM(ref,ref), no expressions."""
    if not isinstance(formula, str) or not formula.startswith("="):
        return None
    expr = formula.lstrip("=+").replace("$", "").replace(" ", "").upper()
    if re.fullmatch(r"SUM\(([A-Z]{1,3}\d+,)+[A-Z]{1,3}\d+\)", expr):
        terms = expr[4:-1].split(",")
    elif re.fullmatch(r"[A-Z]{1,3}\d+(\+[A-Z]{1,3}\d+)+", expr):
        terms = expr.split("+")
    else:
        return None
    return collections.Counter(terms)


def golden_correspondence(proposed, golden):
    if norm(proposed) == norm(golden):
        return True
    a, b = additive_terms(proposed), additive_terms(golden)
    return a is not None and b is not None and a == b


def _normal_xml(element):
    """Canonicalize namespace/attribute order and ignorable indent whitespace."""
    return (element.tag, tuple(sorted(element.attrib.items())),
            (element.text or "").strip(),
            tuple(_normal_xml(child) for child in element))


def _relationship_set(z):
    result = {}
    for filename in z.namelist():
        if not filename.endswith(".rels"):
            continue
        root = ET.fromstring(z.read(filename))
        result[filename] = sorted((x.attrib.get("Type"), x.attrib.get("Target"),
                                   x.attrib.get("TargetMode", "Internal")) for x in root)
    return result


def package_snapshot(path):
    """Semantics-oriented subset of OOXML safety invariants, not full validation."""
    path = Path(path)
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        bad_member = z.testzip()
        if bad_member:
            raise ValueError(f"Damaged ZIP member: {bad_member}")
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        worksheet_names = [x.attrib.get("name") for x in wb.findall("m:sheets/m:sheet", NS)]
        sheet_states = {x.attrib.get("name"):x.attrib.get("state", "visible")
                        for x in wb.findall("m:sheets/m:sheet", NS)}
        workbook_protection = wb.find("m:workbookProtection", NS)
        defined = wb.find("m:definedNames", NS)
        defined_values = sorted((tuple(sorted(x.attrib.items())), (x.text or "").strip())
                                for x in defined) if defined is not None else []
        calc = wb.find("m:calcPr", NS)
        styles = ET.fromstring(z.read("xl/styles.xml"))
        style_counts = {el.tag.rsplit("}",1)[-1]:len(el) for el in styles}
        # Equivalent style tables need not have byte-identical serialization.
        style_semantics = _normal_xml(styles)
        cell_styles = {}
        special_formulas = {}
        merged = {}
        guarded_features = {}
        for name in names:
            if not re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name):
                continue
            root = ET.fromstring(z.read(name))
            cell_styles[name] = {c.attrib["r"]:c.attrib.get("s", "0")
                                 for c in root.findall(".//m:sheetData/m:row/m:c", NS)
                                 if c.attrib.get("s", "0") != "0"}
            special_formulas[name] = {}
            for c in root.findall(".//m:sheetData/m:row/m:c", NS):
                f = c.find("m:f", NS)
                if f is not None and (f.attrib.get("t") in ("dataTable", "array")
                                      or f.attrib.get("ref") is not None):
                    special_formulas[name][c.attrib["r"]] = (
                        tuple(sorted(f.attrib.items())), (f.text or "").strip())
            merged[name] = sorted(x.attrib.get("ref", "")
                                  for x in root.findall("m:mergeCells/m:mergeCell", NS))
            guarded_features[name] = {}
            for feature in ("dataValidations", "conditionalFormatting", "hyperlinks",
                            "sheetProtection", "autoFilter", "tableParts",
                            "drawing", "legacyDrawing"):
                guarded_features[name][feature] = tuple(
                    _normal_xml(e) for e in root.findall(f"m:{feature}", NS))
        parts = {name:hashlib.sha256(z.read(name)).hexdigest() for name in names}
        return {
            "parts":parts,"duplicate_parts":sorted(name for name,count in collections.Counter(names).items() if count>1),
            "sheets":worksheet_names,"sheet_states":sheet_states,
            "defined_names":defined_values,
            "workbook_protection":_normal_xml(workbook_protection) if workbook_protection is not None else None,
            "styles_counts":style_counts,"styles_semantics":style_semantics,
            "cell_styles":cell_styles,"special_formulas":special_formulas,
            "merged":merged,"features":guarded_features,
            "relationships":_relationship_set(z),
            "calculation_settings":dict(calc.attrib) if calc is not None else None,
        }


def compare_integrity(input_path, submission):
    before, after = package_snapshot(input_path), package_snapshot(submission)
    failures=[]
    for key,description in (
        ("sheets", "sheet_order_or_names_changed"),
        ("sheet_states", "sheet_visibility_changed"),
        ("defined_names", "defined_names_changed"),
        ("workbook_protection", "workbook_protection_changed"),
        ("styles_counts", "style_table_counts_changed"),
        ("styles_semantics", "style_definitions_changed"),
        ("cell_styles", "cell_style_assignment_changed"),
        ("special_formulas", "array_or_data_table_formula_changed"),
        ("merged", "merged_ranges_changed"),
        ("features", "worksheet_behavioral_features_changed"),
        ("relationships", "package_relationships_changed"),
    ):
        if before[key] != after[key]:
            failures.append(description)
    if set(before["parts"]) != set(after["parts"]):
        failures.append("package_parts_added_or_removed")
    if after["duplicate_parts"]:
        failures.append("duplicate_package_member_names")
    changed = sorted(k for k in set(before["parts"])&set(after["parts"])
                     if before["parts"][k] != after["parts"][k])
    warnings=[]
    if before["calculation_settings"] != after["calculation_settings"]:
        warnings.append("calculation_flags_changed_not_recalculated")
    if changed:
        warnings.append("zip_part_bytes_changed; semantic_safety_checks_are_not_full_OOXML_validation")
    return {
        "preservation_pass":not failures,
        "issues":failures,"warnings":warnings,
        "part_count_before":len(before["parts"]),
        "part_count_after":len(after["parts"]),
        "byte_changed_part_count":len(changed),
        "byte_changed_parts":changed[:25],
        "special_formula_count":sum(len(x) for x in after["special_formulas"].values()),
        "merged_range_count":sum(len(x) for x in after["merged"].values()),
        "xlsx_recalculation":"not_performed",
        "full_ooxml_validation":"not_performed",
    }


def load_evidence(path, input_path, baseline_path, submission):
    if path is None:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    hashes = data.get("file_hashes", {})
    expected = {"input":sha(Path(input_path)),"baseline":sha(Path(baseline_path)),
                "model_output":sha(Path(submission))}
    if any(hashes.get(k) != v for k,v in expected.items()):
        raise ValueError("Review evidence SHA-256 mismatch: refusing to apply annotations")
    return {(e["sheet"],e["cell"]):e for e in data.get("edits",[])}


def evaluate_v3(out, task, submission, golden=None, review_evidence=None):
    """Score known injected fixes, advisory extra edits, and package integrity.

    Pass remains the conservative minimal-edit compatibility metric. An open
    workbook audit requires expert review; advisory annotations never confer a
    full credit automatically.
    """
    root=Path(out)
    source_path=root/task["input_path"]
    baseline_path=root/"private"/"normalized_baseline.xlsx"
    submission=Path(submission)
    for path,key in ((source_path,"input_sha256"),(baseline_path,"baseline_sha256")):
        if sha(path)!=task[key]:
            raise ValueError(f"{key} mismatch; dataset may have been modified")
    injected=workbook(source_path)
    baseline=workbook(baseline_path)
    submitted=workbook(submission)
    golden_book=None
    if golden is not None:
        if sha(Path(golden))!=GOLDEN_SHA:
            raise ValueError("Golden SHA-256 mismatch; refusing source match")
        golden_book=workbook(golden)
    annotations=load_evidence(review_evidence,source_path,baseline_path,submission)
    faults={(x["sheet"],x["cell"]):x for x in task["faults"]}
    repaired=[];missed=[];alternate=[]
    for (sheet,addr),f in faults.items():
        actual=submitted["cells"].get(sheet,{}).get(addr,{}).get("formula")
        expected=baseline["cells"][sheet][addr]["formula"]
        key=f"{sheet}!{addr}"
        if norm(actual)==norm(expected):
            repaired.append(key)
        elif norm(actual)==norm(injected["cells"][sheet][addr]["formula"]):
            missed.append(key)
        else:
            alternate.append({"cell":key,"proposed":actual,"reference":expected,
                              "status":"alternative_unverified"})
    additional=[]
    for sheet in sorted(set(baseline["cells"])|set(submitted["cells"])):
        before=baseline["cells"].get(sheet,{})
        after=submitted["cells"].get(sheet,{})
        for addr in sorted(set(before)|set(after)):
            if (sheet,addr) in faults:
                continue
            a=before.get(addr,{})
            b=after.get(addr,{})
            if all(a.get(x)==b.get(x) for x in ("formula","value","type","formula_attrs")):
                continue
            evidence=annotations.get((sheet,addr))
            status="unreviewed"
            supporting=[]
            gold=(golden_book or {}).get("cells",{}).get(sheet,{}).get(addr,{})
            reference_changed=(gold.get("formula") is not None and
                               norm(gold["formula"])!=norm(a.get("formula")))
            if reference_changed and golden_correspondence(b.get("formula"),gold["formula"]):
                status="golden_correlated"
                supporting.append("submitted_formula_corresponds_to_official_golden")
            elif evidence and (norm(evidence.get("source"))==norm(a.get("formula")) and
                               norm(evidence.get("gpt"))==norm(b.get("formula"))):
                level=evidence.get("status")
                status={"structural_candidate":"plausible_unverified",
                        "needs_policy_review":"business_policy_pending",
                        "direct_golden":"review_claim_unverified_without_golden"}.get(level,"unreviewed")
                supporting.append("prior_audit_annotation_not_independent_validation")
            item={"cell":f"{sheet}!{addr}","status":status,
                  "before":a.get("formula") if a.get("formula") is not None else a.get("value"),
                  "after":b.get("formula") if b.get("formula") is not None else b.get("value"),
                  "evidence":supporting}
            witness=classify_extra_business_rule(sheet,addr,a.get("formula"),b.get("formula"))
            if witness is not None:
                item["synthetic_business_witness"]=witness
            additional.append(item)
    statuses=dict(sorted(collections.Counter(x["status"] for x in additional).items()))
    integrity=compare_integrity(source_path,submission)
    finance=evaluate_business_constraints(root,task,submission)
    supplemental=[{"cell":x["cell"],**x["synthetic_business_witness"]}
                  for x in additional if x.get("synthetic_business_witness")]
    supported=sum(bool(x["synthetic_business_witness_improved"]) for x in supplemental)
    total=len(faults)
    fixed=len(repaired)
    known_targets_complete=(fixed==total)
    strict=(known_targets_complete and not additional and integrity["preservation_pass"])
    return {
        "pass":strict,
        "grading_version":"three_axis_v3_plus_financial_witness_v1",
        "injected_faults":{"fixed":fixed,"total":total,"recall":fixed/total if total else None,
                           "exact_repaired":sorted(repaired),"not_repaired":sorted(missed),
                           "alternate_formula_unverified":alternate,
                           "complete":known_targets_complete},
        "extra_changes":{"count":len(additional),"evidence_tiers":statuses,
                         "items":additional,"requires_adjudication":bool(additional)},
        "artifact_integrity":integrity,
        "financial_constraints":finance,
        "supplemental_business_evidence":{
            "evaluated_extra_cells":len(supplemental),
            "improved_under_synthetic_witnesses":supported,
            "items":supplemental,
            "status":"advisory_not_independent_full_workbook_recalculation"},
        "verdict":{
            "minimal_repair_strict_pass":strict,
            "known_injection_status":"complete" if known_targets_complete else "incomplete",
            "open_audit_status":"requires_independent_business_review" if additional else "no_extra_edits_detected",
            "all_workbook_errors_verified":False,
        },
        "limitations":["No numeric Excel-compatible recalculation",
                       "Goldens and prior annotations are evidence, not automatic proof of business correctness",
                       "No full OOXML validation",
                       "Synthetic precedent probes do not establish actual workbook numerical outcomes"],
    }
