#!/usr/bin/env python3
"""R19 vs R21 structural differential over the already-decoded structures.

Ticket #21 (B5, Spec B).  Compares the two primary release lines on every
claim the committed scans already encode -- header, container-name table,
kind law, trailer, tail catalog, storage-block payloads, nested geometry
stores, identity block -- and tags each claim:

    identical   holds at the same rate on both lines
    differs     the measured behavior changes between the lines (the note
                says which field, what changed, since which version, and
                whether the driver is writer version or content)
    untested    the claim cannot be tested on these lines (note says why)

Rates are computed from the committed CSVs only (no corpus reads), so
every number is reproducible from the repository:

    python3 -I scripts/triage/version_differential.py            # R19,R20,R21
    python3 -I scripts/triage/version_differential.py --releases R19,R21
    python3 -I scripts/triage/version_differential.py --repo SSadayuki/B31CAADoc

--repo restricts the per-file claims to one repository (same-author
pairing; the only corpus repo holding both lines is SSadayuki/B31CAADoc).
Claims sourced from the sample claims CSVs (container-payloads,
geometry-payloads) have no per-file rows and keep their corpus-sample
rates in that mode.  --bytes sha16[,sha16...] prints the byte-level
spot-check structures (header, tail header, trailer, registration block,
identity block) for named files; that mode reads corpus files read-only.

Output: docs/evidence/data/differential-r19-r21.csv (one row per claim)
plus the summary to stdout.  Sample-scoped claims (payloads, geometry,
identity) carry the sample of their source scan, stated in `row_scope`.
"""
import argparse
import csv
import mmap
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs" / "evidence" / "data"
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT = DATA / "differential-r19-r21.csv"

CB_END = b"CB__END\x00"

# Row scopes over the per-file CSVs.
def scope_all(row):
    return True

def scope_cbend(row):
    return row["ends_cbend"] == "True"

def scope_main(row):
    return row["ff8_at_16_24"] == "True" and row["ends_cbend"] == "True"

def scope_table(row):
    return row["table_found"] == "True"

def scope_walk(row):
    return scope_main(row) and row["walk_ok"] == "True"

def scope_b_measured(row):
    return row.get("B_eq_prev_end", "") != ""

SCOPES = {
    "all": scope_all, "cbend": scope_cbend, "main": scope_main,
    "table files": scope_table, "walk-complete": scope_walk,
    "B-measured": scope_b_measured, "record rows": scope_all,
    "108-file sample": scope_all,
}


def release_of(version):
    """V5R19SP0HF0 -> R19; anything else -> the raw bucket text."""
    if version.startswith("V5R"):
        return "R" + version[3:5]
    return version or "unknown"


def is_true(v):
    return v == "True"


# ---------------------------------------------------------------------------
# Per-claim predicates.  Signature: pred(row, ctx, rel).  ctx carries the
# manifest lookups (repo/kind by sha256).
# ---------------------------------------------------------------------------

def kind_prediction(row):
    """Kind law K1: CATPrtCont => part, else CATProdCont/CATMechProdCont."""
    names = set((row["names"] or "").split(";")) if row["names"] else set()
    if row["table_found"] != "True":
        return "unknown"
    if "CATPrtCont" in names:
        return "part"
    if "CATProdCont" in names or "CATMechProdCont" in names:
        return "product"
    return "unknown"


def p_marker_matches(row, ctx, rel):
    tok = row["cnext_version"]
    return bool(tok) and ("R" + tok[3:5]) == rel


def p_cnt_low_byte(row, ctx, rel):
    return (int(row["cntB"]) & 0xFF) == int(row["cntA"]) + 1


def p_kind_law(row, ctx, rel):
    return kind_prediction(row) == ctx["kind"].get(row["sha256"])


# claims-CSV sources have no per-file rows; the predicate is unused.
def p_unused(row, ctx, rel):
    return True


