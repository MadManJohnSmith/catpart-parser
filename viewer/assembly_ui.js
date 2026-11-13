/* Interactive Assembly UI & Classification Tree Engine (Phase 6, Ticket P3-V5)
   Design Authority: docs/specs/phase6-assembly-viewer-spec.md §4.1, §4.3, §6, §7, §8
   Prior Art: site/viewer/catalog.js, site/viewer/ingest.js, site/viewer/assembly_scene.js

   Implements:
   1. The 4 Canonical Classification Badges (§4.1, §3.2, §6.2):
      - Placed (Green #22c55e / var(--color-success))
      - Identity (Cyan/Blue #06b6d4 / var(--color-info))
      - Unresolved Part (Amber/Yellow #f59e0b / var(--color-warning)) - MUST BE VISIBLE (never omitted)
      - Undecodable Placement (Red/Rose #ef4444 / var(--color-danger)) - ANTI-MASKING (never origin identity)
   2. Hierarchical Instance Tree View with root product row and instance list:
      - Visibility toggle button (eye icon) calling scene.setInstanceVisibility(id, bool)
      - Camera focus/isolate button (crosshair icon) calling scene.isolateInstance(id)
      - Instance Name (instance_name) and Part Number (part_number)
      - Status Badge with explanatory tooltip
   3. Instance Inspector Panel:
      - Instance Name & Part Number
      - Pairing Rule used (triple, desc_block, bare_pair)
      - Classification State & details
      - Coordinate Transform Table: Translation [X, Y, Z] in mm, Quaternion [Qw, Qx, Qy, Qz] (w-first)
   4. Toolbar Controls:
      - Exploded View slider (lambda in [0.0, 3.0], default 0.0) with real-time value display
      - Summary bar: total count, placed count, identity count, unresolved count, undecodable count
      - Assembly switcher for multi-product ingestion disambiguation (§4.3)
   5. Pure ES module style with zero external dependencies.

   Compatible with browser DOM and headless environments.
*/

// --- 1. Classification Status & Pairing Constants (Spec §3.2) -----------------

export const STATUS_PLACED = "placed";
export const STATUS_IDENTITY = "identity";
export const STATUS_UNRESOLVED = "unresolved";
export const STATUS_UNDECODABLE = "undecodable";

export const PAIRING_RULE_TRIPLE = "triple";
export const PAIRING_RULE_DESC_BLOCK = "desc_block";
export const PAIRING_RULE_BARE_PAIR = "bare_pair";

/**
 * Metadata configuration for the 4 canonical classification badges.
 */
export const BADGE_CONFIG = {
  [STATUS_PLACED]: {
    label: "Placed",
    badgeClass: "badge-placed",
    pillClass: "pill good",
    colorHex: "#22c55e",
    cssVar: "var(--color-success)",
    tooltip: "Instance placed at spatial 3D transform",
  },
  [STATUS_IDENTITY]: {
    label: "Identity",
    badgeClass: "badge-identity",
    pillClass: "pill neutral",
    colorHex: "#06b6d4",
    cssVar: "var(--color-info)",
    tooltip: "Default identity placement at origin",
  },
  [STATUS_UNRESOLVED]: {
    label: "Unresolved Part",
    badgeClass: "badge-unresolved",
    pillClass: "pill warn",
    colorHex: "#f59e0b",
    cssVar: "var(--color-warning)",
    tooltip: "Part missing from catalog — not rendered in 3D scene (never omitted from tree)",
  },
  [STATUS_UNDECODABLE]: {
    label: "Undecodable Placement",
    badgeClass: "badge-undecodable",
    pillClass: "pill bad",
    colorHex: "#ef4444",
    cssVar: "var(--color-danger)",
    tooltip: "Transform unresolvable — anti-masking: never falls back to identity origin",
  },
};

// --- 2. SVG Icon Templates ---------------------------------------------------

export const SVG_ICONS = {
  eyeOpen:
    '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
  eyeClosed:
    '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>',
  crosshair:
    '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="22" y1="12" x2="18" y2="12"/><line x1="6" y1="12" x2="2" y2="12"/><line x1="12" y1="6" x2="12" y2="2"/><line x1="12" y1="22" x2="12" y2="18"/></svg>',
  assembly:
    '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>',
  part:
    '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/></svg>',
};

// --- 3. Formatting & HTML Helpers --------------------------------------------

/**
 * Escapes unsafe characters for HTML embedding.
 *
 * @param {any} text
 * @returns {string}
 */
