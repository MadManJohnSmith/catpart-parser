//! The native CLI seam (spec §2.4 of ``docs/specs/phase5-viewer-spec.md``):
//! ``fidelity-cli`` — the harness drives the port through this binary
//! exactly the way it drives the Python console scripts, so a mismatch
//! is attributable to the decoder, never to harness plumbing.
//!
//! V1 (ticket #40): **inspect mode only** — the L1 slice's schema-v1
//! document, the I/O contract of ``catpart-inspect``
//! (``src/catpart/cli.py::main_inspect``): one file-path argument, the
//! summary JSON on stdout (field declaration order = the Python dict
//! construction order of ``build_inspect_report`` — spec §2.1), and a
//! classified error as one JSON line on stderr with exit 1. Usage
//! errors exit 2 (argparse convention). Export mode is V2 (#41).
//!
//! # The L1 error-class vocabulary (one class: ``crash``)
//!
//! The inspect seam's L1-reachable failure surface is exactly the two
//! documented file-level refusals of ``build_inspect_report`` (its
//! docstring; the twins' raise sites): the short-buffer
//! :class:`ValueError` and path-level :class:`OSError`. The Python
//! side's own classification for every one of them is the fitness class
//! ``crash`` (``src/catpart/fitness/runner.py::_classify_file``:
//! "``crash`` covers every exception raised while producing the output
//! — the documented file-level refusals ... as well as unexpected
//! parser exceptions"; the A2 fixture table pins the same mapping —
//! ``short-file`` → "the ``crash`` class"). This seam therefore emits
//! ``{"error_class": "crash", "detail": ...}`` for both refusals: the
//! vocabulary matches the Python side exactly for the L1-reachable
//! classes, and the ``detail`` prose (never compared byte-wise, §3.2)
//! keeps the two refusal modes distinguishable for humans. Any other
//! failure of this binary (a decode panic, a malformed write) exits
//! outside the 0/1 contract and the harness records a harness-level
//! failure — which never counts as a match (§3.2).
//!
//! Numeric contract (spec §2.2): this file performs no arithmetic — it
//! is assembly and I/O only, so unlike the decode modules it carries
//! no ``suboptimal_flops`` allow (the V0 lint policy, ``lib.rs``).

use std::io::Write;
use std::process::ExitCode;

use port::containers::{ContainerRecord, detect_kind, parse_container_table};
use port::header::{HEADER_SIZE, HeaderInfo, parse_header};
use port::identity::parse_document_name;
use port::trailer::{TrailerInfo, parse_trailer};
use port::version::detect_version;
use serde::Serialize;

/// The schema-v1 inspect document (``catpart-inspect`` stdout; schema
/// ``src/catpart/schema/v1.json``). Field declaration order = the
/// Python dict construction order of ``build_inspect_report`` (spec
/// §2.1: even byte JSON equality stays reachable, though Fidelity
/// compares parsed documents, §3.2).
#[derive(Serialize)]
struct InspectDocument {
    schema_version: u32,
    magic: String,
    header_dword: u32,
    header_dword12: u32,
    ff8_at_16_24: bool,
    header_dword16: Option<u32>,
    header_dword20: Option<u32>,
    file_size: u64,
    detected_version: String,
    kind: &'static str,
    document_name: Option<String>,
    containers: Vec<ContainerRecord>,
    trailer: Option<TrailerInfo>,
}

/// The classified error line (the ``catpart-export``/§3.2 shape:
/// ``{"error_class": ..., "detail": ...}``, one JSON line on stderr,
/// exit 1).
#[derive(Serialize)]
struct ClassifiedError {
    error_class: &'static str,
    detail: String,
}

/// The schema version of the document this seam emits (twin:
/// ``catpart.cli.SCHEMA_VERSION``).
const SCHEMA_VERSION: u32 = 1;

const USAGE: &str = "usage: fidelity-cli inspect <file>\n       (export mode lands with V2, ticket #41; usage errors exit 2)";

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.first().map(String::as_str) {
        Some("inspect") if args.len() == 2 => run_inspect(&args[1]),
        _ => {
            eprint!("{USAGE}");
            ExitCode::from(2)
        }
    }
}

/// The twin of ``catpart.cli.main_inspect`` +
/// ``build_inspect_report``: the file-level refusals first (stat,
/// 32-byte minimum), then the whole-buffer decode, then the document
/// on stdout.
fn run_inspect(path: &str) -> ExitCode {
    let file_size = match std::fs::metadata(path) {
        Ok(metadata) => metadata.len(),
        Err(err) => return emit_crash(&format!("{path}: {err}")),
    };
    if file_size < HEADER_SIZE as u64 {
        // The twin's ValueError prose (``build_inspect_report``), the
        // detail of the same crash class.
        return emit_crash(&format!(
            "not a CATIA V5 container: header needs {HEADER_SIZE} bytes, got {file_size}"
        ));
    }
    let data = match std::fs::read(path) {
        Ok(data) => data,
        Err(err) => return emit_crash(&format!("{path}: {err}")),
    };
    let HeaderInfo {
        magic,
        header_dword,
        header_dword12,
        ff8_at_16_24,
        header_dword16,
        header_dword20,
    } = match parse_header(&data[..HEADER_SIZE]) {
        Ok(info) => info,
        Err(err) => return emit_crash(&err.to_string()),
    };
    let records = parse_container_table(&data);
    let document = InspectDocument {
        schema_version: SCHEMA_VERSION,
        magic,
        header_dword,
        header_dword12,
        ff8_at_16_24,
        header_dword16,
        header_dword20,
        file_size,
        detected_version: detect_version(&data),
        kind: detect_kind(&records),
        document_name: parse_document_name(&data),
        containers: records,
        trailer: parse_trailer(&data),
    };
    let stdout = std::io::stdout().lock();
    if let Err(err) = serde_json::to_writer_pretty(stdout, &document) {
        return emit_crash(&format!("cannot write the document: {err}"));
    }
    let _ = std::io::stdout().lock().write_all(b"\n");
    ExitCode::SUCCESS
}

/// One JSON ``{"error_class": "crash", "detail": ...}`` line on
/// stderr, exit 1 (the classified-failure contract, §3.2).
fn emit_crash(detail: &str) -> ExitCode {
    let error = ClassifiedError {
        error_class: "crash",
        detail: detail.to_string(),
    };
    // The error line is the failure artifact — write it, then exit.
    let mut stderr = std::io::stderr().lock();
    let _ = serde_json::to_writer(&mut stderr, &error);
    let _ = stderr.write_all(b"\n");
    ExitCode::from(1)
}