CLAIMS = [
    # -- header (trailer-scan.csv covers all magic_ok files of a release)
    ("HDR-magic", "header", "magic 'V5_CFV2\\0' at 0-8 (scan scope = magic_ok files)",
     "trailer-scan.csv", "all", lambda r, c, rel: True,
     "identical", "scan scope is the magic-verified corpus; 100% by construction on both lines"),
    ("HDR-dword8-lt-size", "header", "dword8 (BE) < file size",
     "trailer-scan.csv", "all", lambda r, c, rel: int(r["dword8"]) < int(r["size_bytes"]),
     "identical", "tail-start pointer semantics unchanged"),
    ("HDR-d8-plus-d12", "header", "dword8 + dword12 == file size (law H1)",
     "trailer-scan.csv", "all", lambda r, c, rel: is_true(r["size_eq_d8_plus_d12"]),
     "identical", "649/649 R19, 355/355 R21"),
    ("HDR-dword12-sane", "header", "dword12 != 0xFFFFFFFF and != 0",
     "trailer-scan.csv", "all",
     lambda r, c, rel: int(r["dword12"]) != 0xFFFFFFFF and int(r["dword12"]) != 0,
     "identical", "no exceptions on either line"),
    ("HDR-ff8", "header", "eight 0xFF bytes at 16-24 (ff x 8 generation)",
     "trailer-scan.csv", "all", lambda r, c, rel: is_true(r["ff8_at_16_24"]),
     "identical", "100% on both lines; the dual-region header does not occur on R19/R21"),
    ("HDR-dual-region", "header", "dual-region header (dword16/dword20 instead of ff x 8)",
     "trailer-scan.csv", "all", lambda r, c, rel: not is_true(r["ff8_at_16_24"]),
     "differs", "0 on R19/R21 vs 146 corpus files (R15 2, R16 12, unknown 132; CAA repos) - an R15/R16/unknown generation, absent since R17"),
    ("HDR-zeros-24-28", "header", "bytes 24-28 zero (word24_be == 0)",
     "header-scan.csv", "all", lambda r, c, rel: r["word24_be"] == "0",
     "identical", "bytes 28-32 are not captured by any committed scan (untested everywhere)"),

    # -- version marker (header-scan.csv cnext_version column, unanchored token)
    ("VM-token-8k", "version marker", "V5RxxSPxxHFyy release token in the first 8 KB",
     "header-scan.csv", "all", lambda r, c, rel: bool(r["cnext_version"]),
     "identical", "97.7% R19 / 94.9% R21 in the 8 KB window; the rest are recovered by the 64 KB CNEXTINFOS-anchored fallback that defines detected_version"),
    ("VM-token-matches", "version marker", "the token's release matches the file's own line",
     "header-scan.csv", "all", p_marker_matches,
     "identical", "no cross-line mismatch; the SP/HF suffix varies per file (content)"),

    # -- container-name table (container-table.csv; record detail: -records-sample.csv)
    ("TB-found", "container table", "name table parses under the record model (incl. T3 constants, anchor, tail bytes)",
     "container-table.csv", "all", lambda r, c, rel: is_true(r["table_found"]),
     "identical", "649/649 R19, 355/355 R21; the 8 no-table corpus files are all unknown-version"),
    ("TB-f10-law", "container table", "f10 == names-area 8-byte slots + 1 (law T1, record sample)",
     "container-table-records-sample.csv", "record rows",
     lambda r, c, rel: int(r["f10"]) == int(r["names_area"]) // 8 + 1,
     "identical", "106/106 R19 and 64/64 R21 sample records"),
    ("TB-f3-vocabulary", "container table", "f3 (table id) is one of 0x00030001/0x00040001/0x00050001",
     "container-table-records-sample.csv", "record rows",
     lambda r, c, rel: r["f3_hex"] in ("0x00030001", "0x00040001", "0x00050001"),
     "identical", "the same three values on both lines"),
    ("TB-f2-weights", "container table", "f2 weight dominated by {11, 12, 13, 21}",
     "container-table-records-sample.csv", "record rows",
     lambda r, c, rel: int(r["f2"]) in (11, 12, 13, 21),
     "identical", "0.95 R19 / 0.94 R21 of sample records; rare larger values are content"),
    ("TB-dir-count", "container table", "directory count == name-record count (law L4)",
     "container-table.csv", "table files", lambda r, c, rel: is_true(r["count_match"]),
     "identical", "0.974 R19 (632/649) vs 0.989 R21 (351/355); exceptions are subset directories - the same failure mode on both lines"),
    ("TB-dir-join", "container table", "directory d6 multiset joins record f1 (law L5, subset form)",
     "container-table.csv", "table files", lambda r, c, rel: is_true(r["join_subset"]),
     "identical", "0.988 R19 / 0.983 R21"),
    ("TB-dir-cum", "container table", "d5 == 1 + cumulative f2 (law L6, bijection files)",
     "container-table.csv", "table files", lambda r, c, rel: is_true(r["cum_ok"]),
     "identical", "holds wherever L4 holds"),
    ("TB-dir-d7", "container table", "d7 == d6 (law L7)",
     "container-table.csv", "table files", lambda r, c, rel: is_true(r["d7_ok"]),
     "identical", "0.988 R19 / 0.983 R21"),
    ("TB-satellite", "container table", "satellite blobs (V5USERID rows) sit between records",
     "container-table.csv", "table files", lambda r, c, rel: int(r["satellite_gaps"]) > 0,
     "identical", "20.5% R19 / 24.5% R21 of table files carry >= 1 satellite gap"),
    ("TB-kind-law", "container table", "kind law K1: CATPrtCont <=> part, else product",
     "container-table.csv", "all", p_kind_law,
     "identical", "649/649 R19, 189/189 R20, 355/355 R21; the two CATMechProdCont+CATPrtCont parts (R20, R21) are still classified by CATPrtCont"),

    # -- container tree (container-tree-scan.csv): the documented negative
    ("TREE-resolve", "container tree", "records resolve parent_name to a same-file name1 (candidate assembly)",
     "container-tree-scan.csv", "all",
     lambda r, c, rel: r["n_parent_unresolved"] == "0" and is_true(r["table_found"]),
     "identical", "negative holds identically: 0 full resolutions; record-level resolution 9.4% R19 / 8.1% R20 / 9.1% R21"),

    # -- trailer (trailer-scan.csv, CB__END-ending files)
    ("TR-exists", "trailer", "file ends with CB__END\\0 (trailer present)",
     "trailer-scan.csv", "all", lambda r, c, rel: scope_cbend(r),
     "identical", "100% of R19/R21 files end with the trailer (no-trailer files are unknown-version only)"),
    ("TR-A-eq-1", "trailer", "trailer A == 1",
     "trailer-scan.csv", "cbend", lambda r, c, rel: is_true(r["A_is_1"]),
     "identical", "649/649 and 355/355"),
    ("TR-C-eq-D", "trailer", "trailer C == D (final region length, stored twice)",
     "trailer-scan.csv", "cbend", lambda r, c, rel: is_true(r["C_eq_D"]),
     "identical", "100% on both lines"),
    ("TR-E-eq-0", "trailer", "trailer E == 0",
     "trailer-scan.csv", "cbend", lambda r, c, rel: is_true(r["E_is_0"]),
     "identical", "the corpus's single E != 0 exception is an unknown-version dual file"),
    ("TR-G-eq-d12", "trailer", "trailer G == dword12 (tail length)",
     "trailer-scan.csv", "cbend", lambda r, c, rel: is_true(r["G_eq_dword12"]),
     "identical", "100% on both lines"),
    ("TR-B-lt-d8", "trailer", "trailer B < dword8 (registration block sits in the payload)",
     "trailer-scan.csv", "cbend", lambda r, c, rel: int(r["B"]) < int(r["dword8"]),
     "identical", "100% on both lines"),
    ("TR-registration", "trailer", "41-byte writer registration block byte-verifies at B",
     "trailer-scan.csv", "cbend", lambda r, c, rel: is_true(r["reg_code"]),
     "identical", "reg_code implies the full DASSAULT-SYSTEMES/CATIA/041803 chain; 100% on both lines"),
    ("TR-F-eq-0", "trailer", "trailer F == 0",
     "trailer-scan.csv", "cbend", lambda r, c, rel: r["F"] == "0",
     "differs", "constant 0 on R19+ (1004/1004 across R19/R20/R21/R23/R24-R32) vs F=1 on R15-R18 + unknown (177 files) and F=2 once (unknown); identical between the two primary lines"),
    ("TR-C-mode-e7", "trailer", "C == 0x000000e7 (the B1 mode value)",
     "trailer-scan.csv", "cbend", lambda r, c, rel: r["C"] == "231",
     "differs", "content variation, not a version change: 9.4% R19 vs 72.1% R21 corpus-wide, but same-repo B31CAADoc shows 70% (R19) vs 51% (R21) and povdoigt R19 is 0/559 - the corpus mix, not the writer version, sets the share"),
    ("TR-reg-tag-M", "trailer", "registration tag byte == 'M' (0x4d)",
     "trailer-scan.csv", "cbend", lambda r, c, rel: r["reg_tag"] == "M",
     "differs", "content variation: the corpus flips M-majority (R19 86%) to N-majority (R21 87%) but same-repo B31CAADoc is all-N on BOTH lines (87/87, 35/35) and R21 repos disagree (dolganin 30M/33N) - repo-dependent, not version-dependent"),

    # -- tail catalog (tail-scan.csv; main scope = ff x 8 + CB__END)
    ("TL-magic", "tail catalog", "CATIA_V5 CB0001 magic at dword8",
     "tail-scan.csv", "main", lambda r, c, rel: is_true(r["magic"]),
     "identical", "100% on both lines"),
    ("TL-header-constants", "tail catalog", "tail header: tag 0x4e, u16be 1000, u16be 64, u16be 12, zeros at +36..+64",
     "tail-scan.csv", "main",
     lambda r, c, rel: all(is_true(r[k]) for k in ("tag4e", "k1000", "origin64", "k12", "zeros36")),
     "identical", "every constant identical on R19/R21"),
    ("TL-cnt-law", "tail catalog", "cntB == cntA + 1 (u16 read)",
     "tail-scan.csv", "main", lambda r, c, rel: is_true(r["cnt_law"]),
     "differs", "R19 649/649 vs R21 340/355 (15 files) and R20 173/189 (16): on 33 files the cntB slot's HIGH byte is nonzero - all parts >= 18.6 MB; R19's corpus max is 8.9 MB, so R19 is untested at that size"),
    ("TL-cnt-low-byte", "tail catalog", "cntB low byte == cntA + 1",
     "tail-scan.csv", "main", p_cnt_low_byte,
     "identical", "holds on all 33 high-byte exceptions too: the count still lives in the low byte; the high byte's semantics are open (precision over B2's 'exceeds one byte')"),
    ("TL-e0-laws", "tail catalog", "entry 0: length == M + 87 and X0 == 94",
     "tail-scan.csv", "main", lambda r, c, rel: is_true(r["e0_X0_94"]),
     "identical", "100% on both lines; M's value distribution shifts (R19 reaches 146, R21 mostly 86/106) - content, driver open"),
    ("TL-e1-name", "tail catalog", "first catalog entry named CATIA1",
     "tail-scan.csv", "main", lambda r, c, rel: r["e1_name"] == "CATIA1",
     "identical", "98.5% R19 / 98.6% R21; the exceptions (first parsed entry = CATStorageProperty region) occur on both lines"),
    ("TL-e1-Y94", "tail catalog", "first catalog entry region length == 94",
     "tail-scan.csv", "main", lambda r, c, rel: is_true(r["e1_Y94"]),
     "identical", "100% on both lines"),
    ("TL-seq-law", "tail catalog", "entry seq runs 2, 3, ... in list order (W4)",
     "tail-scan.csv", "main", lambda r, c, rel: is_true(r["seq_law"]),
     "identical", "100% on both lines wherever entries parse"),
    ("TL-Y-laws", "tail catalog", "Y copies agree within and across entries (W2/W3)",
     "tail-scan.csv", "main", lambda r, c, rel: is_true(r["Y_laws"]),
     "identical", "100% on both lines wherever entries parse"),
    ("TL-walk-ok", "tail catalog", "primary catalog walk completes (decoder coverage, not a law)",
     "tail-scan.csv", "main", lambda r, c, rel: is_true(r["walk_ok"]),
     "differs", "decoder coverage: 0.764 R19 (496/649) vs 0.639 R21 (227/355); failures are the same families (flag/name stops) at content-shifted offsets; parts walk worse than products on both lines"),
    ("TL-trailer-xrec", "tail catalog", "trailer == final xrec: A=1, C==D, G == tail length",
     "tail-scan.csv", "cbend", lambda r, c, rel: is_true(r["trailer_xrec"]),
     "identical", "100% on both lines"),
    ("TL-endblock", "tail catalog", "81-byte end block: seq == cntB, space == 2, Y == C",
     "tail-scan.csv", "walk-complete", lambda r, c, rel: is_true(r["endblock"]),
     "identical", "496/496 R19, 227/227 R21 walk-complete files"),
    ("TL-accounting", "tail catalog", "tail length exactly determined by the entry list",
     "tail-scan.csv", "walk-complete", lambda r, c, rel: is_true(r["accounting_ok"]),
     "identical", "100% of walk-complete files on both lines"),
    ("TL-R1-min64", "tail regions", "min region start == 64 (R1)",
     "tail-scan.csv", "walk-complete", lambda r, c, rel: is_true(r["R1_min64"]),
     "identical", "100% on both lines"),
    ("TL-R2-max-d8", "tail regions", "max region end == dword8 (R2)",
     "tail-scan.csv", "walk-complete", lambda r, c, rel: is_true(r["R2_max_d8"]),
     "identical", "100% on both lines"),
    ("TL-tiling-full", "tail regions", "full tiling, no unclaimed bytes (R3a)",
     "tail-scan.csv", "walk-complete", lambda r, c, rel: is_true(r["tiling_full"]),
     "identical", "0.909 R19 (451/496) vs 0.789 R21 (179/227); residual gaps carry nested sub-catalog bytes on both lines (R3b <= 1 gap: 0.998 / 0.991)"),
    ("TL-B-is-registration", "tail regions", "trailer B is one of the registration-pattern occurrences",
     "tail-scan.csv", "cbend", lambda r, c, rel: is_true(r["B_is_registration"]),
     "identical", "100% on both lines; pattern multiplicity median 11 (R19) / 12 (R21)"),
    ("TL-B-eq-prev-end", "tail regions", "the previous named region ends exactly at B (R4)",
     "tail-scan.csv", "B-measured", lambda r, c, rel: is_true(r["B_eq_prev_end"]),
     "identical", "496/496 R19, 227/227 R21 (walk-complete)"),

    ("TL-sp1-implies", "tail regions", "space flag 1 implies a Cont_*/top-region name",
     "tail-scan.csv", "main", lambda r, c, rel: is_true(r["sp1_implies_name"]),
     "identical", "0.966 R19 / 0.980 R21 - candidate on both lines; the flag's meaning is open"),
    ("TL-sp1-converse", "tail regions", "Cont_* entries always carry space flag 1 (converse)",
     "tail-scan.csv", "main", lambda r, c, rel: is_true(r["cont_sp1"]),
     "identical", "0.897 R19 / 0.865 R21 - below the bar on both lines (candidate), same shape"),
    ("TB-contiguous", "container table", "records strictly contiguous (no satellite or open gaps)",
     "container-table.csv", "table files",
     lambda r, c, rel: int(r["open_gaps"]) == 0 and int(r["satellite_gaps"]) == 0,
     "identical", "0.787 R19 / 0.746 R21; gap structure (satellite blobs) identical in kind"),

    # -- storage-block payloads (sample-scoped: container-payloads-claims.csv)
    ("PL-C2-region-rule", "payload blocks", "region ends byte-verify at the claimed boundary kind",
     "container-payloads-claims.csv#C2", "114-file sample", p_unused,
     "identical", "1.000 on every sampled release including R19/R21"),
    ("PL-C1b-join", "payload blocks", "every non-identity block GUID joins a name-table record",
     "container-payloads-claims.csv#C1b", "114-file sample", p_unused,
     "identical", "1.000 R19 vs 0.969 R21 (3 residual blocks) - residuals are containers absent from partial tables (the B1 subset phenomenon), not a framing change"),
    ("PL-C3b-tag34", "payload blocks", "tag34 names terminate with 0x9f or a type-tag byte",
     "container-payloads-claims.csv#C3b", "114-file sample", p_unused,
     "identical", "1.000 R19 vs 0.991 R21 (4 residuals); R20 dips to 0.940 (30) - residuals are binary coincidences in stream data, not a framing variant"),
    ("PL-C4b-u16le", "payload blocks", "u16le share among u16le/u32le-framed ASCII rows",
     "container-payloads-claims.csv#C4b", "114-file sample", p_unused,
     "differs", "0.241 R19 vs 0.003 R21/R20 - driver unresolved (B3 open question 6): R19's sample files are small, R20/R21's are large parts; needs an equal-context comparison"),
    ("PL-C6-cardinality", "payload blocks", "exactly one CATProdCont record joined by exactly one block per file",
     "container-payloads-claims.csv#C6", "114-file sample", p_unused,
     "identical", "1.000 on both lines"),
    ("PL-C7-featcont", "payload blocks", "CATFeatCont: no record, no block, no literal outside the table",
     "container-payloads-claims.csv#C7", "114-file sample", p_unused,
     "identical", "1.000 on both lines (negative finding unchanged)"),

    # -- identity block (units-names-probe-files.csv, 108-file sample)
    ("ID-model", "identity block", "exactly one CATIA-named block with the 16-zero GUID slot; name2 walk parses",
     "units-names-probe-files.csv", "108-file sample",
     lambda r, c, rel: is_true(r["identity_model_ok"]),
     "identical", "1.000 on every sampled release"),
    ("ID-doc-name", "identity block", "identity block stores the save-time document name as name2",
     "units-names-probe-files.csv", "108-file sample",
     lambda r, c, rel: is_true(r["doc_name_present"]),
     "differs", "present on R15-R19 (R19 5/16) and ABSENT from R20+ (R20 0/12, R21 0/11, R23 0/11, R24 0/9): the writer stopped storing it between R19 and R20; byte examples in the note"),

    # -- geometry containers (geometry-payloads-claims.csv, 81-file scan)
    ("GE-V1-cgmgeom", "geometry", "exactly one CGMGeom block per part, none per product",
     "geometry-payloads-claims.csv#V1_one_cgmgeom_per_part", "81-file scan", p_unused,
     "identical", "1.000 on both lines (sample: 4 R19 parts, 5 R21 parts)"),
    ("GE-V2-cgrcont", "geometry", "CATCGRCont block present but region < 64 KiB",
     "geometry-payloads-claims.csv#V2_cgrcont_small", "81-file scan", p_unused,
     "identical", "1.000 on both lines"),
    ("GE-V3-nested", "geometry", "nested V5_CFV2 container in the CATStdCont region",
     "geometry-payloads-claims.csv#V3_stdcont_nested", "81-file scan", p_unused,
     "identical", "R19 4/4, R21 5/5 (R20 5/6) - the same store architecture"),
    ("GE-V4-stream-names", "geometry", "UTF-16 stream-name tokens in a payload region",
     "geometry-payloads-claims.csv#V4_surfacicreps", "81-file scan", p_unused,
     "identical", "R19 4/4, R21 4/5"),
    ("GE-V5-strip", "geometry", "strip-index records inside the CATStdCont region",
     "geometry-payloads-claims.csv#V5_strip_in_stdcont", "81-file scan", p_unused,
     "identical", "R19 4/4, R21 4/5 (small-part misses are content density)"),
    ("GE-V6-specificity", "geometry", "strip-index records absent from CGMGeom regions",
     "geometry-payloads-claims.csv#V6_strip_in_cgmgeom", "81-file scan", p_unused,
     "identical", "0 passes on every release (specificity holds)"),
    ("GE-V8-cgm-catalog", "geometry", "the CGM payload region is named by a tail-catalog region (delta law)",
     "geometry-payloads-claims.csv#V8_cgm_region_in_catalog", "deep sample", p_unused,
     "identical", "R19 1/1, R21 3/3 deep files"),

    # -- untested on the R19/R21 lines (rate cells empty; the note says why)
    ("UT-dual-dwords", "header", "semantics of dword16/dword20 in the dual-region header",
     "-", "all", p_unused,
     "untested", "no R19/R21 file carries a dual-region header (0/1004); the variant exists only on R15 (2), R16 (12) and unknown (132) files - B2's two dword20 hypotheses were tested there and failed"),
    ("UT-header-28-32", "header", "header bytes 28-32 are zero",
     "-", "all", p_unused,
     "untested", "no committed scan reads bytes 28-32 (header-scan.csv carries word24_be = bytes 24-28 only); untested on every line"),
    ("UT-F-nonzero", "trailer", "semantics of trailer F = 1 / 2",
     "-", "all", p_unused,
     "untested", "F is 0 on all 1193 R19/R20/R21 CB__END files; nonzero F occurs only on R15-R18 + unknown files, so its semantics cannot be probed on the primary lines"),
    ("UT-reg-tag-meaning", "trailer", "meaning of the registration tag byte M (0x4d) vs N (0x4e)",
     "-", "all", p_unused,
     "untested", "both values occur on both lines and the split is repo-dependent within one release (R21: dolganin 30M/33N, huanhuan233 15M/48N); no byte-level model distinguishes M from N files"),
    ("UT-cnt-high-byte", "tail catalog", "semantics of the cntB slot's high byte on large parts",
     "-", "all", p_unused,
     "untested", "the value is open everywhere; the 33 affected files are parts >= 18.6 MB and R19's corpus max is 8.9 MB, so an equal-size R19-vs-R21 comparison is impossible in this corpus"),
    ("UT-tail-var8", "tail catalog", "semantics of the 8 file-dependent tail-header bytes (+11..+19)",
     "-", "all", p_unused,
     "untested", "file-dependent on both lines with overlapping value sets (256-distinct-byte samples); no version-scoped model exists (B2 open question 1)"),
    ("UT-e0-M-driver", "tail catalog", "what sets M (the entry-0 length quantum, 86 + 20k)",
     "-", "all", p_unused,
     "untested", "M is file-dependent on both lines and the 86+20k law holds corpus-wide (e0_len == M+87, 100% both lines); its driver (name0 content/length) is open"),
    ("UT-reg-others", "tail regions", "what distinguishes the trailer's B-target registration block from the other identical-format occurrences",
     "-", "all", p_unused,
     "untested", "the 41-byte pattern occurs 3-22 (R19) / 3-20 (R21) times per file with no distinguishing bytes known (B2 open question)"),
    ("UT-tag-0x55", "tail catalog", "the tail-header tag 0x55",
     "-", "all", p_unused,
     "untested", "occurs only on the 8 no-trailer unknown-version files; absent from R19/R21 (tag is 0x4e on 100% of both lines)"),
    ("UT-osmx-cb0001", "payload blocks", "whether every OSMX / CB0001 region end is a real stream header",
     "-", "all", p_unused,
     "untested", "the region rule byte-verifies boundaries only (C2); B3 open question 2 - no version-scoped test exists"),
    ("UT-u32le-subformat", "payload blocks", "the u32le attribute-string sub-format inside stream regions",
     "-", "all", p_unused,
     "untested", "candidate framing only (C4/C4b); no per-version model to test - B3 open question 3"),
    ("UT-strip-semantics", "geometry", "strip-record primitive semantics (G1: triangles vs polylines, vertex pool)",
     "-", "all", p_unused,
     "untested", "the grammar is a byte-level fact on both lines; the semantics are inferred and need a controlled decode pass (B4 open question 2) - not version-scoped"),
]