export function escapeHtml(text) {
  if (text === null || text === undefined) return "";
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

/**
 * Formats a floating-point coordinate value with fixed precision.
 *
 * @param {number} val
 * @param {number} [precision=4]
 * @returns {string}
 */
export function formatCoordinate(val, precision = 4) {
  if (typeof val !== "number" || Number.isNaN(val)) return "0.0000";
  if (!Number.isFinite(val)) return String(val);
  const clean = Math.abs(val) < 1e-12 ? 0.0 : val;
  return clean.toFixed(precision);
}

/**
 * Normalizes status string to canonical lower-case form.
 *
 * @param {string} status
 * @returns {string}
 */
export function normalizeStatus(status) {
  if (!status) return STATUS_PLACED;
  const s = String(status).trim().toLowerCase();
  if (s.includes("unresolved")) return STATUS_UNRESOLVED;
  if (s.includes("undecodable")) return STATUS_UNDECODABLE;
  if (s.includes("identity")) return STATUS_IDENTITY;
  if (s.includes("placed")) return STATUS_PLACED;
  return s;
}

/**
 * Renders an HTML string for one of the 4 canonical classification badges.
 *
 * @param {string} status - "placed" | "identity" | "unresolved" | "undecodable"
 * @param {Object} [options={}]
 * @param {string} [options.customTooltip]
 * @param {string} [options.extraClass]
 * @returns {string}
 */
export function renderBadgeHtml(status, options = {}) {
  const norm = normalizeStatus(status);
  const cfg = BADGE_CONFIG[norm] || BADGE_CONFIG[STATUS_PLACED];
  const tooltip = options.customTooltip || cfg.tooltip;
  const extraClass = options.extraClass ? ` ${options.extraClass}` : "";
  const classes = `status-badge ${cfg.badgeClass} ${cfg.pillClass}${extraClass}`;

  return `<span class="${classes}" title="${escapeHtml(tooltip)}" data-status="${norm}">${escapeHtml(cfg.label)}</span>`;
}

/**
 * Generates HTML string for the Coordinate Transform Table.
 *
 * Enforces the Anti-Masking Invariant:
 * Undecodable placements NEVER display origin identity coordinates!
 *
 * @param {number[]|null} transform - 7-tuple [tx, ty, tz, qw, qx, qy, qz]
 * @param {string} status - Canonical classification status
 * @param {Object} [options={}]
 * @param {string} [options.detail] - Optional classification refusal explanation
 * @returns {string}
 */
export function renderTransformTableHtml(transform, status, options = {}) {
  const norm = normalizeStatus(status);
  const detail = options.detail || "";

  if (norm === STATUS_UNDECODABLE) {
    return `
      <div class="inspector-notice bad">
        <div class="notice-title"><strong>Undecodable Placement</strong></div>
        <p>Transform unresolvable from binary records. Anti-masking invariant strictly enforced:
        this instance is <strong>never defaulted to origin identity</strong>.</p>
        ${detail ? `<p class="notice-detail dim">${escapeHtml(detail)}</p>` : ""}
      </div>
    `;
  }

  if (norm === STATUS_UNRESOLVED) {
    return `
      <div class="inspector-notice warn">
        <div class="notice-title"><strong>Unresolved Part</strong></div>
        <p>Component <code>.CATPart</code> file missing from uploaded catalog. The instance is
        classified and visible in the tree, but 3D geometry is not available.</p>
        ${detail ? `<p class="notice-detail dim">${escapeHtml(detail)}</p>` : ""}
      </div>
    `;
  }

  if (norm === STATUS_IDENTITY) {
    return `
      <div class="inspector-notice info">
        <div class="notice-title"><strong>Origin Identity Default</strong></div>
        <p>No <code>_Position</code> transform declared in CATProduct pool. Placed at canonical identity origin.</p>
      </div>
      <table class="transform-table" aria-label="Identity coordinates table">
        <thead>
          <tr>
            <th colspan="2">Translation (mm)</th>
            <th colspan="2">Quaternion (w-first)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>X</td><td><code>0.0000 mm</code></td>
            <td>Q<sub>w</sub></td><td><code>1.0000</code></td>
          </tr>
          <tr>
            <td>Y</td><td><code>0.0000 mm</code></td>
            <td>Q<sub>x</sub></td><td><code>0.0000</code></td>
          </tr>
          <tr>
            <td>Z</td><td><code>0.0000 mm</code></td>
            <td>Q<sub>y</sub></td><td><code>0.0000</code></td>
          </tr>
          <tr>
            <td>—</td><td>—</td>
            <td>Q<sub>z</sub></td><td><code>0.0000</code></td>
          </tr>
        </tbody>
      </table>
    `;
  }

  // STATUS_PLACED
  const t = Array.isArray(transform) && transform.length >= 7
    ? transform
    : [0, 0, 0, 1, 0, 0, 0];

  const tx = t[0];
  const ty = t[1];
  const tz = t[2];
  const qw = t[3];
  const qx = t[4];
  const qy = t[5];
  const qz = t[6];

  return `
    <table class="transform-table" aria-label="Spatial coordinates table">
      <thead>
        <tr>
          <th colspan="2">Translation (mm)</th>
          <th colspan="2">Quaternion (w-first)</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>X</td><td><code>${formatCoordinate(tx)} mm</code></td>
          <td>Q<sub>w</sub></td><td><code>${formatCoordinate(qw)}</code></td>
        </tr>
        <tr>
          <td>Y</td><td><code>${formatCoordinate(ty)} mm</code></td>
          <td>Q<sub>x</sub></td><td><code>${formatCoordinate(qx)}</code></td>
        </tr>
        <tr>
          <td>Z</td><td><code>${formatCoordinate(tz)} mm</code></td>
          <td>Q<sub>y</sub></td><td><code>${formatCoordinate(qy)}</code></td>
        </tr>
        <tr>
          <td>—</td><td>—</td>
          <td>Q<sub>z</sub></td><td><code>${formatCoordinate(qz)}</code></td>
        </tr>
      </tbody>
    </table>
  `;
}

/**
 * Generates HTML string for the Summary Bar counters.
 *
 * @param {Object} counts
 * @returns {string}
 */
export function renderSummaryBarHtml(counts = {}) {
  const total = Number(counts.total || 0);
  const placed = Number(counts.placed || 0);
  const identity = Number(counts.identity || 0);
  const unresolved = Number(counts.unresolved || 0);
  const undecodable = Number(counts.undecodable || 0);

  return `
    <div class="summary-chip summary-total" title="Total declared instances">
      <span class="chip-label">Total</span>
      <span class="chip-val">${total}</span>
    </div>
    <div class="summary-chip summary-placed pill good badge-placed" title="Instances placed with 3D transform">
      <span class="chip-label">Placed</span>
      <span class="chip-val">${placed}</span>
    </div>
    <div class="summary-chip summary-identity pill neutral badge-identity" title="Instances with identity origin placement">
      <span class="chip-label">Identity</span>
      <span class="chip-val">${identity}</span>
    </div>
    <div class="summary-chip summary-unresolved pill warn badge-unresolved" title="Component parts missing from catalog (never omitted)">
      <span class="chip-label">Unresolved</span>
      <span class="chip-val">${unresolved}</span>
    </div>
    <div class="summary-chip summary-undecodable pill bad badge-undecodable" title="Undecodable placements (anti-masking enforced)">
      <span class="chip-label">Undecodable</span>
      <span class="chip-val">${undecodable}</span>
    </div>
  `;
}

/**
 * Generates HTML string for the Root Product Row.
 *
 * @param {Object} rootInfo
 * @param {Object} [counts={}]
 * @returns {string}
 */
export function renderRootRowHtml(rootInfo = {}, counts = {}) {
  const name = rootInfo.name || "Assembly Root";
  const ver = rootInfo.detectedVersion ? ` (${escapeHtml(rootInfo.detectedVersion)})` : "";
  const total = Number(counts.total || 0);
  const placed = Number(counts.placed || 0);
  const identity = Number(counts.identity || 0);
  const unresolved = Number(counts.unresolved || 0);
  const undecodable = Number(counts.undecodable || 0);

  return `
    <div class="tree-root-row" data-root-name="${escapeHtml(name)}">
      <div class="root-info">
        <div class="root-title">
          <span class="root-icon">${SVG_ICONS.assembly}</span>
          <strong class="root-name">${escapeHtml(name)}</strong>
          <span class="root-ver dim">${ver}</span>
        </div>
        <div class="root-counts dim">
          <span>${total} instance${total === 1 ? "" : "s"}</span>
          <span class="count-breakdown">(${placed} placed, ${identity} identity, ${unresolved} unresolved, ${undecodable} undecodable)</span>
        </div>
      </div>
    </div>
  `;
}

/**
 * Generates HTML string for an individual tree node list item.
 *
 * @param {Object} instance - ProductInstanceRecord
 * @param {Object} [options={}]
 * @returns {string}
 */
export function renderTreeNodeHtml(instance, options = {}) {
  if (!instance || !instance.instance_name) return "";

  const name = String(instance.instance_name);
  const pn = String(instance.part_number || "");
  const normStatus = normalizeStatus(instance.placement_status);
  const isUnresolved = normStatus === STATUS_UNRESOLVED;

  const isVisible = options.visible !== false && !isUnresolved;
  const isIsolated = !!options.isolated;
  const isSelected = !!options.selected;

  const disabledAttr = isUnresolved ? " disabled" : "";
  const visIcon = isVisible ? SVG_ICONS.eyeOpen : SVG_ICONS.eyeClosed;
  const visTitle = isUnresolved
    ? "Part missing from catalog"
    : isVisible
    ? "Hide instance"
    : "Show instance";

  const isolateTitle = isUnresolved
    ? "Part missing from catalog"
    : isIsolated
    ? "Restore all instances"
    : "Isolate instance";

  const selectedClass = isSelected ? " selected" : "";
  const isolatedClass = isIsolated ? " is-isolated" : "";
  const hiddenClass = !isVisible && !isUnresolved ? " is-hidden" : "";

  return `
    <li class="tree-node status-${normStatus}${selectedClass}" data-instance-id="${escapeHtml(name)}" data-part-number="${escapeHtml(pn)}" data-status="${normStatus}">
      <div class="node-row">
        <button class="inst-vis-toggle icon-btn${hiddenClass}" type="button"${disabledAttr} title="${visTitle}" aria-label="Toggle visibility for ${escapeHtml(name)}" data-instance-id="${escapeHtml(name)}">
          ${visIcon}
        </button>
        <button class="inst-isolate-btn icon-btn${isolatedClass}" type="button"${disabledAttr} title="${isolateTitle}" aria-label="Isolate ${escapeHtml(name)}" data-instance-id="${escapeHtml(name)}">
          ${SVG_ICONS.crosshair}
        </button>
        <button class="node-select-btn" type="button" data-instance-id="${escapeHtml(name)}">
          <span class="inst-name">${escapeHtml(name)}</span>
          <span class="part-number dim">(${escapeHtml(pn)})</span>
        </button>
        ${renderBadgeHtml(normStatus)}
      </div>
    </li>
  `;
}

/**
 * Generates HTML string for the Instance Inspector sidebar panel.
 *
 * @param {Object} instance - ProductInstanceRecord
 * @param {Object} [options={}]
 * @returns {string}
 */
export function renderInspectorHtml(instance, options = {}) {
  if (!instance) {
    return `
      <div class="inspector-empty">
        <p class="dim">Select an instance to view transform and pairing details.</p>
      </div>
    `;
  }

  const name = instance.instance_name || "Unknown Instance";
  const pn = instance.part_number || "—";
  const normStatus = normalizeStatus(instance.placement_status);
  const rule = instance.pairing_rule || "triple";
  const tag = instance.object_tag !== undefined && instance.object_tag !== null
    ? `0x${instance.object_tag.toString(16)} (${instance.object_tag})`
    : null;
  const detail = instance.classification_detail || options.classificationDetail || "";

  return `
    <div class="inspector-content" data-instance-id="${escapeHtml(name)}">
      <div class="inspector-header">
        <h3 class="inspector-title">${escapeHtml(name)}</h3>
        ${renderBadgeHtml(normStatus)}
      </div>
      <div class="inspector-kv">
        <div class="kv-row">
          <span class="kv-key">Part Number</span>
          <span class="kv-val"><code>${escapeHtml(pn)}</code></span>
        </div>
        <div class="kv-row">
          <span class="kv-key">Pairing Rule</span>
          <span class="kv-val"><code>${escapeHtml(rule)}</code></span>
        </div>
        <div class="kv-row">
          <span class="kv-key">Classification</span>
          <span class="kv-val"><code>${escapeHtml(normStatus)}</code></span>
        </div>
        ${tag ? `
        <div class="kv-row">
          <span class="kv-key">Object Tag</span>
          <span class="kv-val"><code>${escapeHtml(tag)}</code></span>
        </div>` : ""}
      </div>
      <div class="inspector-section">
        <div class="section-title">Coordinate Transform</div>
        ${renderTransformTableHtml(instance.transform, normStatus, { detail })}
      </div>
    </div>
  `;
}

// --- 4. Lightweight Headless DOM Fallback for Testing ------------------------

/**
 * Creates a minimal DOM element mock when running outside the browser (e.g. Node tests).
 *
 * @param {string} tag
 * @param {any} [ownerDoc=null]
 * @returns {any}
 */
export function createMockElement(tag, ownerDoc = null) {
  const tagName = String(tag).toUpperCase();
  const attributes = new Map();
  const listeners = new Map();
  const children = [];
  const classSet = new Set();

  const el = {
    tagName,
    nodeType: 1,
    ownerDocument: ownerDoc,
    parentNode: null,
    parentElement: null,
    style: {},
    dataset: {},
    value: "",
    disabled: false,
    checked: false,
    title: "",
    hidden: false,

    get className() {
      return Array.from(classSet).join(" ");
    },
    set className(val) {
      classSet.clear();
      if (val) {
        for (const c of String(val).trim().split(/\s+/)) {
          if (c) classSet.add(c);
        }
        attributes.set("class", Array.from(classSet).join(" "));
      } else {
        attributes.delete("class");
      }
    },

    classList: {
      add(...classes) {
        for (const c of classes) if (c) classSet.add(c);
        attributes.set("class", Array.from(classSet).join(" "));
      },
      remove(...classes) {
        for (const c of classes) classSet.delete(c);
        attributes.set("class", Array.from(classSet).join(" "));
      },
      toggle(c, force) {
        let res = false;
        if (force === true) {
          classSet.add(c);
          res = true;
        } else if (force === false) {
          classSet.delete(c);
          res = false;
        } else if (classSet.has(c)) {
          classSet.delete(c);
          res = false;
        } else {
          classSet.add(c);
          res = true;
        }
        attributes.set("class", Array.from(classSet).join(" "));
        return res;
      },
      contains(c) {
        return classSet.has(c);
      },
    },

    setAttribute(k, v) {
      const key = String(k).toLowerCase();
      const val = String(v);
      attributes.set(key, val);
      if (key === "class") el.className = val;
      if (key === "id") el.id = val;
      if (key === "value") el.value = val;
      if (key === "disabled") el.disabled = true;
      if (key.startsWith("data-")) {
        const camel = key.slice(5).replace(/-([a-z])/g, (_, g) => g.toUpperCase());
        el.dataset[camel] = val;
      }
    },

    getAttribute(k) {
      const key = String(k).toLowerCase();
      if (key === "class") return el.className;
      if (key === "id") return el.id || null;
      if (key === "value") return el.value || null;
      return attributes.has(key) ? attributes.get(key) : null;
    },

    hasAttribute(k) {
      return attributes.has(String(k).toLowerCase());
    },

    removeAttribute(k) {
      const key = String(k).toLowerCase();
      attributes.delete(key);
      if (key === "disabled") el.disabled = false;
    },

    get children() {
      return children.filter((c) => c && c.nodeType === 1);
    },

    get childNodes() {
      return [...children];
    },

    appendChild(child) {
      if (!child) return child;
      child.parentNode = el;
      child.parentElement = el;
      children.push(child);
      return child;
    },

    removeChild(child) {
      const idx = children.indexOf(child);
      if (idx !== -1) {
        children.splice(idx, 1);
        child.parentNode = null;
        child.parentElement = null;
      }
      return child;
    },

    replaceChildren(...newChildren) {
      for (const c of children) {
        c.parentNode = null;
        c.parentElement = null;
      }
      children.length = 0;
      for (const c of newChildren) {
        if (c) el.appendChild(c);
      }
    },

    addEventListener(event, fn) {
      const e = String(event).toLowerCase();
      if (!listeners.has(e)) listeners.set(e, []);
      listeners.get(e).push(fn);
    },

    removeEventListener(event, fn) {
      const e = String(event).toLowerCase();
      if (listeners.has(e)) {
        const list = listeners.get(e);
        const idx = list.indexOf(fn);
        if (idx !== -1) list.splice(idx, 1);
      }
    },

    dispatchEvent(ev) {
      const type = (ev && ev.type ? ev.type : String(ev)).toLowerCase();
      if (ev && !ev.target) ev.target = el;
      if (ev && !ev.currentTarget) ev.currentTarget = el;
      if (listeners.has(type)) {
        for (const fn of listeners.get(type)) {
          fn.call(el, ev);
        }
      }
      if (ev && ev.bubbles && el.parentNode && typeof el.parentNode.dispatchEvent === "function") {
        el.parentNode.dispatchEvent(ev);
      }
      return true;
    },

    click() {
      const ev = {
        type: "click",
        target: el,
        currentTarget: el,
        preventDefault() {},
        stopPropagation() {},
        bubbles: true,
      };
      el.dispatchEvent(ev);
    },

    _rawHtml: "",
    get innerHTML() {
      if (children.length > 0) {
        return children
          .map((c) => {
            if (c.outerHTML) return c.outerHTML;
            return c.textContent || "";
          })
          .join("");
      }
      return el._rawHtml;
    },
    set innerHTML(html) {
      el._rawHtml = String(html);
      // Clear children
      children.length = 0;
    },

    get outerHTML() {
      const tag = el.tagName.toLowerCase();
      const attrStrs = [];
      for (const [k, v] of attributes) {
        attrStrs.push(`${k}="${escapeHtml(v)}"`);
      }
      const attrPart = attrStrs.length > 0 ? " " + attrStrs.join(" ") : "";
      return `<${tag}${attrPart}>${el.innerHTML}</${tag}>`;
    },

    _text: "",
    get textContent() {
      if (children.length > 0) {
        return children.map((c) => c.textContent).join("");
      }
      return el._text || el._rawHtml.replace(/<[^>]+>/g, "");
    },
    set textContent(txt) {
      el._text = String(txt);
      el._rawHtml = escapeHtml(txt);
      children.length = 0;
    },

    querySelector(selector) {
      return queryMock(el, selector)[0] || null;
    },

    querySelectorAll(selector) {
      return queryMock(el, selector);
    },
  };

  return el;
}

/**
 * Minimal selector matcher for mock elements.
 * Supports: tag, #id, .class, [attr], [attr="val"]
 */
function elementMatches(el, sel) {
  if (!el || el.nodeType !== 1) return false;
  let s = sel.trim();
  if (s === "*") return true;

  // 1. Extract and test all [attr=val] or [attr] segments
  const attrRegex = /\[([^\]]+)\]/g;
  let match;
  while ((match = attrRegex.exec(s)) !== null) {
    const inner = match[1].trim();
    const eqIdx = inner.indexOf("=");
    if (eqIdx === -1) {
      if (!el.hasAttribute(inner)) return false;
    } else {
      const attr = inner.slice(0, eqIdx).trim();
      let val = inner.slice(eqIdx + 1).trim();
      if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
        val = val.slice(1, -1);
      }
      if (el.getAttribute(attr) !== val) return false;
    }
  }
  // Strip attribute selectors
  s = s.replace(attrRegex, "").trim();
  if (!s) return true;

  // 2. Extract and test #id
  const hashIdx = s.indexOf("#");
  if (hashIdx !== -1) {
    const afterHash = s.slice(hashIdx + 1).split(".")[0];
    if (el.id !== afterHash) return false;
    s = s.slice(0, hashIdx) + s.slice(hashIdx + 1 + afterHash.length);
  }
  if (!s) return true;

  // 3. Extract and test .classes and tag
  const dotParts = s.split(".");
  const tagPart = dotParts[0].trim();
  if (tagPart && el.tagName.toLowerCase() !== tagPart.toLowerCase()) {
    return false;
  }

  for (let i = 1; i < dotParts.length; i++) {
    const c = dotParts[i].trim();
    if (c && !el.classList.contains(c)) return false;
  }

  return true;
}

