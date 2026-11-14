//! The schema-v1 inspect document — the L1 slice's output document
//! (``catpart-inspect`` stdout; schema ``src/catpart/schema/v1.json``),
//! shared by the native CLI seam (``bin/fidelity-cli.rs``, spec §2.4)
//! and the WASM boundary (``wasm_boundary.rs``, spec §2.3) so the field
//! declaration order is single-sourced. Spec:
//! ``docs/specs/phase5-viewer-spec.md`` — sections cited below are its
//! sections, the way Python docstrings cite evidence notes.
//!
//! Field declaration order = the Python dict construction order of
//! ``build_inspect_report`` (§2.1: even byte JSON equality stays
//! reachable, though Fidelity compares parsed documents, §3.2).
//!
//! The inspect seam's failure surface is the two documented file-level
//! refusals of ``build_inspect_report`` (its docstring; the twins'
//! raise sites): the short-buffer :class:`ValueError` and path-level
//! :class:`OSError`. The Python side's own classification for every one
//! of them is the fitness class ``crash``
//! (``src/catpart/fitness/runner.py::_classify_file``: "``crash``
//! covers every exception raised while producing the output"; the A2
//! fixture table pins the same mapping — ``short-file`` → the
//! ``crash`` class). The refusal carries exactly that class; the
//! ``detail`` prose is never compared byte-wise (§3.2) and keeps the
//! two refusal modes distinguishable for humans.
//!
//! This file performs no arithmetic — assembly and serialization shapes
//! only, like the CLI seam it feeds (the V0 lint policy, ``lib.rs``: no
//! ``suboptimal_flops`` allow here).

use serde::Serialize;

use crate::containers::{ContainerRecord, detect_kind, parse_container_table};
use crate::header::{HEADER_SIZE, HeaderInfo, parse_header};
use crate::identity::parse_document_name;
use crate::trailer::{TrailerInfo, parse_trailer};
use crate::version::detect_version;

/// The schema version of the document the inspect seams emit (twin:
/// ``catpart.cli.SCHEMA_VERSION``).
pub const SCHEMA_VERSION: u32 = 1;

/// The inspect seam's failure class: the Python side's own
/// classification for every L1-reachable refusal (the module header).
pub const INSPECT_CRASH: &str = "crash";

/// A classified inspect refusal — the L1 shape of the classified-error
/// seam (§3.2 compares the ``error_class`` string; the ``detail`` is
/// human prose citing the violated claim, non-empty, never compared
/// byte-wise).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InspectRefusal {
    /// The machine-readable class (the inspect seam's: ``crash``).
    pub error_class: &'static str,
    /// The human explanation; non-empty, cites the violated claim.
    pub detail: String,
}

/// The schema-v1 inspect document (``catpart-inspect`` stdout; schema
/// ``src/catpart/schema/v1.json``). Field declaration order = the
/// Python dict construction order of ``build_inspect_report`` (§2.1).
#[derive(Debug, Serialize)]
pub struct InspectDocument {
    /// The schema version (1).
    pub schema_version: u32,
    /// The 8-byte magic, lossy-decoded ASCII (twin: ``latin-1``-safe).
    pub magic: String,
    /// Header dword8 (bytes 8-12, big-endian).
    pub header_dword: u32,
    /// Header dword12 (bytes 12-16, big-endian; law H1).
    pub header_dword12: u32,
    /// The eight ``0xFF`` bytes at 16-24 (or the dual-region absence).
    pub ff8_at_16_24: bool,
    /// Header dword16 (the dual-region generation only).
    pub header_dword16: Option<u32>,
    /// Header dword20 (the dual-region generation only).
    pub header_dword20: Option<u32>,
    /// The file size in bytes.
    pub file_size: u64,
    /// The CNEXTINFOS-detected version string.
    pub detected_version: String,
    /// ``part`` / ``product`` (the kind law, K1).
    pub kind: &'static str,
    /// The save-time document name (C3), when the identity block is
    /// present and parses.
    pub document_name: Option<String>,
    /// The container-name table records (B1).
    pub containers: Vec<ContainerRecord>,
    /// The trailer (A..G dwords + registration), when it validates.
    pub trailer: Option<TrailerInfo>,
}

/// The twin of ``catpart.cli.build_inspect_report`` over an in-memory
/// buffer: the short-buffer refusal, then the whole-buffer decode into
/// the schema-v1 document. The native CLI passes the bytes it read from
/// the path (its path-level refusals stay there — the OSError arm is
/// not reachable for a buffer); the WASM boundary passes the dropped
/// file's bytes, where this is the entire refusal surface.
pub fn build_inspect_document(data: &[u8]) -> Result<InspectDocument, InspectRefusal> {
    let file_size = data.len() as u64;
    if file_size < HEADER_SIZE as u64 {
        // The twin's ValueError prose (``build_inspect_report``).
        return Err(InspectRefusal {
            error_class: INSPECT_CRASH,
            detail: format!(
                "not a CATIA V5 container: header needs {HEADER_SIZE} bytes, got {file_size}"
            ),
        });
    }
    let HeaderInfo {
        magic,
        header_dword,
        header_dword12,
        ff8_at_16_24,
        header_dword16,
        header_dword20,
    } = match parse_header(&data[..HEADER_SIZE]) {
        Ok(info) => info,
        Err(err) => {
            return Err(InspectRefusal {
                error_class: INSPECT_CRASH,
                detail: err.to_string(),
            });
        }
    };
    let records = parse_container_table(data);
    Ok(InspectDocument {
        schema_version: SCHEMA_VERSION,
        magic,
        header_dword,
        header_dword12,
        ff8_at_16_24,
        header_dword16,
        header_dword20,
        file_size,
        detected_version: detect_version(data),
        kind: detect_kind(&records),
        document_name: parse_document_name(data),
        containers: records,
        trailer: parse_trailer(data),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The twin's ValueError prose, pinned: class crash, non-empty
    /// detail citing the violated claim (the header minimum).
    #[test]
    fn short_buffer_refuses_crash() {
        let refusal = build_inspect_document(&[0u8; 16]).unwrap_err();
        assert_eq!(refusal.error_class, "crash");
        assert_eq!(
            refusal.detail,
            "not a CATIA V5 container: header needs 32 bytes, got 16"
        );
    }

    /// The document's field declaration order compiles from the
    /// struct's declaration order — pinned by construction here; the
    /// fixture-mode harness compares the Python dict order per file.
    #[test]
    fn schema_version_is_one() {
        assert_eq!(SCHEMA_VERSION, 1);
    }
}
