//! Container-name table record parsing (schema v1) — the port of the
//! Python reference module ``catpart.containers``
//! (``src/catpart/containers.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md`` (B1 records, kind law).
//!
//! The twin's docstring carries the B1 record layout (all multi-byte
//! fields little-endian), the anchor-scan procedure over the
//! evidence-validated first 2 MB window, and the kind law; this port
//! cites, never restates. The behavior is mirrored 1:1 including the
//! fail-closed arm: an anchor position failing any record-model element
//! is skipped, and a file without a table yields an empty record list.
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-07-container-table-and-trailer.md``
//!   ("B1" — the fixed-layout record, the anchor scan, laws T1-T3,
//!   D1-D3)
//! - ``docs/evidence/2026-11-07-container-kind-law.md`` (the kind law:
//!   ``CATPrtCont`` / ``CATProdCont`` / ``CATMechProdCont``)
//!
//! Numeric contract (spec §2.2 point 3): decode module — the
//! ``suboptimal_flops`` allow below is the pinned carve-out (mul_add
//! changes rounding and flips exact-equality decisions); see the
//! crate docs in ``lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]

use serde::Serialize;

/// Evidence-validated scan window (twin:
/// :data:`catpart.containers.SCAN_WINDOW` — B1: "the table scan reads
/// only the first 2 MB of each file").
pub const SCAN_WINDOW: usize = 2 * 1024 * 1024;

/// Record field f9, bytes ``02 00 81 20`` little-endian (twin:
/// :data:`catpart.containers.ANCHOR`).
pub const ANCHOR: u32 = 0x2081_0002;
/// Record field f5 constant (twin: :data:`catpart.containers.F5_CONST`).
pub const F5_CONST: u32 = 0x006C_0001;
/// Record field f3's exactly-three-values corpus-wide vocabulary (twin:
/// :data:`catpart.containers.TABLE_IDS`).
pub const TABLE_IDS: [u32; 3] = [0x0003_0001, 0x0004_0001, 0x0005_0001];
/// The constant 8-byte record tail (twin:
/// :data:`catpart.containers.RECORD_TAIL`).
const RECORD_TAIL: [u8; 8] = [0x03, 0x00, 0xf7, 0x00, 0x03, 0x00, 0x00, 0x00];

/// Kind-law container names (twin:
/// :data:`catpart.containers.PART_CONTAINER` /
/// ``PRODUCT_CONTAINERS``; docs/evidence/2026-11-07-container-kind-law.md).
pub const PART_CONTAINER: &str = "CATPrtCont";
pub const PRODUCT_CONTAINERS: [&str; 2] = ["CATProdCont", "CATMechProdCont"];

/// Kind-law outcomes (twin: ``KIND_PART`` / ``KIND_PRODUCT`` /
/// ``KIND_UNKNOWN``).
pub const KIND_PART: &str = "part";
pub const KIND_PRODUCT: &str = "product";
pub const KIND_UNKNOWN: &str = "unknown";

/// One validated container-name table record (B1 layout) — the twin's
/// :class:`catpart.containers.ContainerRecord` dataclass. Field
/// declaration order = the twin's ``to_json`` dict construction order
/// (the JSON contract rides the same seam, spec §2.1).
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ContainerRecord {
    /// The container's own name (record field name1).
    pub name: String,
    /// The record's parent/base name (record field name2).
    pub parent_name: String,
    /// Record field f3 at S+8 (little-endian).
    pub table_id: u32,
    /// Record field idx at S+12 (little-endian), 1-based.
    pub index: u32,
    /// Record field f1 at S+0 (little-endian); evidence-note
    /// ``stream_id``.
    pub stream_id: u32,
    /// Record field f2 at S+4 (little-endian); evidence-note ``weight``.
    pub weight: u32,
    /// The record's 16-byte GUID, lowercase hex.
    pub guid: String,
}