function queryMock(root, selector) {
  const results = [];
  const parts = selector.trim().split(/\s+/);
  if (parts.length === 0) return results;

  function walk(node) {
    for (const child of node.children) {
      let matches = false;
      if (parts.length === 1) {
        matches = elementMatches(child, parts[0]);
      } else {
        if (elementMatches(child, parts[parts.length - 1])) {
          matches = true;
        }
      }
      if (matches) results.push(child);
      walk(child);
    }
  }

  walk(root);
  return results;
}

/**
 * Creates a minimal headless Document mock.
 */
export function createMinimalDocument() {
  const doc = {
    createElement(tag) {
      return createMockElement(tag, doc);
    },
    getElementById(id) {
      return queryMock(doc.body, `#${id}`)[0] || null;
    },
    querySelector(sel) {
      return queryMock(doc.body, sel)[0] || null;
    },
    querySelectorAll(sel) {
      return queryMock(doc.body, sel);
    },
  };
  doc.body = createMockElement("BODY", doc);
  return doc;
}

// --- 5. DOM Element Factory Functions ----------------------------------------

/**
 * Creates a DOM element for a canonical classification badge.
 *
 * @param {string} status
 * @param {Object} [options={}]
 * @param {any} [doc=null]
 * @returns {any}
 */
export function createBadgeElement(status, options = {}, doc = null) {
  const d = doc || (typeof document !== "undefined" ? document : createMinimalDocument());
  const norm = normalizeStatus(status);
  const cfg = BADGE_CONFIG[norm] || BADGE_CONFIG[STATUS_PLACED];
  const tooltip = options.customTooltip || cfg.tooltip;

  const span = d.createElement("span");
  span.className = `status-badge ${cfg.badgeClass} ${cfg.pillClass}${options.extraClass ? ` ${options.extraClass}` : ""}`;
  span.title = tooltip;
  span.setAttribute("data-status", norm);
  span.textContent = cfg.label;
  return span;
}

