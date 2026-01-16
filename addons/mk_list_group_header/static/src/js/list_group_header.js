/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";
import { onMounted, onPatched, onWillUnmount } from "@odoo/owl";

const DEBUG = true;
const TAG = "[MK-GROUP-HEADER]";
// const TARGET_MODEL = "project.profit.lost";

const ROOT_CLASS = "mk_pl_2header";
const ROW_CLASS = "mk_group_header_row";
const STYLE_ID = "mk_pl_2header_style";


function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
  /* 1) Tắt transition top của o_mobile_sticky để khỏi “hở” khi scroll */
  .${ROOT_CLASS} .o_mobile_sticky{
    transition: none !important;
  }

  /* 2) Ép nền cho cả 2 tầng header để không bị “trong suốt” */
  .${ROOT_CLASS} table.o_list_table thead tr.${ROW_CLASS},
  .${ROOT_CLASS} table.o_list_table thead tr.${ROW_CLASS} th,
  .${ROOT_CLASS} table.o_list_table thead tr:not(.${ROW_CLASS}) th{
    background: var(--ListRenderer-thead-bg-color) !important;
    background-clip: padding-box;
  }
  /* 3) Kẻ line giữa tầng 1 và tầng 2 */
  .${ROOT_CLASS} table.o_list_table thead tr.${ROW_CLASS} th{
    border-bottom: 1px solid var(--border-color-light) !important;
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

/* ===================== ✅ READ ONLY FROM archInfo.columns ===================== */
/**
 * Đây mới là “chỗ đọc options” đúng nhất trong ListRenderer.
 * options thường nằm ở:
 *  - col.attrs.options  (đa số)
 *  - hoặc col.options
 */
function getColumns(renderer) {
    return (
        renderer?.props?.archInfo?.columns ||
        renderer?.props?.list?.archInfo?.columns ||
        renderer?.props?.columns ||
        renderer?.columns ||
        []
    );
}

function getFieldName(col) {
    return col?.name || col?.fieldName || col?.attrs?.name || col?.field?.name || null;
}
function log(...args) {
    if (!DEBUG) return;
    console.log(TAG, ...args);
}

function buildGroupMapFromColumns(renderer) {
    const cols = getColumns(renderer);
    const map = {};

    for (const c of cols) {
        const name = getFieldName(c);
        if (!name) continue;
        const optRaw =
            c?.attrs?.options ??
            c?.options ??
            c?.field?.options ??
            c?.field?.attrs?.options ??
            null;

        const opt = parseOptions(optRaw);
        const hg = opt?.header_group || opt?.headerGroup;

        if (hg) map[name] = hg;
    }

    // DEBUG: show nơi options nằm
    if (DEBUG && !renderer.__mkDumpedCols) {
        renderer.__mkDumpedCols = true;
        try {
            console.table(
                cols
                    .map((c) => {
                        const name = getFieldName(c);
                        const raw = c?.attrs?.options ?? c?.options ?? c?.field?.options ?? c?.field?.attrs?.options ?? null;
                        const parsed = parseOptions(raw);
                        return {
                            field: name,
                            raw_options: typeof raw === "string" ? raw : raw ? "[object]" : "",
                            header_group: parsed?.header_group || parsed?.headerGroup || "",
                            where:
                                c?.attrs?.options != null ? "col.attrs.options" :
                                    c?.options != null ? "col.options" :
                                        c?.field?.options != null ? "col.field.options" :
                                            c?.field?.attrs?.options != null ? "col.field.attrs.options" :
                                                "",
                        };
                    })
                    .filter((x) => x.field)
            );
        } catch (e) {
            log("console.table failed", e);
        }
    }

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
    th.removeAttribute("data-name");
}

function cloneEmptyCell(refTh) {
    const th = refTh.cloneNode(false);
    stripInteractiveAttrs(th);
    th.textContent = "";
    th.style.pointerEvents = "none";
    return th;
}

function cloneGroupCell(refDataTh, label, colspan) {
    const th = refDataTh.cloneNode(false);
    stripInteractiveAttrs(th);
    th.removeAttribute("style"); // tránh ảnh hưởng width/sticky inline
    th.colSpan = colspan;
    th.textContent = label || "";
    th.style.textAlign = "center";
    th.style.fontWeight = "600";
    th.style.pointerEvents = "none";
    return th;
}

function rowSignature(row) {
    if (!row) return "";
    const ths = Array.from(row.children).filter((n) => n.tagName === "TH");
    return ths.map((th) => `${(th.textContent || "").trim()}@${th.colSpan || 1}`).join("|");
}

function getRendererTable(renderer) {
    // renderer.el đôi khi là .o_list_renderer, table nằm trong đó
    const root =
        renderer?.el?.closest?.(".o_list_view") ||
        renderer?.el?.closest?.(".o_list_renderer") ||
        renderer?.el ||
        null;

    const table =
        root?.querySelector?.("table.o_list_table") ||
        renderer?.el?.querySelector?.("table.o_list_table") ||
        null;

    return { root, table };
}

// fallback chỉ để tìm TABLE khi renderer.el chưa sẵn
function isVisible(el) {
    return !!(el && el.getClientRects && el.getClientRects().length);
}
function findVisibleListTables() {
    const listViews = Array.from(document.querySelectorAll(".o_list_view")).filter(isVisible);
    return listViews
        .map((lv) => ({ root: lv, table: lv.querySelector("table.o_list_table") }))
        .filter((x) => x.table);
}

/* ===================== INSERT GROUP ROW ===================== */

function insertOrReplaceGroupRow(groupMap, root, table) {
    const thead = table.querySelector("thead");
    if (!thead) return false;

    const headerRow = thead.querySelector(`tr:not(.${ROW_CLASS})`);
    if (!headerRow) return false;

    const cells = Array.from(headerRow.children).filter((n) => n.tagName === "TH");
    if (!cells.length) return false;

    const firstData = cells.findIndex(isDataCell);
    const lastDataFromRight = [...cells].reverse().findIndex(isDataCell);
    const lastData = lastDataFromRight === -1 ? -1 : (cells.length - 1 - lastDataFromRight);
    if (firstData === -1 || lastData === -1 || lastData < firstData) return false;

    // ✅ BẮT BUỘC: phải đọc được từ options (columns)
    if (!groupMap || !Object.keys(groupMap).length) return false;

    root?.classList?.add(ROOT_CLASS);

    // const h = Math.round(headerRow.getBoundingClientRect().height || 32);
    // table.style.setProperty("--mk-group-h", `${h}px`);

    const groups = [];
    let cur = null;

    for (let i = firstData; i <= lastData; i++) {
        const th = cells[i];
        const field = th.getAttribute("data-name");
        const label = groupMap[field] || ""; // field không có option -> rỗng
        const span = th.colSpan || 1;

        if (!cur || cur.label !== label) {
            cur = { label, span, ref: th };
            groups.push(cur);
        } else {
            cur.span += span;
        }
    }

    // nếu tất cả label rỗng -> coi như options chưa ăn -> không chèn
    if (!groups.some((g) => (g.label || "").trim())) return false;

    const existing = thead.querySelector(`tr.${ROW_CLASS}`);

    const tr = headerRow.cloneNode(false);
    tr.classList.add(ROW_CLASS);

    for (let i = 0; i < firstData; i++) tr.appendChild(cloneEmptyCell(cells[i]));
    for (const g of groups) tr.appendChild(cloneGroupCell(g.ref, g.label, g.span));
    for (let i = lastData + 1; i < cells.length; i++) tr.appendChild(cloneEmptyCell(cells[i]));

    const newSig = rowSignature(tr);
    const oldSig = rowSignature(existing);
    if (existing && newSig === oldSig) {
        const gh = Math.round(existing.getBoundingClientRect().height || 32);
        table.style.setProperty("--mk-group-h", `${gh}px`);
        return true;
    }

    if (existing && existing.parentNode === thead) existing.replaceWith(tr);
    else thead.insertBefore(tr, headerRow);
    const gh = Math.round(tr.getBoundingClientRect().height || 32);
    table.style.setProperty("--mk-group-h", `${gh}px`);

    return true;
}

/* ===================== PATCH LIFECYCLE ===================== */

const originalSetup = ListRenderer.prototype.setup;

patch(ListRenderer.prototype, {
    setup() {
        originalSetup.call(this);

        ensureStyle();

        this.__mkScheduled = false;
        const scheduleRefresh = () => {
            if (this.__mkScheduled) return;
            this.__mkScheduled = true;

            requestAnimationFrame(() => {
                this.__mkScheduled = false;

                // ✅ map chỉ từ options columns
                const map = buildGroupMapFromColumns(this);

                let ok = false;
                const { root, table } = getRendererTable(this);
                if (root && table) ok = insertOrReplaceGroupRow(map, root, table);

                if (!ok) {
                    const tables = findVisibleListTables();
                    for (const t of tables) ok = insertOrReplaceGroupRow(map, t.root, t.table) || ok;
                }

                if (!ok) log("no insert (options chưa tới được columns OR table chưa sẵn)");
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
            };
            tick();
        };

        onMounted(runWithRetry);

        onPatched(() => {
            ensureObserver();
            scheduleRefresh();
        });

        let resizeTimer = null;
        const onResize = () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => scheduleRefresh(), 60);
        };

        onMounted(() => window.addEventListener("resize", onResize, { passive: true }));

        onWillUnmount(() => {
            window.removeEventListener("resize", onResize);
            if (this.__mkObserver) this.__mkObserver.disconnect();
            this.__mkObserver = null;
            this.__mkThead = null;
            this.__mkDumpedCols = null;
        });
    },
});
