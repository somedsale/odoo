/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";
import { onMounted, onPatched, onWillUnmount } from "@odoo/owl";

const DEBUG = true;
const TAG = "[MK-GROUP-HEADER]";
const TARGET_MODEL = "project.profit.lost";

const ROOT_CLASS = "mk_pl_2header";
const ROW_CLASS = "mk_group_header_row";
const STYLE_ID = "mk_pl_2header_style";

function log(...a) { if (DEBUG) console.log(TAG, ...a); }
function warn(...a) { if (DEBUG) console.warn(TAG, ...a); }

function ensureStyle() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .${ROOT_CLASS} table.o_list_table { --mk-group-h: 32px; }
    .${ROOT_CLASS} table.o_list_table thead tr.${ROW_CLASS} th{
      top: 0 !important;
      z-index: 6;
      background: var(--o-view-background-color, #fff);
    }
    .${ROOT_CLASS} table.o_list_table thead tr:not(.${ROW_CLASS}) th{
      top: var(--mk-group-h) !important;
    }
  `;
  document.head.appendChild(style);
}

function getResModel(renderer) {
  const p = renderer?.props;
  return (
    p?.list?.resModel ||
    p?.resModel ||
    p?.list?.model?.root?.resModel ||
    p?.model?.root?.resModel ||
    p?.list?.model?.config?.resModel ||
    p?.model?.config?.resModel ||
    null
  );
}

function parseOptions(opts) {
  if (!opts) return null;
  if (typeof opts === "object") return opts;
  if (typeof opts === "string") {
    const s = opts
      .trim()
      .replace(/None/g, "null")
      .replace(/True/g, "true")
      .replace(/False/g, "false")
      .replace(/'/g, '"');
    try { return JSON.parse(s); } catch { return null; }
  }
  return null;
}

/* ===================== READ ONLY FROM ARCH (XML) ===================== */

function getArchRoot(renderer) {
  return renderer?.props?.archInfo?.arch || renderer?.props?.list?.archInfo?.arch || null;
}

function walkArch(node, cb) {
  if (!node) return;
  if (Array.isArray(node)) { node.forEach((n) => walkArch(n, cb)); return; }

  cb(node);

  const kids = node.children || node.childNodes || node.content || node.nodes || [];
  const arr = Array.isArray(kids) ? kids : Array.from(kids || []);
  arr.forEach((ch) => walkArch(ch, cb));
}

function buildGroupMapFromArch(renderer) {
  const arch = getArchRoot(renderer);
  const map = {};
  if (!arch) return map;

  walkArch(arch, (node) => {
    const tag = (node.tag || node.tagName || "").toLowerCase();
    if (tag !== "field") return;

    const attrs = node.attrs || node.attributes || {};
    const name =
      attrs.name ||
      node.name ||
      node.getAttribute?.("name") ||
      null;

    const optsRaw =
      attrs.options ||
      node.getAttribute?.("options") ||
      null;

    const opt = parseOptions(optsRaw);
    const hg = opt?.header_group || opt?.headerGroup;
    if (name && hg) map[name] = hg;
  });

  return map;
}

/* ===================== DOM HELPERS ===================== */

function isDataCell(th) {
  return th?.tagName === "TH" && th.hasAttribute("data-name");
}

function stripInteractiveAttrs(th) {
  th.removeAttribute("data-tooltip");
  th.removeAttribute("tabindex");
  th.removeAttribute("role");
  th.removeAttribute("aria-label");
  th.removeAttribute("rowspan");
  th.removeAttribute("data-name"); // group row bỏ data-name
}

function cloneEmptyCell(refTh) {
  const th = refTh.cloneNode(false); // giữ sticky/class/style cho cột special
  stripInteractiveAttrs(th);
  th.textContent = "";
  return th;
}

function cloneGroupCell(refDataTh, label, colspan) {
  const th = refDataTh.cloneNode(false); // giữ class/padding giống Odoo
  stripInteractiveAttrs(th);

  // IMPORTANT: group row không được mang width/sticky inline style của cột data
  th.removeAttribute("style");

  th.colSpan = colspan;
  th.textContent = label || "";
  th.style.textAlign = "center";
  th.style.fontWeight = "600";
  return th;
}

function rowSignature(row) {
  if (!row) return "";
  const ths = Array.from(row.children).filter((n) => n.tagName === "TH");
  return ths.map((th) => `${(th.textContent || "").trim()}@${th.colSpan || 1}`).join("|");
}

function getRendererTable(renderer) {
  const root =
    renderer?.el?.closest?.(".o_list_view") ||
    renderer?.el?.closest?.(".o_list_renderer") ||
    renderer?.el ||
    null;

  const table = root?.querySelector?.("table.o_list_table") || null;
  return { root, table };
}

// (fallback chỉ để tìm TABLE khi this.el chưa kịp có; KHÔNG fallback group label)
function isVisible(el) {
  return !!(el && el.getClientRects && el.getClientRects().length);
}
function findProfitLostTablesBySignature() {
  const listViews = Array.from(document.querySelectorAll(".o_list_view")).filter(isVisible);
  const out = [];
  for (const lv of listViews) {
    const table = lv.querySelector("table.o_list_table");
    if (!table) continue;

    const hasProject = !!table.querySelector('thead th[data-name="project_id"]');
    const hasProfit = !!table.querySelector('thead th[data-name="profit"]');
    const hasRevenue = !!table.querySelector('thead th[data-name="revenue"]');

    if ([hasProject, hasProfit, hasRevenue].filter(Boolean).length >= 2) {
      out.push({ root: lv, table });
    }
  }
  return out;
}

/* ===================== INSERT GROUP ROW ===================== */

function insertOrReplaceGroupRow(groupMap, root, table) {
  const thead = table.querySelector("thead");
  if (!thead) return false;

  // header gốc: lấy tr KHÔNG phải group row
  const headerRow = thead.querySelector(`tr:not(.${ROW_CLASS})`);
  if (!headerRow) return false;

  const cells = Array.from(headerRow.children).filter((n) => n.tagName === "TH");
  if (!cells.length) return false;

  const firstData = cells.findIndex(isDataCell);
  const lastDataFromRight = [...cells].reverse().findIndex(isDataCell);
  const lastData = lastDataFromRight === -1 ? -1 : (cells.length - 1 - lastDataFromRight);
  if (firstData === -1 || lastData === -1 || lastData < firstData) return false;

  // BẮT BUỘC: phải có ít nhất 1 header_group từ option
  if (!groupMap || !Object.keys(groupMap).length) return false;

  // scope css
  root?.classList?.add(ROOT_CLASS);

  // set top offset theo chiều cao header gốc
  const h = Math.round(headerRow.getBoundingClientRect().height || 32);
  table.style.setProperty("--mk-group-h", `${h}px`);

  // build groups theo thứ tự cột đang render
  const groups = [];
  let cur = null;

  for (let i = firstData; i <= lastData; i++) {
    const th = cells[i];
    const field = th.getAttribute("data-name");
    const label = groupMap[field] || ""; // field không có option => rỗng
    const span = th.colSpan || 1;

    if (!cur || cur.label !== label) {
      cur = { label, span, ref: th };
      groups.push(cur);
    } else {
      cur.span += span;
    }
  }

  // nếu tất cả label đều rỗng => coi như không có option => không chèn
  if (!groups.some((g) => (g.label || "").trim())) return false;

  const existing = thead.querySelector(`tr.${ROW_CLASS}`);

  const tr = headerRow.cloneNode(false);
  tr.classList.add(ROW_CLASS);

  // left special
  for (let i = 0; i < firstData; i++) tr.appendChild(cloneEmptyCell(cells[i]));
  // group cells
  for (const g of groups) tr.appendChild(cloneGroupCell(g.ref, g.label, g.span));
  // right special
  for (let i = lastData + 1; i < cells.length; i++) tr.appendChild(cloneEmptyCell(cells[i]));

  // chống nháy: nếu giống y chang thì khỏi replace
  const newSig = rowSignature(tr);
  const oldSig = rowSignature(existing);
  if (existing && newSig === oldSig) return true;

  if (existing && existing.parentNode === thead) existing.replaceWith(tr);
  else thead.insertBefore(tr, headerRow);

  return true;
}

/* ===================== PATCH LIFECYCLE ===================== */

const originalSetup = ListRenderer.prototype.setup;

patch(ListRenderer.prototype, {
  setup() {
    originalSetup.call(this);

    const resModel = getResModel(this);
    log("loaded", { resModel });
    if (resModel !== TARGET_MODEL) return;

    ensureStyle();

    // cache groupMap (đọc từ ARCH)
    this.__mkGroupMap = null;
    const getMap = () => {
      if (this.__mkGroupMap) return this.__mkGroupMap;
      const map = buildGroupMapFromArch(this);
      this.__mkGroupMap = map;
      log("groupMap FROM ARCH", map);
      return map;
    };

    this.__mkScheduled = false;
    const scheduleRefresh = () => {
      if (this.__mkScheduled) return;
      this.__mkScheduled = true;

      requestAnimationFrame(() => {
        this.__mkScheduled = false;

        const map = getMap();
        let ok = false;

        // 1) try theo renderer el
        const { root, table } = getRendererTable(this);
        if (root && table) ok = insertOrReplaceGroupRow(map, root, table);

        // 2) fallback chỉ để tìm table (không fallback label)
        if (!ok) {
          const tables = findProfitLostTablesBySignature();
          for (const t of tables) ok = insertOrReplaceGroupRow(map, t.root, t.table) || ok;
        }

        if (!ok) log("no insert (options not found OR table not ready)");
      });
    };

    const ensureObserver = () => {
      const { table } = getRendererTable(this);
      const thead = table?.querySelector("thead");
      if (!thead) return false;

      if (this.__mkThead === thead && this.__mkObserver) return true;

      if (this.__mkObserver) this.__mkObserver.disconnect();
      this.__mkThead = thead;

      this.__mkObserver = new MutationObserver(() => scheduleRefresh());
      this.__mkObserver.observe(thead, { childList: true, subtree: true });
      return true;
    };

    const runWithRetry = () => {
      let tries = 0;
      const tick = () => {
        tries++;
        scheduleRefresh();
        if (ensureObserver()) return;
        if (tries < 30) setTimeout(tick, 50);
        else warn("cannot attach observer yet (table not stable)");
      };
      tick();
    };

    onMounted(runWithRetry);
    onPatched(() => {
      // cột ẩn/hiện thay đổi => đọc lại ARCH map
      this.__mkGroupMap = null;
      ensureObserver();
      scheduleRefresh();
    });

    let resizeTimer = null;
    const onResize = () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => scheduleRefresh(), 80);
    };

    onMounted(() => window.addEventListener("resize", onResize, { passive: true }));
    onWillUnmount(() => {
      window.removeEventListener("resize", onResize);
      if (this.__mkObserver) this.__mkObserver.disconnect();
      this.__mkObserver = null;
      this.__mkThead = null;
      this.__mkGroupMap = null;
    });
  },
});