CSV_FILES = {
    "trailer-scan.csv", "header-scan.csv", "container-table.csv",
    "container-table-records-sample.csv", "container-tree-scan.csv",
    "container-payloads-claims.csv", "geometry-payloads-claims.csv",
    "units-names-probe-files.csv", "tail-scan.csv",
}
CLAIMS_CSV_SOURCES = {"container-payloads-claims.csv",
                      "geometry-payloads-claims.csv"}


def split_source(source):
    """'file.csv#ClaimId' -> ('file.csv', 'ClaimId')."""
    base, _, cid = source.partition("#")
    return base, cid or None


def read_csv(path):
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def load_tables():
    """Read the scans; normalize file identity against the manifest.

    Some sample CSVs key files by a 16-hex sha prefix and header-scan.csv
    lacks detected_version; both are resolved here so every downstream
    lookup (release bucket, repo guard, kind) works uniformly.
    """
    man = [r for r in read_csv(MANIFEST) if r["magic_ok"] == "yes"]
    full_of = {}
    ver_of = {}
    repo_of = {}
    kind_of = {}
    for r in man:
        sha = r["sha256"]
        full_of[sha] = sha
        ver_of[sha] = release_of(r["detected_version"])
        repo_of[sha] = r["repo"]
        kind_of[sha] = r["kind"]
    tables = {}
    for name in CSV_FILES:
        rows = read_csv(DATA / name)
        for r in rows:
            sha = r.get("sha256", "")
            full = full_of.get(sha)
            if full is None and len(sha) < 64:
                full = next((s for s in full_of if s.startswith(sha)), None)
            if full is not None:
                r["sha256"] = full
            if not r.get("detected_version"):
                r["detected_version"] = ver_of.get(r.get("sha256", ""), "")
        tables[name] = rows
    return man, tables, {"repo": repo_of, "kind": kind_of}


