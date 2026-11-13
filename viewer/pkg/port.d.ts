/* tslint:disable */
/* eslint-disable */

/**
 * The §2.3 export entry: the summary plus the typed-array mesh and the
 * additive curve loops, or the classified error thrown. The PLY has no
 * meaning at this boundary — the viewer consumes the arrays directly.
 */
export function decode_export(bytes: Uint8Array | number[]): any;

/**
 * The §2.3 inspect entry: the schema-v1 document for the whole buffer,
 * or the classified error thrown (see the module header). Whole-buffer
 * only — the decode is one pass over the in-memory buffer, the shape
 * the Fidelity harness compares (§2.3's rationale).
 */
export function decode_inspect(bytes: Uint8Array | number[]): any;

export type InitInput = RequestInfo | URL | Response | BufferSource | WebAssembly.Module;

export interface InitOutput {
    readonly memory: WebAssembly.Memory;
    readonly decode_export: (a: number, b: number) => [number, number, number];
    readonly decode_inspect: (a: number, b: number) => [number, number, number];
    readonly __wbindgen_malloc: (a: number, b: number) => number;
    readonly __wbindgen_realloc: (a: number, b: number, c: number, d: number) => number;
    readonly __wbindgen_free: (a: number, b: number, c: number) => void;
    readonly __wbindgen_exn_store: (a: number) => void;
    readonly __externref_table_alloc: () => number;
    readonly __wbindgen_externrefs: WebAssembly.Table;
    readonly __externref_table_dealloc: (a: number) => void;
    readonly __wbindgen_start: () => void;
}

export type SyncInitInput = BufferSource | WebAssembly.Module;

/**
 * Instantiates the given `module`, which can either be bytes or
 * a precompiled `WebAssembly.Module`.
 *
 * @param {{ module: SyncInitInput }} module - Passing `SyncInitInput` directly is deprecated.
 *
 * @returns {InitOutput}
 */
export function initSync(module: { module: SyncInitInput } | SyncInitInput): InitOutput;

/**
 * If `module_or_path` is {RequestInfo} or {URL}, makes a request and
 * for everything else, calls `WebAssembly.instantiate` directly.
 *
 * @param {{ module_or_path: InitInput | Promise<InitInput> }} module_or_path - Passing `InitInput` directly is deprecated.
 *
 * @returns {Promise<InitOutput>}
 */
export default function __wbg_init (module_or_path?: { module_or_path: InitInput | Promise<InitInput> } | InitInput | Promise<InitInput>): Promise<InitOutput>;
