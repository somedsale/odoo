/** @odoo-module **/

import { localization as l10n } from "@web/core/l10n/localization";

const TAG = "[SOMED-REALTIME-NUMFMT]";

if (!window.__SOMED_REALTIME_NUMFMT__) {
    window.__SOMED_REALTIME_NUMFMT__ = true;

    const NBSP = "\u00A0";
    const NNBSP = "\u202F";

    const esc = (x) => String(x ?? "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

    function getSep() {
        const decimalPoint = l10n.decimalPoint || ".";
        const thousandsSep =
            l10n.thousandsSep !== undefined && l10n.thousandsSep !== null
                ? l10n.thousandsSep
                : ",";
        return { decimalPoint, thousandsSep };
    }

    function findNumericRoot(inputEl) {
        return inputEl?.closest?.(
            ".o_field_float, .o_field_integer, .o_field_monetary, .o_field_number, .o_field_widget"
        );
    }

    function isProbablyNumericByValue(v) {
        const s = String(v ?? "");
        // chỉ số + dấu cách + dấu phân cách + dấu trừ
        return /^[0-9\s\-\.,\u00A0\u202F]*$/.test(s) && /[0-9]/.test(s);
    }

    function isNumericFieldInput(inputEl) {
        if (!inputEl || inputEl.tagName !== "INPUT") return false;
        if (inputEl.readOnly || inputEl.disabled) return false;

        // 1) wrapper chuẩn
        const root = inputEl.closest(".o_field_float, .o_field_integer, .o_field_monetary, .o_field_number");
        if (root) return true;

        // 2) list editable: thường có o_input + inputmode
        const im = inputEl.getAttribute("inputmode");
        if (inputEl.classList.contains("o_input") && (im === "numeric" || im === "decimal")) return true;

        // 3) input number chắc chắn là số
        if (inputEl.type === "number") return true;

        // 4) fallback theo nội dung đang gõ
        return isProbablyNumericByValue(inputEl.value);
    }

    function isIntegerField(inputEl) {
        const root = findNumericRoot(inputEl);
        if (root && root.classList.contains("o_field_integer")) return true;

        // fallback: inputmode numeric coi như integer
        return inputEl.getAttribute("inputmode") === "numeric";
    }

    function normalizeInputType(inputEl) {
        // type=number => browser không cho hiển thị separators
        if (inputEl.type === "number") {
            try { inputEl.type = "text"; } catch (_) { }
        }
        inputEl.setAttribute("inputmode", isIntegerField(inputEl) ? "numeric" : "decimal");
    }

    function stripToNumeric(str, allowDecimal = true) {
        if (str === null || str === undefined) return "";
        const { decimalPoint, thousandsSep } = getSep();

        let s = String(str);

        // remove whitespace (space + nbsp + nnbsp)
        s = s.replaceAll(" ", "")
            .replaceAll(NBSP, "")
            .replaceAll(NNBSP, "")
            .replace(/\s+/g, "");

        const neg = s.startsWith("-");
        if (neg) s = s.slice(1);

        if (thousandsSep) {
            s = s.replace(new RegExp(esc(thousandsSep), "g"), "");
        }

        const allowed = allowDecimal ? decimalPoint : "";
        s = s.replace(new RegExp(`[^0-9${esc(allowed)}]`, "g"), "");

        // only 1 decimalPoint
        if (allowDecimal && decimalPoint) {
            const i = s.indexOf(decimalPoint);
            if (i >= 0) {
                const head = s.slice(0, i);
                const tail = s.slice(i + 1).replaceAll(decimalPoint, "");
                s = head + decimalPoint + tail;
            }
        }

        return (neg ? "-" : "") + s;
    }

    function formatThousands(raw, allowDecimal = true, keepTrailingDecimal = false) {
        const { decimalPoint, thousandsSep } = getSep();
        if (raw === "" || raw === "-") return raw;

        let s = String(raw);
        const neg = s.startsWith("-");
        if (neg) s = s.slice(1);

        let intPart = s;
        let decPart = "";

        if (allowDecimal && decimalPoint) {
            const i = s.indexOf(decimalPoint);
            if (i >= 0) {
                intPart = s.slice(0, i);
                decPart = s.slice(i + 1);
            }
        }

        const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, thousandsSep);

        if (!allowDecimal || !decimalPoint) {
            return (neg ? "-" : "") + grouped;
        }

        if (decPart !== "" || keepTrailingDecimal) {
            return (neg ? "-" : "") + grouped + decimalPoint + decPart;
        }
        return (neg ? "-" : "") + grouped;
    }

    // caret helpers
    function countSigLeft(str, pos, decimalPoint) {
        let c = 0;
        for (let i = 0; i < Math.min(pos, str.length); i++) {
            const ch = str[i];
            if ((ch >= "0" && ch <= "9") || ch === decimalPoint || ch === "-") c++;
        }
        return c;
    }

    function posForSigCount(str, sigCount, decimalPoint) {
        if (sigCount <= 0) return 0;
        let c = 0;
        for (let i = 0; i < str.length; i++) {
            const ch = str[i];
            if ((ch >= "0" && ch <= "9") || ch === decimalPoint || ch === "-") c++;
            if (c >= sigCount) return i + 1;
        }
        return str.length;
    }

    function safeSetSelectionRange(input, start, end) {
        try {
            if (typeof input.setSelectionRange === "function" && input.type !== "number") {
                input.setSelectionRange(start, end);
            }
        } catch (_) { }
    }

    // run AFTER OWL render
    function afterOwl(cb) {
        setTimeout(() => requestAnimationFrame(cb), 0);
    }

    function applyFormatAfterOwl(input, startSig, endSig, allowDecimal, keepTrailingDecimal) {
        afterOwl(() => {
            if (!document.contains(input)) return;
            if (input.__somed_numfmt_lock2) return;

            input.__somed_numfmt_lock2 = true;
            try {
                const { decimalPoint } = getSep();

                const cur = input.value ?? "";
                const keep2 = allowDecimal && decimalPoint && cur.endsWith(decimalPoint);

                const raw2 = stripToNumeric(cur, allowDecimal);
                const fmt2 = formatThousands(raw2, allowDecimal, keep2 || keepTrailingDecimal);

                input.value = fmt2;

                const newStart = posForSigCount(fmt2, startSig, decimalPoint);
                const newEnd = posForSigCount(fmt2, endSig, decimalPoint);
                safeSetSelectionRange(input, newStart, newEnd);
            } finally {
                input.__somed_numfmt_lock2 = false;
            }
        });
    }

    // =========================
    // EVENTS
    // =========================

    document.addEventListener("focusin", (ev) => {
        const input = ev.target;
        if (!isNumericFieldInput(input)) return;
        normalizeInputType(input);

        const { decimalPoint } = getSep();
        const allowDecimal = !isIntegerField(input);

        const before = input.value ?? "";
        const keepTrailingDecimal = allowDecimal && decimalPoint && before.endsWith(decimalPoint);

        afterOwl(() => {
            if (!document.contains(input)) return;
            const raw = stripToNumeric(input.value ?? "", allowDecimal);
            input.value = formatThousands(raw, allowDecimal, keepTrailingDecimal);
        });
    }, true);

    document.addEventListener("input", (ev) => {
        if (ev.isComposing) return;

        const input = ev.target;
        if (!isNumericFieldInput(input)) return;
        normalizeInputType(input);

        if (input.__somed_numfmt_lock) return;

        const { decimalPoint } = getSep();
        const allowDecimal = !isIntegerField(input);

        const before = input.value ?? "";
        const selStart = input.selectionStart ?? before.length;
        const selEnd = input.selectionEnd ?? before.length;

        const keepTrailingDecimal = allowDecimal && decimalPoint && before.endsWith(decimalPoint);

        const raw = stripToNumeric(before, allowDecimal);

        const startSig = countSigLeft(before, selStart, decimalPoint);
        const endSig = countSigLeft(before, selEnd, decimalPoint);

        // 1) set RAW cho Odoo đọc
        input.__somed_numfmt_lock = true;
        input.value = raw;

        const rawStart = posForSigCount(raw, startSig, decimalPoint);
        const rawEnd = posForSigCount(raw, endSig, decimalPoint);
        safeSetSelectionRange(input, rawStart, rawEnd);

        // 2) sau OWL render xong -> format lại UI
        applyFormatAfterOwl(input, startSig, endSig, allowDecimal, keepTrailingDecimal);

        afterOwl(() => { input.__somed_numfmt_lock = false; });
    }, true);

    document.addEventListener("blur", (ev) => {
        const input = ev.target;
        if (!isNumericFieldInput(input)) return;

        const allowDecimal = !isIntegerField(input);
        input.value = stripToNumeric(input.value ?? "", allowDecimal);
    }, true);
}