/**
 * Creates the Root Product Row DOM element.
 *
 * @param {Object} rootInfo
 * @param {Object} [counts={}]
 * @param {any} [doc=null]
 * @returns {any}
 */
export function createRootRowElement(rootInfo = {}, counts = {}, doc = null) {
  const d = doc || (typeof document !== "undefined" ? document : createMinimalDocument());
  const name = rootInfo.name || "Assembly Root";
  const ver = rootInfo.detectedVersion ? ` (${rootInfo.detectedVersion})` : "";
  const total = Number(counts.total || 0);
  const placed = Number(counts.placed || 0);
  const identity = Number(counts.identity || 0);
  const unresolved = Number(counts.unresolved || 0);
  const undecodable = Number(counts.undecodable || 0);

  const container = d.createElement("div");
  container.className = "tree-root-container";

  const rootRow = d.createElement("div");
  rootRow.className = "tree-root-row";
  rootRow.setAttribute("data-root-name", name);

  const info = d.createElement("div");
  info.className = "root-info";

  const title = d.createElement("div");
  title.className = "root-title";

  const iconSpan = d.createElement("span");
  iconSpan.className = "root-icon";
  iconSpan.innerHTML = SVG_ICONS.assembly;
  title.appendChild(iconSpan);

  const nameEl = d.createElement("strong");
  nameEl.className = "root-name";
  nameEl.textContent = name;
  title.appendChild(nameEl);

  if (ver) {
    const verEl = d.createElement("span");
    verEl.className = "root-ver dim";
    verEl.textContent = ver;
    title.appendChild(verEl);
  }
  info.appendChild(title);

  const countsEl = d.createElement("div");
  countsEl.className = "root-counts dim";

  const totalSpan = d.createElement("span");
  totalSpan.textContent = `${total} instance${total === 1 ? "" : "s"} `;
  countsEl.appendChild(totalSpan);

  const breakdownSpan = d.createElement("span");
  breakdownSpan.className = "count-breakdown";
  breakdownSpan.textContent = `(${placed} placed, ${identity} identity, ${unresolved} unresolved, ${undecodable} undecodable)`;
  countsEl.appendChild(breakdownSpan);

  info.appendChild(countsEl);
  rootRow.appendChild(info);
  container.appendChild(rootRow);

  return container;
}

/**
 * Creates an individual tree node list item DOM element.
 *
 * @param {Object} instance - ProductInstanceRecord
 * @param {Object} [options={}]
 * @param {any} [doc=null]
 * @returns {any}
 */
export function createTreeNodeElement(instance, options = {}, doc = null) {
  const d = doc || (typeof document !== "undefined" ? document : createMinimalDocument());
  const name = String(instance.instance_name);
  const pn = String(instance.part_number || "");
  const normStatus = normalizeStatus(instance.placement_status);
  const isUnresolved = normStatus === STATUS_UNRESOLVED;
  const isVisible = options.visible !== false && !isUnresolved;
  const isIsolated = !!options.isolated;
  const isSelected = !!options.selected;

  const li = d.createElement("li");
  li.className = `tree-node status-${normStatus}${isSelected ? " selected" : ""}`;
  li.setAttribute("data-instance-id", name);
  li.setAttribute("data-part-number", pn);
  li.setAttribute("data-status", normStatus);
  li.setAttribute("role", "treeitem");

  const row = d.createElement("div");
  row.className = "node-row";

  // Visibility button
  const visBtn = d.createElement("button");
  visBtn.type = "button";
  visBtn.className = `inst-vis-toggle icon-btn${!isVisible && !isUnresolved ? " is-hidden" : ""}`;
  visBtn.setAttribute("data-instance-id", name);
  visBtn.setAttribute("aria-label", `Toggle visibility for ${name}`);
  if (isUnresolved) {
    visBtn.disabled = true;
    visBtn.title = "Part missing from catalog";
  } else {
    visBtn.title = isVisible ? "Hide instance" : "Show instance";
  }
  visBtn.innerHTML = isVisible ? SVG_ICONS.eyeOpen : SVG_ICONS.eyeClosed;
  row.appendChild(visBtn);

  // Isolate button
  const isoBtn = d.createElement("button");
  isoBtn.type = "button";
  isoBtn.className = `inst-isolate-btn icon-btn${isIsolated ? " is-isolated" : ""}`;
  isoBtn.setAttribute("data-instance-id", name);
  isoBtn.setAttribute("aria-label", `Isolate ${name}`);
  if (isUnresolved) {
    isoBtn.disabled = true;
    isoBtn.title = "Part missing from catalog";
  } else {
    isoBtn.title = isIsolated ? "Restore all instances" : "Isolate instance";
  }
  isoBtn.innerHTML = SVG_ICONS.crosshair;
  row.appendChild(isoBtn);

  // Select button
  const selBtn = d.createElement("button");
  selBtn.type = "button";
  selBtn.className = "node-select-btn";
  selBtn.setAttribute("data-instance-id", name);

  const nameSpan = d.createElement("span");
  nameSpan.className = "inst-name";
  nameSpan.textContent = name;
  selBtn.appendChild(nameSpan);

  const pnSpan = d.createElement("span");
  pnSpan.className = "part-number dim";
  pnSpan.textContent = `(${pn})`;
  selBtn.appendChild(pnSpan);

  row.appendChild(selBtn);

  // Status Badge element
  const badgeEl = createBadgeElement(normStatus, options, d);
  row.appendChild(badgeEl);

  li.appendChild(row);
  return li;
}