def rate_for(rows, scope, pred, rel, ctx):
    """(n, passes) for one release bucket, or None when the bucket is empty."""
    sel = [r for r in rows
           if release_of(r.get("detected_version", "")) == rel
           and r.get("sha256", "") in ctx["repo"]
           and SCOPES[scope](r)]
    if not sel:
        return None
    return len(sel), sum(1 for r in sel if pred(r, ctx, rel))


def claims_csv_rate(rows, rel):
    """(n, passes) from a per-claim/per-release CSV row, or None."""
    for r in rows:
        if r["release"] == rel:
            n = int(r.get("observations") or r.get("files") or 0)
            return n, int(r.get("passes") or 0)
    return None


def fmt(v):
    return "-" if v is None else "%d/%d=%.3f" % (v[1], v[0], v[1] / v[0])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--releases", default="R19,R20,R21",
                    help="comma-separated release buckets (default R19,R20,R21)")
    ap.add_argument("--repo", default="",
                    help="restrict per-file claims to one repository (pairing mode)")
    ap.add_argument("--bytes", default="",
                    help="comma-separated 16-hex sha prefixes: print the "
                         "spot-check structures for those files")
    ap.add_argument("--no-write", action="store_true",
                    help="do not rewrite differential-r19-r21.csv")
    args = ap.parse_args()
    releases = [r.strip() for r in args.releases.split(",") if r.strip()]

    if args.bytes:
        return dump_bytes([s.strip() for s in args.bytes.split(",") if s.strip()])

    man, tables, ctx = load_tables()
    if args.repo:
        keep = {r["sha256"] for r in man if r["repo"] == args.repo}
        ctx["repo"] = {s: args.repo for s in keep}

    out = None
    writer = None
    if not args.no_write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        out = OUT.open("w", newline="")
        writer = csv.writer(out)
        writer.writerow(["claim_id", "structure", "statement", "source",
                         "row_scope", "verdict", "note"]
                        + [c for rel in releases
                           for c in (f"{rel}_n", f"{rel}_pass", f"{rel}_rate")])

    print("claims: %d  releases: %s%s" % (
        len(CLAIMS), ",".join(releases),
        "  repo=%s (sample-CSV claims keep corpus rates)" % args.repo
        if args.repo else ""))
    for cid, struct, stmt, source, scope, pred, verdict, note in CLAIMS:
        base, src_claim = split_source(source)
        if verdict == "untested":
            vals = {rel: None for rel in releases}
        elif base in CLAIMS_CSV_SOURCES:
            rows = [r for r in tables[base]
                    if src_claim is None or r["claim"] == src_claim]
            vals = {rel: claims_csv_rate(rows, rel) for rel in releases}
        else:
            vals = {rel: rate_for(tables[source], scope, pred, rel, ctx)
                    for rel in releases}
        if writer:
            cells = []
            for rel in releases:
                v = vals[rel]
                cells += [v[0], v[1], "%.3f" % (v[1] / v[0])] if v else ["", "", ""]
            writer.writerow([cid, struct, stmt, source, scope, verdict, note]
                            + cells)
        print("  %-22s %-16s %-9s %s" % (
            cid, struct, verdict,
            "  ".join("%s %s" % (rel, fmt(vals[rel])) for rel in releases)))

    if out:
        out.close()
        print("wrote", OUT)
    return 0


