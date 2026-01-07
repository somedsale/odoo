/** @odoo-module **/

/**
 * Drag & Drop upload cho widget many2many_binary (đặc biệt trong tree/list view)
 * - Kéo thả file vào ô "Tệp đính kèm" sẽ tự upload như bấm chọn file
 */

const FIELD_SELECTOR = ".o_field_many2many_binary";

function hasFiles(ev) {
    const dt = ev.dataTransfer;
    if (!dt) return false;
    // Chrome/Edge: types thường có "Files"
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

function findFieldEl(target) {
    return target?.closest?.(FIELD_SELECTOR) || null;
}

function findInput(fieldEl) {
    return (
        fieldEl.querySelector("input.o_input_file") ||
        fieldEl.querySelector("input[type='file']") ||
        null
    );
}

async function ensureInput(fieldEl) {
    let input = findInput(fieldEl);
    if (input) return input;

    // Thử click nút trong field để widget render input (nếu có)
    const btn =
        fieldEl.querySelector("button") ||
        fieldEl.closest("button");

    if (btn) btn.click();

    // chờ 1 tick
    await new Promise((r) => setTimeout(r, 0));
    return findInput(fieldEl);
}

function setFilesToInput(input, files) {
    const dt = new DataTransfer();
    for (const f of files) dt.items.add(f);
    input.files = dt.files;
    input.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
}

let lastHoverEl = null;

function onDragEnter(ev) {
    if (!hasFiles(ev)) return;
    const fieldEl = findFieldEl(ev.target);
    if (!fieldEl) return;

    ev.preventDefault();
    ev.stopPropagation();

    if (lastHoverEl && lastHoverEl !== fieldEl) {
        lastHoverEl.classList.remove("o_drag_drop_active");
    }
    lastHoverEl = fieldEl;
    fieldEl.classList.add("o_drag_drop_active");
}

function onDragOver(ev) {
    if (!hasFiles(ev)) return;
    const fieldEl = findFieldEl(ev.target);
    if (!fieldEl) return;

    ev.preventDefault();
    ev.stopPropagation();
    ev.dataTransfer.dropEffect = "copy";
}

function onDragLeave(ev) {
    if (!hasFiles(ev)) return;
    const fieldEl = findFieldEl(ev.target);
    if (!fieldEl) return;

    ev.preventDefault();
    ev.stopPropagation();

    // chỉ bỏ highlight khi rời đúng field đó
    fieldEl.classList.remove("o_drag_drop_active");
    if (lastHoverEl === fieldEl) lastHoverEl = null;
}

async function onDrop(ev) {
    if (!hasFiles(ev)) return;

    const fieldEl = findFieldEl(ev.target);
    if (!fieldEl) return;

    ev.preventDefault();
    ev.stopPropagation();

    fieldEl.classList.remove("o_drag_drop_active");
    if (lastHoverEl === fieldEl) lastHoverEl = null;

    const files = extractFiles(ev);
    if (!files.length) return;

    const input = await ensureInput(fieldEl);
    if (!input) {
        console.warn("[m2m_binary_dragdrop] Không tìm thấy input[type=file] trong field many2many_binary.");
        return;
    }

    setFilesToInput(input, files);
}

// Gắn listener toàn trang (capture) để không bị list view nuốt event
document.addEventListener("dragenter", onDragEnter, true);
document.addEventListener("dragover", onDragOver, true);
document.addEventListener("dragleave", onDragLeave, true);
document.addEventListener("drop", onDrop, true);