/**
 * Creates the Coordinate Transform Table DOM element.
 *
 * @param {number[]} transform
 * @param {any} [doc=null]
 * @param {boolean} [isIdentity=false]
 * @returns {any}
 */
export function createTransformTableElement(transform, doc = null, isIdentity = false) {
  const d = doc || (typeof document !== "undefined" ? document : createMinimalDocument());
  const table = d.createElement("table");
  table.className = "transform-table";
  table.setAttribute("aria-label", isIdentity ? "Identity coordinates table" : "Spatial coordinates table");

  const thead = d.createElement("thead");
  const hrow = d.createElement("tr");

  const th1 = d.createElement("th");
  th1.setAttribute("colspan", "2");
  th1.textContent = "Translation (mm)";
  hrow.appendChild(th1);

  const th2 = d.createElement("th");
  th2.setAttribute("colspan", "2");
  th2.textContent = "Quaternion (w-first)";
  hrow.appendChild(th2);

  thead.appendChild(hrow);
  table.appendChild(thead);

  const tbody = d.createElement("tbody");

  const tx = transform[0];
  const ty = transform[1];
  const tz = transform[2];
  const qw = transform[3];
  const qx = transform[4];
  const qy = transform[5];
  const qz = transform[6];

  function addRow(tKey, tVal, qKey, qVal) {
    const tr = d.createElement("tr");

    const td1 = d.createElement("td");
    td1.textContent = tKey;
    tr.appendChild(td1);

    const td2 = d.createElement("td");
    if (tVal !== null) {
      const c = d.createElement("code");
      c.textContent = `${formatCoordinate(tVal)} mm`;
      td2.appendChild(c);
    } else {
      td2.textContent = "—";
    }
    tr.appendChild(td2);

    const td3 = d.createElement("td");
    if (qKey) {
      td3.innerHTML = qKey;
    } else {
      td3.textContent = "—";
    }
    tr.appendChild(td3);

    const td4 = d.createElement("td");
    if (qVal !== null) {
      const c = d.createElement("code");
      c.textContent = formatCoordinate(qVal);
      td4.appendChild(c);
    } else {
      td4.textContent = "—";
    }
    tr.appendChild(td4);

    tbody.appendChild(tr);
  }

  addRow("X", tx, "Q<sub>w</sub>", qw);
  addRow("Y", ty, "Q<sub>x</sub>", qx);
  addRow("Z", tz, "Q<sub>y</sub>", qy);
  addRow("—", null, "Q<sub>z</sub>", qz);

  table.appendChild(tbody);
  return table;
}

/**
 * Creates the Instance Inspector panel DOM element.
 *
 * @param {Object} instance - ProductInstanceRecord
 * @param {Object} [options={}]
 * @param {any} [doc=null]
 * @returns {any}
 */
export function createInspectorElement(instance, options = {}, doc = null) {
  const d = doc || (typeof document !== "undefined" ? document : createMinimalDocument());
  const container = d.createElement("div");
  container.className = "inspector-card";

  if (!instance) {
    const empty = d.createElement("div");
    empty.className = "inspector-empty";
    const p = d.createElement("p");
    p.className = "dim";
    p.textContent = "Select an instance to view transform and pairing details.";
    empty.appendChild(p);
    container.appendChild(empty);
    return container;
  }

  const name = instance.instance_name || "Unknown Instance";
  const pn = instance.part_number || "—";
  const normStatus = normalizeStatus(instance.placement_status);
  const rule = instance.pairing_rule || "triple";
  const tag = instance.object_tag !== undefined && instance.object_tag !== null
    ? `0x${instance.object_tag.toString(16)} (${instance.object_tag})`
    : null;
  const detail = instance.classification_detail || options.classificationDetail || "";

  const content = d.createElement("div");
  content.className = "inspector-content";
  content.setAttribute("data-instance-id", name);

  // Header
  const header = d.createElement("div");
  header.className = "inspector-header";
  const title = d.createElement("h3");
  title.className = "inspector-title";
  title.textContent = name;
  header.appendChild(title);
  header.appendChild(createBadgeElement(normStatus, {}, d));
  content.appendChild(header);

  // Key-value grid
  const kv = d.createElement("div");
  kv.className = "inspector-kv";

  function addKvRow(k, v, isCode = false) {
    const row = d.createElement("div");
    row.className = "kv-row";
    const keyEl = d.createElement("span");
    keyEl.className = "kv-key";
    keyEl.textContent = k;
    const valEl = d.createElement("span");
    valEl.className = "kv-val";
    if (isCode) {
      const code = d.createElement("code");
      code.textContent = v;
      valEl.appendChild(code);
    } else {
      valEl.textContent = v;
    }
    row.appendChild(keyEl);
    row.appendChild(valEl);
    kv.appendChild(row);
  }

  addKvRow("Part Number", pn, true);
  addKvRow("Pairing Rule", rule, true);
  addKvRow("Classification", normStatus, false);
  if (tag) addKvRow("Object Tag", tag, true);
  content.appendChild(kv);

  // Section
  const section = d.createElement("div");
  section.className = "inspector-section";
  const secTitle = d.createElement("div");
  secTitle.className = "section-title";
  secTitle.textContent = "Coordinate Transform";
  section.appendChild(secTitle);

  // Notice / Transform Table
  if (normStatus === STATUS_UNDECODABLE) {
    const notice = d.createElement("div");
    notice.className = "inspector-notice bad";
    const nt = d.createElement("div");
    nt.className = "notice-title";
    const str = d.createElement("strong");
    str.textContent = "Undecodable Placement";
    nt.appendChild(str);
    notice.appendChild(nt);

    const desc = d.createElement("p");
    desc.textContent = "Transform unresolvable from binary records. Anti-masking invariant strictly enforced: this instance is never defaulted to origin identity.";
    notice.appendChild(desc);

    if (detail) {
      const dt = d.createElement("p");
      dt.className = "notice-detail dim";
      dt.textContent = detail;
      notice.appendChild(dt);
    }
    section.appendChild(notice);
  } else if (normStatus === STATUS_UNRESOLVED) {
    const notice = d.createElement("div");
    notice.className = "inspector-notice warn";
    const nt = d.createElement("div");
    nt.className = "notice-title";
    const str = d.createElement("strong");
    str.textContent = "Unresolved Part";
    nt.appendChild(str);
    notice.appendChild(nt);

    const desc = d.createElement("p");
    desc.textContent = "Component .CATPart file missing from uploaded catalog. The instance is classified and visible in the tree, but 3D geometry is not available.";
    notice.appendChild(desc);

    if (detail) {
      const dt = d.createElement("p");
      dt.className = "notice-detail dim";
      dt.textContent = detail;
      notice.appendChild(dt);
    }
    section.appendChild(notice);
  } else if (normStatus === STATUS_IDENTITY) {
    const notice = d.createElement("div");
    notice.className = "inspector-notice info";
    const nt = d.createElement("div");
    nt.className = "notice-title";
    const str = d.createElement("strong");
    str.textContent = "Origin Identity Default";
    nt.appendChild(str);
    notice.appendChild(nt);

    const desc = d.createElement("p");
    desc.textContent = "No _Position transform declared in CATProduct pool. Placed at canonical identity origin.";
    notice.appendChild(desc);
    section.appendChild(notice);

    section.appendChild(createTransformTableElement([0, 0, 0, 1, 0, 0, 0], d, true));
  } else {
    // STATUS_PLACED
    const t = Array.isArray(instance.transform) && instance.transform.length >= 7
      ? instance.transform
      : [0, 0, 0, 1, 0, 0, 0];
    section.appendChild(createTransformTableElement(t, d, false));
  }

  content.appendChild(section);
  container.appendChild(content);
  return container;
}