/// The twin's :func:`catpart.containers._ceil8` — ``((n + 7) // 8) * 8``,
/// i.e. round ``n`` up to the next multiple of 8. Written as
/// ``n.div_ceil(8) * 8`` for the pinned clippy gate (``-D warnings``
/// allows no suppression beyond the §2.2 decode carve-out): the lint
/// reads ``((n + 7) / 8) * 8`` as a manual ceil-division of ``n``, and
/// ``n.div_ceil(8)`` is exactly that for every unsigned input —
/// integer arithmetic, no float, so the §2.2 operation-order contract
/// (a float-decision rule) is untouched. (V1 note, 2026-11-13: the
/// first transcription mistakenly applied ``div_ceil`` to ``n + 7``
/// — ``(n + 7).div_ceil(8) * 8`` — which over-rounds by one slot
/// whenever ``n`` is not 8-aligned; the fixture-mode harness caught it
/// on the first run, exactly its job. The unit tests below pin the
/// twin's literal values so this cannot regress silently.)
fn ceil8(n: usize) -> usize {
    n.div_ceil(8) * 8
}

/// ``buf.find(needle, from)`` — the first occurrence of ``needle`` at
/// or after ``from`` inside ``haystack``, or ``None`` (the twin scans
/// with :meth:`bytes.find`).
fn find_from(haystack: &[u8], needle: &[u8], from: usize) -> Option<usize> {
    if needle.is_empty() {
        return Some(from.min(haystack.len()));
    }
    if from >= haystack.len() {
        return None;
    }
    let last = haystack.len().checked_sub(needle.len())?;
    let mut i = from;
    while i <= last {
        if haystack[i] == needle[0] && &haystack[i..i + needle.len()] == needle {
            return Some(i);
        }
        i += 1;
    }
    None
}

/// Python :meth:`str.isprintable` on an ASCII-decoded string: the
/// printable ASCII range is exactly ``0x20..=0x7E`` (space included;
/// the names decode as ASCII before the check, so no other code point
/// can appear).
fn ascii_printable(bytes: &[u8]) -> bool {
    bytes.iter().all(|&b| (0x20..=0x7e).contains(&b))
}

fn le32(buf: &[u8], at: usize) -> u32 {
    u32::from_le_bytes([buf[at], buf[at + 1], buf[at + 2], buf[at + 3]])
}

/// Parse and validate one container-name record at offset ``s`` (twin:
/// :func:`catpart.containers._parse_record`).
///
/// Returns ``(record, end_offset)`` — the end offset is where law T2
/// places the next record — or ``None`` when any layout element of the
/// model is violated (bounds, T3 constants, f3 table id, names, T1
/// padding/tail): the anchor position is then simply not a record.
fn parse_record(buf: &[u8], s: usize) -> Option<(ContainerRecord, usize)> {
    if s + 40 > buf.len() {
        return None;
    }
    let f1 = le32(buf, s);
    let f2 = le32(buf, s + 4);
    let f3 = le32(buf, s + 8);
    let idx = le32(buf, s + 12);
    let f5 = le32(buf, s + 16);
    let f6 = le32(buf, s + 20);
    let f8 = le32(buf, s + 28);
    let f9 = le32(buf, s + 32);
    let f10 = le32(buf, s + 36);
    if !(f5 == F5_CONST && f6 == 2 && f8 == 0 && f9 == ANCHOR) {
        return None;
    }
    if !TABLE_IDS.contains(&f3) {
        return None;
    }
    // names: two printable ASCII NUL-terminated strings starting at S+40
    let p = s + 40;
    let n1 = find_from(buf, b"\x00", p)?;
    if n1 == p {
        return None;
    }
    let n2 = find_from(buf, b"\x00", n1 + 1)?;
    if n2 == n1 + 1 {
        return None;
    }
    if n2 - p > 256 {
        return None;
    }
    let name1_bytes = &buf[p..n1];
    let name2_bytes = &buf[n1 + 1..n2];
    // ``decode("ascii")``: any byte >= 0x80 fails the twin's decode.
    if !name1_bytes.iter().all(|&b| b < 0x80) || !name2_bytes.iter().all(|&b| b < 0x80) {
        return None;
    }
    if !(ascii_printable(name1_bytes) && ascii_printable(name2_bytes)) {
        return None;
    }
    let name1 = String::from_utf8(name1_bytes.to_vec()).ok()?;
    let name2 = String::from_utf8(name2_bytes.to_vec()).ok()?;
    let total = (n2 + 1) - p;
    let area = ceil8(total);
    let end_names = p + area;
    if end_names + 8 + 16 > buf.len() {
        return None;
    }
    if buf[n2 + 1..end_names].iter().any(|&b| b != 0) {
        return None; // law T1: padding bytes verified zero
    }
    if buf[end_names..end_names + 8] != RECORD_TAIL {
        return None;
    }
    if f10 != (area / 8 + 1) as u32 {
        return None; // law T1
    }
    let guid_bytes = &buf[end_names + 8..end_names + 24];
    let guid: String = guid_bytes.iter().map(|b| format!("{b:02x}")).collect();
    Some((
        ContainerRecord {
            name: name1,
            parent_name: name2,
            table_id: f3,
            index: idx,
            stream_id: f1,
            weight: f2,
            guid,
        },
        end_names + 24,
    ))
}

