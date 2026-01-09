/** @odoo-module **/

const FIELD_WIDGET_SEL = ".o_field_many2many_binary";
const ROW_SEL = "tr.o_data_row";
const ACTIVE_ROW_CLASS = "o_selected_row";
const FIELD_NAME = "attachment_ids";

if (!window.__m2mBinaryDragDropInstalled) {
    window.__m2mBinaryDragDropInstalled = true;

    function hasFiles(ev) {
        const dt = ev.dataTransfer;
        if (!dt) return false;
        return Array.from(dt.types || []).includes("Files");
    }

    function extractFiles(ev) {
        const out = [];
        const dt = ev.dataTransfer;
        if (!dt) return out;

        if (dt.items?.length) {
            for (const item of dt.items) {
                if (item.kind === "file") {
                    const f = item.getAsFile();
                    if (f) out.push(f);
                }
            }
        } else if (dt.files?.length) {
            out.push(...dt.files);
        }
        return out;
    }

    function prevent(ev) {
        ev.preventDefault();
        ev.stopPropagation();
    }

    function findRow(target) {
        return target?.closest?.(ROW_SEL) || null;
    }

    function findFieldElFrom(target) {
        return target?.closest?.(FIELD_WIDGET_SEL) || null;
    }

    function preferredCell(row) {
        if (!row) return null;
        const td = row.querySelector(`td[data-name="${FIELD_NAME}"]`);
        if (td) return td;
        return row.querySelector(FIELD_WIDGET_SEL)?.closest("td") || null;
    }

    function findInput(container) {
        return (
            container?.querySelector?.("input.o_input_file") ||
            container?.querySelector?.("input[type='file']") ||
            null
        );
    }

    function setFilesToInput(input, files) {
        const dt = new DataTransfer();
        for (const f of files) dt.items.add(f);
        input.files = dt.files;
        input.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
    }

    async function wait(ms) {
        return new Promise((r) => setTimeout(r, ms));
    }

    async function ensureReadyInput(evTarget) {
        let fieldEl = findFieldElFrom(evTarget);
        if (fieldEl) {
            const input = findInput(fieldEl);
            if (input) return input;
        }

        const row = findRow(evTarget);
        if (!row) return null;

        const cell = preferredCell(row) || row;

        // ép active row/cell để widget render đúng
        cell.click?.();
        await wait(0);

        for (let i = 0; i < 10; i++) {
            fieldEl =
                cell.querySelector?.(FIELD_WIDGET_SEL) ||
                row.querySelector?.(FIELD_WIDGET_SEL) ||
                null;

            if (fieldEl) {
                const input = findInput(fieldEl);
                if (input) return input;
            }
            await wait(i < 2 ? 0 : 80);
        }

        return null;
    }

    let hoverEl = null;

    // NEW: global drag mode để show “drop zones”
    let dragDepth = 0;
    function setGlobalDragMode(on) {
        document.body.classList.toggle("o_drag_files", !!on);
    }

    document.addEventListener(
        "dragenter",
        (ev) => {
            if (!hasFiles(ev)) return;

            // bật global mode khi file vừa vào cửa sổ
            dragDepth++;
            if (dragDepth === 1) setGlobalDragMode(true);

            const row = findRow(ev.target);
            const fieldEl = findFieldElFrom(ev.target);
            if (!row && !fieldEl) return;

            prevent(ev);

            const el = fieldEl || preferredCell(row) || row;
            if (!el) return;

            if (hoverEl && hoverEl !== el) hoverEl.classList.remove("o_drag_drop_active");
            hoverEl = el;
            hoverEl.classList.add("o_drag_drop_active");
        },
        true
    );

    document.addEventListener(
        "dragover",
        (ev) => {
            if (!hasFiles(ev)) return;

            const row = findRow(ev.target);
            const fieldEl = findFieldElFrom(ev.target);
            if (!row && !fieldEl) return;

            prevent(ev);
            ev.dataTransfer.dropEffect = "copy";
        },
        true
    );

    document.addEventListener(
        "dragleave",
        (ev) => {
            if (!hasFiles(ev)) return;
            prevent(ev);

            // giảm depth; khi ra khỏi window => tắt global mode
            dragDepth = Math.max(0, dragDepth - 1);
            if (dragDepth === 0) {
                setGlobalDragMode(false);
                if (hoverEl) hoverEl.classList.remove("o_drag_drop_active");
                hoverEl = null;
            }
        },
        true
    );

    document.addEventListener(
        "drop",
        async (ev) => {
            if (!hasFiles(ev)) return;

            const row = findRow(ev.target);
            const fieldEl = findFieldElFrom(ev.target);
            if (!row && !fieldEl) return;

            prevent(ev);

            // tắt global mode ngay khi drop
            dragDepth = 0;
            setGlobalDragMode(false);

            if (hoverEl) hoverEl.classList.remove("o_drag_drop_active");
            hoverEl = null;

            const files = extractFiles(ev);
            if (!files.length) return;

            const input = await ensureReadyInput(ev.target);
            if (!input) {
                console.debug("[DD] input file chưa sẵn (row chưa lưu hoặc widget chưa render kịp).");
                return;
            }

            setFilesToInput(input, files);
        },
        true
    );
}