/**
 * Creates the Summary Bar DOM element.
 *
 * @param {Object} counts
 * @param {any} [doc=null]
 * @returns {any}
 */
export function createSummaryBarElement(counts = {}, doc = null) {
  const d = doc || (typeof document !== "undefined" ? document : createMinimalDocument());
  const bar = d.createElement("div");
  bar.className = "assembly-summary-bar";

  const total = Number(counts.total || 0);
  const placed = Number(counts.placed || 0);
  const identity = Number(counts.identity || 0);
  const unresolved = Number(counts.unresolved || 0);
  const undecodable = Number(counts.undecodable || 0);

  function makeChip(label, val, classes, tooltip) {
    const chip = d.createElement("div");
    chip.className = `summary-chip ${classes}`;
    chip.title = tooltip;
    const l = d.createElement("span");
    l.className = "chip-label";
    l.textContent = label;
    const v = d.createElement("span");
    v.className = "chip-val";
    v.textContent = String(val);
    chip.appendChild(l);
    chip.appendChild(v);
    return chip;
  }

  bar.appendChild(makeChip("Total", total, "summary-total", "Total declared instances"));
  bar.appendChild(makeChip("Placed", placed, "summary-placed pill good badge-placed", "Instances placed with 3D transform"));
  bar.appendChild(makeChip("Identity", identity, "summary-identity pill neutral badge-identity", "Instances with identity origin placement"));
  bar.appendChild(makeChip("Unresolved", unresolved, "summary-unresolved pill warn badge-unresolved", "Component parts missing from catalog (never omitted)"));
  bar.appendChild(makeChip("Undecodable", undecodable, "summary-undecodable pill bad badge-undecodable", "Undecodable placements (anti-masking enforced)"));

  return bar;
}

// --- 6. AssemblyUI Orchestration Controller ----------------------------------

/**
 * Interactive Assembly UI and Classification Tree Controller.
 *
 * Coordinates:
 * - Hierarchical instance tree view with real-time status badges
 * - Anti-omission guarantee: Unresolved parts are never omitted from tree
 * - Anti-masking invariant: Undecodable placements never defaulted to origin identity
 * - Interactive visibility toggle and instance isolation
 * - Instance Inspector panel with 7-tuple translation and w-first quaternion
 * - Exploded view slider (lambda in [0.0, 3.0])
 * - Multi-product root switcher dropdown
 */
export class AssemblyUI {
  /**
   * @param {Object} [options={}]
   * @param {HTMLElement|any} [options.treeContainer] - Container for the assembly tree
   * @param {HTMLElement|any} [options.inspectorContainer] - Container for the instance inspector
   * @param {HTMLElement|any} [options.summaryContainer] - Container for the summary bar
   * @param {HTMLElement|any} [options.toolbarContainer] - Container for exploded view controls
   * @param {HTMLElement|any} [options.switcherContainer] - Container for assembly switcher dropdown
   * @param {any} [options.scene=null] - AssemblyScene instance (site/viewer/assembly_scene.js)
   * @param {any} [options.catalog=null] - VirtualFileCatalog instance (site/viewer/catalog.js)
   * @param {any} [options.document=null] - Document implementation (defaults to window.document or mock)
   * @param {(record: any, el: any) => void} [options.onSelectInstance]
   * @param {(instanceId: string, visible: boolean) => void} [options.onToggleVisibility]
   * @param {(instanceId: string, isIsolated: boolean) => void} [options.onIsolateInstance]
   * @param {(scale: number) => void} [options.onExplodeChange]
   * @param {(product: any) => void} [options.onSwitchProduct]
   */
  constructor(options = {}) {
    this.options = options;
    this.doc = options.document || (typeof document !== "undefined" ? document : createMinimalDocument());

    this.treeContainer = options.treeContainer || null;
    this.inspectorContainer = options.inspectorContainer || null;
    this.summaryContainer = options.summaryContainer || null;
    this.toolbarContainer = options.toolbarContainer || null;
    this.switcherContainer = options.switcherContainer || null;

    this.scene = options.scene || null;
    this.catalog = options.catalog || null;

    /** @type {Object|null} Active ProductStructureDocument */
    this.currentDocument = null;

    /** @type {Map<string, Object>} instanceName -> ProductInstanceRecord */
    this.instanceMap = new Map();

    /** @type {Map<string, boolean>} instanceName -> isVisible */
    this.visibilityMap = new Map();

    /** @type {string|null} ID of currently isolated instance */
    this.isolatedInstanceId = null;

    /** @type {string|null} ID of currently selected instance */
    this.selectedInstanceId = null;

    /** @type {number} Current exploded view scale */
    this.explodedScale = 0.0;

    /** @type {any[]} List of available product entries for switcher */
    this.productsList = [];

    // Internal DOM references created during render
    this.treeListEl = null;
    this.sliderInputEl = null;
    this.sliderValEl = null;
    this.switcherSelectEl = null;
  }

  /**
   * Sets the active AssemblyScene instance.
   *
   * @param {any} scene
   * @returns {this}
   */
  setScene(scene) {
    this.scene = scene;
    return this;
  }

  /**
   * Sets the active VirtualFileCatalog instance.
   *
   * @param {any} catalog
   * @returns {this}
   */
  setCatalog(catalog) {
    this.catalog = catalog;
    return this;
  }

  /**
   * Loads and renders an assembly from a ProductStructureDocument.
   *
   * @param {Object} productDoc - Decoded product structure document
   * @param {any} [catalog=null] - VirtualFileCatalog instance
   * @param {Object} [options={}]
   * @returns {this}
   */
  setAssembly(productDoc, catalog = null, options = {}) {
    if (!productDoc) {
      this.clear();
      return this;
    }

    this.currentDocument = productDoc;
    if (catalog) this.catalog = catalog;

    this.instanceMap.clear();
    this.visibilityMap.clear();
    this.isolatedInstanceId = null;
    this.selectedInstanceId = null;

    const instances = Array.isArray(productDoc.instances) ? productDoc.instances : [];

    // Compute classification tallies
    let placedCount = 0;
    let identityCount = 0;
    let unresolvedCount = 0;
    let undecodableCount = 0;

    for (const inst of instances) {
      const name = String(inst.instance_name);
      let status = normalizeStatus(inst.placement_status);

      // Cross-check with catalog: if part cannot be resolved, ensure marked unresolved
      if (this.catalog && typeof this.catalog.resolvePart === "function" && inst.part_number) {
        const resolved = this.catalog.resolvePart(inst.part_number);
        if (!resolved) {
          status = STATUS_UNRESOLVED;
        }
      }

      const rec = {
        ...inst,
        placement_status: status,
      };

      this.instanceMap.set(name, rec);
      const isVis = status !== STATUS_UNRESOLVED;
      this.visibilityMap.set(name, isVis);

      if (status === STATUS_PLACED) placedCount++;
      else if (status === STATUS_IDENTITY) identityCount++;
      else if (status === STATUS_UNRESOLVED) unresolvedCount++;
      else if (status === STATUS_UNDECODABLE) undecodableCount++;
    }

    const counts = {
      total: instances.length,
      placed: placedCount,
      identity: identityCount,
      unresolved: unresolvedCount,
      undecodable: undecodableCount,
    };

    // 1. Render Summary Bar
    this.renderSummary(counts);

    // 2. Render Tree View
    const rootInfo = {
      name: productDoc.product_name || "Assembly Root",
      detectedVersion: productDoc.detected_version || null,
    };
    this.renderTree(Array.from(this.instanceMap.values()), rootInfo, counts);

    // 3. Setup Toolbar Controls (Exploded View slider)
    this.setupToolbar();

    // 4. Clear or reset Inspector to idle state
    this.clearInspector();

    return this;
  }

