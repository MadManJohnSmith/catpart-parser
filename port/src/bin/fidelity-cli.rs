//! The native CLI seam (spec §2.4 of ``docs/specs/phase5-viewer-spec.md``):
//! ``fidelity-cli`` — the harness drives the port through this binary
//! exactly the way it drives the Python console scripts, so a mismatch
//! is attributable to the decoder, never to harness plumbing.
//!
//! V1 (ticket #40): **inspect mode** — the L1 slice's schema-v1
//! document, the I/O contract of ``catpart-inspect``
//! (``src/catpart/cli.py::main_inspect``): one file-path argument, the
//! summary JSON on stdout (field declaration order = the Python dict
//! construction order of ``build_inspect_report`` — spec §2.1), and a
//! classified error as one JSON line on stderr with exit 1. Usage
//! errors exit 2 (argparse convention).
//!
//! V2 (ticket #41): **export mode** — the non-composite geometry
//! slice's seam, the I/O contract of ``catpart-export``
//! (``src/catpart/cli.py::main_export``, spec §2.4): the file path
//! argument, the PLY path as the second argument, the summary JSON on
//! stdout (field declaration order = the Python dict construction
//! order of ``_export_store``), the binary-LE PLY written to the
//! second path only after the whole store decodes (failures leave no
//! partial output), and a classified error as one JSON line on stderr
//! with exit 1. Usage errors exit 2.
//!
//! # The error-class vocabularies
//!
//! Inspect (L1, one class: ``crash``): the inspect seam's L1-reachable
//! failure surface is exactly the two documented file-level refusals
//! of ``build_inspect_report`` (its docstring; the twins' raise sites):
//! the short-buffer :class:`ValueError` and path-level
//! :class:`OSError`. The Python side's own classification for every
//! one of them is the fitness class ``crash``
//! (``src/catpart/fitness/runner.py::_classify_file``: "``crash``
//! covers every exception raised while producing the output — the
//! documented file-level refusals ... as well as unexpected parser
//! exceptions"; the A2 fixture table pins the same mapping —
//! ``short-file`` → "the ``crash`` class"). This seam therefore emits
//! ``{"error_class": "crash", "detail": ...}`` for both refusals: the
//! vocabulary matches the Python side exactly for the L1-reachable
//! classes, and the ``detail`` prose (never compared byte-wise, §3.2)
//! keeps the two refusal modes distinguishable for humans.
//!
//! Export (L2, the geometry vocabulary): the classified-failure seam
//! of ``catpart.geometry.errors`` — ``missing-geometry-store``,
//! ``undecoded-variant``, ``malformed-store-header``,
//! ``malformed-pool-group``, ``malformed-pool-vertex``,
//! ``unreadable-file``/``io-error`` — at the twin's exact raise sites
//! (the port's ``geometry/errors.rs`` single-sources the strings; the
//! §2.3 vocabulary). The Python side's own classes for the same raise
//! sites are these kebab classes (one JSON line on stderr, exit 1);
//! no finer class exists on either side, and none is invented here.
//! The V2 fail-closed composite arms raise ``undecoded-variant`` (the
//! twin's class for every composite-path refusal; composite-path
//! EXPORTS are excluded by the harness, never false matches — the
//! ticket's hard stop; see ``geometry/export.rs``).
//!
//! Any other failure of this binary (a decode panic, a malformed
//! write) exits outside the 0/1 contract and the harness records a
//! harness-level failure — which never counts as a match (§3.2). The
//! panics mirror the twin's own unclassified crashes (the empty-file
//! mmap ``ValueError`` and past-EOF ``IndexError`` arms), which the
//! compared populations never reach.
//!
//! Numeric contract (spec §2.2): this file performs no arithmetic — it
//! is assembly and I/O only, so unlike the decode modules it carries
//! no ``suboptimal_flops`` allow (the V0 lint policy, ``lib.rs``).

use std::io::Write;
use std::process::ExitCode;

use port::geometry::errors::ExportError;
use port::geometry::export::build_export;
use port::inspect::{InspectDocument, build_inspect_document};
use serde::Serialize;

/// The classified error line (the ``catpart-export``/§3.2 shape:
/// ``{"error_class": ..., "detail": ...}``, one JSON line on stderr,
/// exit 1).
#[derive(Serialize)]
struct ClassifiedError {
    error_class: &'static str,
    detail: String,
}

const USAGE: &str = "usage: fidelity-cli inspect <file>\n       fidelity-cli export <file> <ply-output>\n       (usage errors exit 2)";

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.first().map(String::as_str) {
        Some("inspect") if args.len() == 2 => run_inspect(&args[1]),
        Some("export") if args.len() == 3 => run_export(&args[1], &args[2]),
        _ => {
            eprint!("{USAGE}");
            ExitCode::from(2)
        }
    }
}

/// The twin of ``catpart.cli.main_inspect``: the path-level refusals
/// (stat, read — the OSError arm, the crash class), then the shared
/// whole-buffer document build (``inspect.rs``, the builder the WASM
/// boundary also drives), then the document on stdout.
fn run_inspect(path: &str) -> ExitCode {
    if let Err(err) = std::fs::metadata(path) {
        return emit_classified("crash", &format!("{path}: {err}"));
    }
    let data = match std::fs::read(path) {
        Ok(data) => data,
        Err(err) => return emit_classified("crash", &format!("{path}: {err}")),
    };
    let document: InspectDocument = match build_inspect_document(&data) {
        Ok(document) => document,
        Err(refusal) => return emit_classified(refusal.error_class, &refusal.detail),
    };
    let stdout = std::io::stdout().lock();
    if let Err(err) = serde_json::to_writer_pretty(stdout, &document) {
        return emit_classified("crash", &format!("cannot write the document: {err}"));
    }
    let _ = std::io::stdout().lock().write_all(b"\n");
    ExitCode::SUCCESS
}

/// The twin of ``catpart.cli.main_export`` + ``build_export``: the
/// classified decode (the PLY is written only after the whole store
/// decodes — failures leave no partial output), then the summary JSON
/// on stdout.
fn run_export(path: &str, out_path: &str) -> ExitCode {
    match build_export(path, out_path) {
        Ok(summary) => {
            let stdout = std::io::stdout().lock();
            if let Err(err) = serde_json::to_writer_pretty(stdout, &summary) {
                return emit_classified("io-error", &format!("cannot write the summary: {err}"));
            }
            let _ = std::io::stdout().lock().write_all(b"\n");
            ExitCode::SUCCESS
        }
        Err(ExportError {
            error_class,
            detail,
        }) => emit_classified(error_class, &detail),
    }
}

/// One JSON ``{"error_class": ..., "detail": ...}`` line on stderr,
/// exit 1 (the classified-failure contract, §3.2).
fn emit_classified(error_class: &'static str, detail: &str) -> ExitCode {
    let error = ClassifiedError {
        error_class,
        detail: detail.to_string(),
    };
    // The error line is the failure artifact — write it, then exit.
    let mut stderr = std::io::stderr().lock();
    let _ = serde_json::to_writer(&mut stderr, &error);
    let _ = stderr.write_all(b"\n");
    ExitCode::from(1)
}