/// Return the validated table records of ``data``, in file order (twin:
/// :func:`catpart.containers.parse_container_table`).
///
/// ``data`` is the whole-file buffer; the scan covers the
/// evidence-validated first [`SCAN_WINDOW`] bytes, starting after the
/// 32-byte header. Anchor positions that fail the record model are
/// skipped (0 such positions exist corpus-wide on the 1810 with-table
/// files); files without a table yield an empty list (8 corpus files).
pub fn parse_container_table(data: &[u8]) -> Vec<ContainerRecord> {
    let buf = &data[..data.len().min(SCAN_WINDOW)];
    let anchor_bytes = ANCHOR.to_le_bytes();
    let mut records = Vec::new();
    let mut pos = find_from(buf, &anchor_bytes, 0);
    while let Some(at) = pos {
        if at < 32 {
            // Inside the header no record can start; skip the anchor.
            pos = find_from(buf, &anchor_bytes, at + 1);
            continue;
        }
        match parse_record(buf, at - 32) {
            Some((record, end)) => {
                records.push(record);
                pos = find_from(buf, &anchor_bytes, end);
            }
            None => {
                pos = find_from(buf, &anchor_bytes, at + 1);
            }
        }
    }
    records
}

/// Return the file kind from the table records (kind law K1; twin:
/// :func:`catpart.containers.detect_kind`).
///
/// Evidence: docs/evidence/2026-11-07-container-kind-law.md —
/// ``CATPrtCont`` among the record names means a part (1436/1436
/// with-table corpus parts), ``CATProdCont``/``CATMechProdCont`` without
/// ``CATPrtCont`` a product (374/374 with-table products; 2 parts carry
/// the mechanical-product container next to ``CATPrtCont``, so the part
/// name decides), ``unknown`` with no table (8 corpus files).
pub fn detect_kind(records: &[ContainerRecord]) -> &'static str {
    let mut saw_product_container = false;
    for record in records {
        if record.name == PART_CONTAINER {
            return KIND_PART;
        }
        if PRODUCT_CONTAINERS.contains(&record.name.as_str()) {
            saw_product_container = true;
        }
    }
    if saw_product_container {
        return KIND_PRODUCT;
    }
    KIND_UNKNOWN
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A B1-valid record assembled from the layout the twin documents;
    /// mirrors ``tests/fixtures_gen.py::container_record``'s shape.
    fn valid_record_bytes(name: &str, parent: &str, guid: [u8; 16]) -> Vec<u8> {
        let names = format!("{name}\x00{parent}\x00");
        let total = names.len();
        // The twin's literal law values, hard-coded from the name pair:
        // area = ceil8(total), f10 = area/8 + 1. NOT computed via
        // [ceil8] — a wrong round-up must break this test, not
        // self-consistently pass it (the V1 ceil8 regression).
        let area = match total % 8 {
            0 => total,
            _ => total + (8 - total % 8),
        };
        let mut rec = Vec::new();
        rec.extend_from_slice(&1u32.to_le_bytes()); // f1
        rec.extend_from_slice(&11u32.to_le_bytes()); // f2
        rec.extend_from_slice(&0x0003_0001u32.to_le_bytes()); // f3
        rec.extend_from_slice(&1u32.to_le_bytes()); // idx
        rec.extend_from_slice(&F5_CONST.to_le_bytes()); // f5
        rec.extend_from_slice(&2u32.to_le_bytes()); // f6
        rec.extend_from_slice(&0u32.to_le_bytes()); // f7 (S+24, unchecked)
        rec.extend_from_slice(&0u32.to_le_bytes()); // f8
        rec.extend_from_slice(&ANCHOR.to_le_bytes()); // f9
        rec.extend_from_slice(&((area / 8 + 1) as u32).to_le_bytes()); // f10
        rec.extend_from_slice(names.as_bytes());
        rec.extend(std::iter::repeat_n(0u8, area - total));
        rec.extend_from_slice(&RECORD_TAIL);
        rec.extend_from_slice(&guid);
        rec
    }

    #[test]
    fn ceil8_matches_the_twin_law_values() {
        // ((n + 7) // 8) * 8, pinned literally: 22 -> 24 (the
        // CATPrtCont/CATProdCont name area), not 32.
        assert_eq!(ceil8(22), 24);
        assert_eq!(ceil8(1), 8);
        assert_eq!(ceil8(8), 8);
        assert_eq!(ceil8(9), 16);
        assert_eq!(ceil8(0), 0);
    }

    #[test]
    fn parses_valid_record_and_reports_fields() {
        let mut guid = [0u8; 16];
        guid[15] = 0xae;
        let mut buf = vec![0u8; 32];
        buf.extend_from_slice(&valid_record_bytes("CATPrtCont", "CATProdCont", guid));
        let records = parse_container_table(&buf);
        assert_eq!(records.len(), 1);
        let rec = &records[0];
        assert_eq!(rec.name, "CATPrtCont");
        assert_eq!(rec.parent_name, "CATProdCont");
        assert_eq!(rec.table_id, 0x0003_0001);
        assert_eq!(rec.index, 1);
        assert_eq!(rec.stream_id, 1);
        assert_eq!(rec.weight, 11);
        assert_eq!(rec.guid, "000000000000000000000000000000ae");
        assert_eq!(detect_kind(&records), KIND_PART);
    }

    #[test]
    fn kind_law_part_name_decides_over_product_container() {
        let guid = [0u8; 16];
        let mut buf = vec![0u8; 32];
        buf.extend_from_slice(&valid_record_bytes("CATMechProdCont", "CATContainer", guid));
        buf.extend_from_slice(&valid_record_bytes("CATPrtCont", "CATFeatCont", guid));
        assert_eq!(detect_kind(&parse_container_table(&buf)), KIND_PART);
    }

    #[test]
    fn product_table_without_part_container() {
        let guid = [0u8; 16];
        let mut buf = vec![0u8; 32];
        buf.extend_from_slice(&valid_record_bytes("CATProdCont", "CATContainer", guid));
        assert_eq!(detect_kind(&parse_container_table(&buf)), KIND_PRODUCT);
    }

    #[test]
    fn no_table_yields_empty_and_unknown_kind() {
        let buf = [0u8; 128];
        assert!(parse_container_table(&buf).is_empty());
        assert_eq!(detect_kind(&[]), KIND_UNKNOWN);
    }

    #[test]
    fn fails_closed_on_nonzero_padding() {
        let guid = [0u8; 16];
        let mut rec = valid_record_bytes("CATPrtCont", "CATProdCont", guid);
        // Pad with 0x01 instead of the required zero padding (law T1).
        let names_len = b"CATPrtCont\x00CATProdCont\x00".len();
        rec[40 + names_len] = 0x01;
        let mut buf = vec![0u8; 32];
        buf.extend_from_slice(&rec);
        assert!(parse_container_table(&buf).is_empty());
    }

    #[test]
    fn skips_anchor_positions_failing_the_model() {
        // A bare anchor dword at a valid position with no record model
        // behind it: skipped, empty result.
        let mut buf = vec![0u8; 32];
        buf.extend_from_slice(&ANCHOR.to_le_bytes());
        buf.extend(std::iter::repeat_n(0u8, 64));
        assert!(parse_container_table(&buf).is_empty());
    }

    #[test]
    fn scan_window_is_first_2mb_only() {
        // An anchor-based record beyond the 2 MB window is not scanned.
        let guid = [0u8; 16];
        let mut buf = vec![0u8; 32];
        buf.extend(std::iter::repeat_n(0u8, SCAN_WINDOW));
        buf.extend_from_slice(&valid_record_bytes("CATPrtCont", "CATProdCont", guid));
        assert!(parse_container_table(&buf).is_empty());
    }
}