  /**
   * Renders the summary bar with the 4-status tallies.
   *
   * @param {Object} counts
   */
  renderSummary(counts) {
    if (!this.summaryContainer) return;
    this.summaryContainer.replaceChildren(createSummaryBarElement(counts, this.doc));
  }

  /**
   * Renders the hierarchical instance tree view.
   *
   * Guarantees:
   * - Unresolved parts are NEVER omitted from the tree.
   * - Root product row shows assembly filename and count breakdown.
   *
   * @param {Object[]} instances - Array of ProductInstanceRecord objects
   * @param {Object} [rootInfo={}]
   * @param {Object} [counts={}]
   */
  renderTree(instances, rootInfo = {}, counts = {}) {
    if (!this.treeContainer) return;

    this.treeContainer.replaceChildren();

    // 1. Create root product container row
    const rootEl = createRootRowElement(rootInfo, counts, this.doc);
    this.treeContainer.appendChild(rootEl);

    // 2. Create instance <ul> list
    const ul = this.doc.createElement("ul");
    ul.className = "assembly-tree";
    ul.setAttribute("role", "tree");
    this.treeListEl = ul;

    for (const inst of instances) {
      const name = inst.instance_name;
      const isVis = this.visibilityMap.get(name) !== false;
      const isIso = this.isolatedInstanceId === name;
      const isSel = this.selectedInstanceId === name;

      const li = createTreeNodeElement(inst, {
        visible: isVis,
        isolated: isIso,
        selected: isSel,
      }, this.doc);

      // Bind node interactions
      this._bindTreeNodeEvents(li, inst);
      ul.appendChild(li);
    }

    this.treeContainer.appendChild(ul);
  }

  /**
   * Binds click and action events to a tree node element.
   *
   * @private
   * @param {any} nodeEl
   * @param {Object} instanceRecord
   */
  _bindTreeNodeEvents(nodeEl, instanceRecord) {
    const id = instanceRecord.instance_name;

    // 1. Visibility toggle button
    const visBtn = nodeEl.querySelector(".inst-vis-toggle");
    if (visBtn) {
      visBtn.addEventListener("click", (ev) => {
        if (ev && typeof ev.stopPropagation === "function") ev.stopPropagation();
        this.toggleInstanceVisibility(id);
      });
    }

    // 2. Camera focus / isolate button
    const isoBtn = nodeEl.querySelector(".inst-isolate-btn");
    if (isoBtn) {
      isoBtn.addEventListener("click", (ev) => {
        if (ev && typeof ev.stopPropagation === "function") ev.stopPropagation();
        this.isolateInstance(id);
      });
    }

    // 3. Node selection
    const selBtn = nodeEl.querySelector(".node-select-btn");
    const handleSelect = (ev) => {
      if (ev && typeof ev.stopPropagation === "function") ev.stopPropagation();
      this.selectInstance(id);
    };

    if (selBtn) {
      selBtn.addEventListener("click", handleSelect);
    }
    nodeEl.addEventListener("click", handleSelect);
  }

  /**
   * Selects an instance in the tree and updates the Inspector.
   *
   * Dispatches 'instance-selected' event and invokes onSelectInstance callback.
   *
   * @param {string} instanceId
   * @returns {Object|null} The selected instance record
   */
  selectInstance(instanceId) {
    const record = this.instanceMap.get(instanceId);
    if (!record) return null;

    this.selectedInstanceId = instanceId;

    // Update tree node visual selection state
    if (this.treeListEl) {
      const allNodes = this.treeListEl.querySelectorAll(".tree-node");
      for (const node of allNodes) {
        if (node.getAttribute("data-instance-id") === instanceId) {
          node.classList.add("selected");
        } else {
          node.classList.remove("selected");
        }
      }
    }

    // Update Inspector panel
    this.renderInspector(record);

    // Callback notification
    if (typeof this.options.onSelectInstance === "function") {
      this.options.onSelectInstance(record, this.getSelectedNodeElement());
    }

    // Dispatch DOM event
    this._dispatchEvent("instance-selected", {
      instanceId,
      instance: record,
      transform: record.transform || null,
      placementStatus: record.placement_status,
      pairingRule: record.pairing_rule || null,
    });

    return record;
  }

  /**
   * Retrieves the currently selected tree node DOM element.
   *
   * @returns {any}
   */
  getSelectedNodeElement() {
    if (!this.treeListEl || !this.selectedInstanceId) return null;
    return this.treeListEl.querySelector(`[data-instance-id="${this.selectedInstanceId}"]`);
  }

  /**
   * Retrieves the currently selected instance record.
   *
   * @returns {Object|null}
   */
  getSelectedInstance() {
    return this.selectedInstanceId ? this.instanceMap.get(this.selectedInstanceId) || null : null;
  }

  /**
   * Renders the Inspector sidebar with instance details and transform table.
   *
   * @param {Object} record
   */
  renderInspector(record) {
    if (!this.inspectorContainer) return;
    this.inspectorContainer.replaceChildren(createInspectorElement(record, {}, this.doc));
  }

  /**
   * Clears the Inspector panel to the default placeholder.
   */
  clearInspector() {
    if (!this.inspectorContainer) return;
    this.inspectorContainer.replaceChildren(createInspectorElement(null, {}, this.doc));
  }

  /**
   * Sets visibility for a specific instance.
   *
   * @param {string} instanceId
   * @param {boolean} visible
   * @returns {boolean} Whether visibility changed
   */
  setInstanceVisibility(instanceId, visible) {
    const record = this.instanceMap.get(instanceId);
    if (!record) return false;

    // Unresolved parts cannot be made visible in 3D scene
    if (record.placement_status === STATUS_UNRESOLVED) {
      this.visibilityMap.set(instanceId, false);
      return false;
    }

    const isVis = !!visible;
    this.visibilityMap.set(instanceId, isVis);

    // Update 3D scene
    if (this.scene && typeof this.scene.setInstanceVisibility === "function") {
      this.scene.setInstanceVisibility(instanceId, isVis);
    }

    // Update tree node button UI
    if (this.treeListEl) {
      const node = this.treeListEl.querySelector(`[data-instance-id="${instanceId}"]`);
      if (node) {
        const btn = node.querySelector(".inst-vis-toggle");
        if (btn) {
          btn.innerHTML = isVis ? SVG_ICONS.eyeOpen : SVG_ICONS.eyeClosed;
          btn.title = isVis ? "Hide instance" : "Show instance";
          if (isVis) {
            btn.classList.remove("is-hidden");
          } else {
            btn.classList.add("is-hidden");
          }
        }
      }
    }

    // Callback notification
    if (typeof this.options.onToggleVisibility === "function") {
      this.options.onToggleVisibility(instanceId, isVis);
    }

    this._dispatchEvent("instance-visibility-changed", {
      instanceId,
      visible: isVis,
    });

    return isVis;
  }