def dump_bytes(sha16s):
    """Print the spot-check structures for named corpus files (read-only)."""
    man = [r for r in read_csv(MANIFEST) if r["magic_ok"] == "yes"]
    for s in sha16s:
        r = next((m for m in man if m["sha256"].startswith(s)), None)
        if r is None:
            print("unknown sha prefix:", s)
            return 1
        with (ROOT / r["local_path"]).open("rb") as fh:
            data = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        size = int(r["size_bytes"])
        d8 = int.from_bytes(data[8:12], "big")
        d12 = int.from_bytes(data[12:16], "big")
        print("=" * 96)
        print("%s %s %s %s size=%d %s" % (s, r["detected_version"], r["kind"],
                                          r["repo"], size, r["path"][-56:]))
        print("header[0:32]:", data[:32].hex(" "))
        print("  dword8=%d dword12=%d ff8=%s bytes24_32=%s" % (
            d8, d12, data[16:24] == b"\xff" * 8, data[24:32].hex()))
        tail = data[d8:]
        print("tail[0:36]:", tail[:36].hex(" "))
        print("  cntA=%d cntB=%d var8=%s" % (
            int.from_bytes(tail[24:26], "little"),
            int.from_bytes(tail[26:28], "little"), tail[28:36].hex()))
        tb = data[-36:]
        print("trailer[-36]:", tb.hex(" "))
        print("  A=%d B=%d C=%d D=%d E=%d F=%d G=%d ends=%r" % (
            int.from_bytes(tb[0:4], "big"), int.from_bytes(tb[4:8], "big"),
            int.from_bytes(tb[8:12], "big"), int.from_bytes(tb[12:16], "big"),
            int.from_bytes(tb[16:20], "big"), int.from_bytes(tb[20:24], "big"),
            int.from_bytes(tb[24:28], "big"), tb[28:] == CB_END))
        b = int.from_bytes(tb[4:8], "big")
        print("registration@B:", data[b:b + 41].hex(" "))
        # identity block: the CATStorageProperty block whose name1 is CATIA
        for m in re.finditer(rb"\x34\x12CATStorageProperty", data):
            seg = data[m.start():m.start() + 300]
            head = re.match(rb"\x34\x12CATStorageProperty"
                            rb"\x80\x01\x00\x00\x00\x00\x22", seg)
            if not head:
                continue
            uni = seg.find(b"CATUnicodeString", head.end() + 4)
            if uni < 0:
                continue
            q = uni + len(b"CATUnicodeString")
            names = []
            for _ in range(2):
                nm = re.match(rb"\xa0\x02\x00\x00\x00\x00\x34(.)", seg[q:])
                if not nm:
                    break
                ln = nm.group(1)[0]
                names.append(seg[q + 8:q + 8 + ln])
                q += 8 + ln + 1
            if names and names[0] == b"CATIA":
                print("identity block@%d: name1=%r name2=%r" % (
                    m.start(), names[0], names[1] if len(names) > 1 else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