  /**
   * Toggles visibility for a specific instance.
   *
   * @param {string} instanceId
   * @returns {boolean} New visibility state
   */
  toggleInstanceVisibility(instanceId) {
    const curr = this.visibilityMap.get(instanceId) !== false;
    return this.setInstanceVisibility(instanceId, !curr);
  }

  /**
   * Gets current visibility state of an instance.
   *
   * @param {string} instanceId
   * @returns {boolean}
   */
  getInstanceVisibility(instanceId) {
    return this.visibilityMap.get(instanceId) !== false;
  }

  /**
   * Isolates an instance (hides all others). If already isolated, restores all.
   *
   * @param {string|null} instanceId
   * @returns {string|null} Currently isolated instance ID (or null if restored)
   */
  isolateInstance(instanceId) {
    if (!instanceId || this.isolatedInstanceId === instanceId) {
      // Restore all instances
      this.isolatedInstanceId = null;
      for (const [id, rec] of this.instanceMap) {
        if (rec.placement_status !== STATUS_UNRESOLVED) {
          this.setInstanceVisibility(id, true);
        }
      }
    } else {
      // Isolate target
      this.isolatedInstanceId = instanceId;
      for (const [id, rec] of this.instanceMap) {
        if (id === instanceId) {
          this.setInstanceVisibility(id, true);
        } else {
          this.setInstanceVisibility(id, false);
        }
      }
    }

    // Delegate to scene isolateInstance if available
    if (this.scene && typeof this.scene.isolateInstance === "function") {
      this.scene.isolateInstance(this.isolatedInstanceId);
    }

    // Update tree node isolate button UI
    if (this.treeListEl) {
      const allBtns = this.treeListEl.querySelectorAll(".inst-isolate-btn");
      for (const btn of allBtns) {
        const id = btn.getAttribute("data-instance-id");
        if (id === this.isolatedInstanceId) {
          btn.classList.add("is-isolated");
          btn.title = "Restore all instances";
        } else {
          btn.classList.remove("is-isolated");
          btn.title = "Isolate instance";
        }
      }
    }

    // Callback notification
    if (typeof this.options.onIsolateInstance === "function") {
      this.options.onIsolateInstance(instanceId, this.isolatedInstanceId !== null);
    }

    this._dispatchEvent("instance-isolated", {
      instanceId,
      isIsolated: this.isolatedInstanceId !== null,
    });

    return this.isolatedInstanceId;
  }

  /**
   * Retrieves the currently isolated instance ID.
   *
   * @returns {string|null}
   */
  getIsolatedInstance() {
    return this.isolatedInstanceId;
  }

  // --- Toolbar & Exploded View Controls --------------------------------------

  /**
   * Sets up or updates the toolbar controls (Exploded View slider).
   */
  setupToolbar() {
    if (!this.toolbarContainer) return;

    const group = this.doc.createElement("div");
    group.className = "exploded-control";

    const label = this.doc.createElement("label");
    label.className = "dim";
    label.setAttribute("for", "explode-slider");
    label.textContent = "Explode:";
    group.appendChild(label);

    const input = this.doc.createElement("input");
    input.type = "range";
    input.id = "explode-slider";
    input.className = "exploded-slider";
    input.setAttribute("min", "0.0");
    input.setAttribute("max", "3.0");
    input.setAttribute("step", "0.05");
    input.value = this.explodedScale.toFixed(2);
    group.appendChild(input);

    const valSpan = this.doc.createElement("span");
    valSpan.id = "explode-value";
    valSpan.className = "explode-value";
    valSpan.textContent = this.explodedScale.toFixed(2);
    group.appendChild(valSpan);

    this.toolbarContainer.replaceChildren(group);

    this.sliderInputEl = input;
    this.sliderValEl = valSpan;

    input.addEventListener("input", (ev) => {
      const val = parseFloat(ev.target.value) || 0.0;
      this.setExplodedScale(val);
    });
  }

  /**
   * Sets the exploded view scale lambda in [0.0, 3.0].
   *
   * @param {number} scale
   * @returns {number} The clamped applied scale
   */
  setExplodedScale(scale) {
    const lambda = Math.max(0.0, Math.min(3.0, Number(scale) || 0.0));
    this.explodedScale = lambda;

    if (this.sliderInputEl) {
      this.sliderInputEl.value = String(lambda);
    }
    if (this.sliderValEl) {
      this.sliderValEl.textContent = lambda.toFixed(2);
    }

    // Update 3D scene
    if (this.scene && typeof this.scene.setExplodedScale === "function") {
      this.scene.setExplodedScale(lambda);
    }

    // Callback notification
    if (typeof this.options.onExplodeChange === "function") {
      this.options.onExplodeChange(lambda);
    }

    this._dispatchEvent("exploded-scale-changed", { scale: lambda });

    return lambda;
  }

  /**
   * Returns current exploded view scale.
   *
   * @returns {number}
   */
  getExplodedScale() {
    return this.explodedScale;
  }

  // --- Multi-Product Switcher (§4.3) -----------------------------------------

  /**
   * Configures the product switcher dropdown when multiple .CATProduct files are ingested.
   *
   * @param {any[]} products - Array of product file/catalog entries
   * @param {string|any} [activeProduct=null] - Currently active product name or entry
   */
  setProductList(products, activeProduct = null) {
    this.productsList = Array.isArray(products) ? products : [];
    if (!this.switcherContainer) return;

    if (this.productsList.length <= 1) {
      this.switcherContainer.replaceChildren();
      this.switcherSelectEl = null;
      return;
    }

    const activeName = activeProduct
      ? (typeof activeProduct === "string" ? activeProduct : activeProduct.name || activeProduct.stem)
      : null;

    const select = this.doc.createElement("select");
    select.id = "root-product-select";
    select.className = "product-select";
    select.setAttribute("aria-label", "Select root assembly product");

    for (const p of this.productsList) {
      const name = typeof p === "string" ? p : p.name || p.stem || "Product";
      const opt = this.doc.createElement("option");
      opt.value = name;
      opt.textContent = name;
      if (name === activeName) {
        opt.setAttribute("selected", "selected");
      }
      select.appendChild(opt);
    }

    this.switcherContainer.replaceChildren(select);
    this.switcherSelectEl = select;

    select.addEventListener("change", (ev) => {
      const selectedName = ev.target.value;
      const matched = this.productsList.find(
        (p) => (typeof p === "string" ? p : p.name || p.stem) === selectedName
      );
      if (typeof this.options.onSwitchProduct === "function") {
        this.options.onSwitchProduct(matched || selectedName);
      }
      this._dispatchEvent("product-switched", { product: matched || selectedName });
    });
  }

  /**
   * Resets all UI containers to idle state.
   */
  clear() {
    this.currentDocument = null;
    this.instanceMap.clear();
    this.visibilityMap.clear();
    this.isolatedInstanceId = null;
    this.selectedInstanceId = null;
    this.explodedScale = 0.0;

    if (this.treeContainer) this.treeContainer.replaceChildren();
    if (this.summaryContainer) this.summaryContainer.replaceChildren();
    if (this.toolbarContainer) this.toolbarContainer.replaceChildren();
    if (this.switcherContainer) this.switcherContainer.replaceChildren();
    this.clearInspector();

    this.treeListEl = null;
    this.sliderInputEl = null;
    this.sliderValEl = null;
    this.switcherSelectEl = null;
  }

  /**
   * Internal event dispatcher helper.
   *
   * @private
   * @param {string} eventName
   * @param {any} detail
   */
  _dispatchEvent(eventName, detail) {
    const target = this.treeContainer || (this.doc && this.doc.body) || null;
    if (!target || typeof target.dispatchEvent !== "function") return;

    const event = {
      type: eventName,
      detail,
      bubbles: true,
      preventDefault() {},
      stopPropagation() {},
    };
    target.dispatchEvent(event);
    if (!target.parentNode && this.doc && this.doc.body && target !== this.doc.body) {
      this.doc.body.dispatchEvent(event);
    }
  }
}
