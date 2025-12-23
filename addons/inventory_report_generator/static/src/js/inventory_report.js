/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { jsonrpc } from "@web/core/network/rpc_service";
import { download } from "@web/core/network/download";

const { Component, onWillStart, useState } = owl;

export class InventoryReport extends Component {
    setup() {
        this.action = useService("action");
        this.orm = useService("orm");

        const now = new Date();
        const nowY = String(now.getFullYear());
        const nowM = String(now.getMonth() + 1);
        const nowQ = String(Math.floor(now.getMonth() / 3) + 1);
        this.defaults = { nowY, nowM, nowQ };

        this.state = useState({
            show_filters: true,
            is_applying: false,
            error: "",
            is_scrolled: false,
            filters: {
                date_from: "",
                date_to: "",
                year: nowY,
                month: "",
                quarter: "",
                location_id: "",
            },
            page: 1,
            page_size: 50,
        });

        this.locations = [];
        this.wizard_id = null;

        this.orders = {};
        this.all_lines = [];
        this.totals = {}; // ✅ NEW

        this._monthKeys = null;
        this._quarterKeys = null;

        onWillStart(async () => {
            await this._initWizard();
            await this._loadFieldMeta();
            await this._loadLocations();
            await this.load_data();
        });
    }

    toggle_filters() {
        this.state.show_filters = !this.state.show_filters;
    }

    async _initWizard() {
        this.wizard_id = await jsonrpc("/web/dataset/call_kw/dynamic.inventory.report/create", {
            model: "dynamic.inventory.report",
            method: "create",
            args: [{}],
            kwargs: {},
        });
    }

    async _loadFieldMeta() {
        const res = await this.orm.call(
            "dynamic.inventory.report",
            "fields_get",
            [["month", "quarter"]],
            { attributes: ["selection"] }
        );
        const monthSel = res?.month?.selection || [];
        const quarterSel = res?.quarter?.selection || [];
        this._monthKeys = new Set(monthSel.map((x) => String(x[0])));
        this._quarterKeys = new Set(quarterSel.map((x) => String(x[0])));
    }

    async _loadLocations() {
        this.locations = await this.orm.searchRead(
            "stock.location",
            [["usage", "=", "internal"]],
            ["id", "complete_name"],
            { order: "complete_name" }
        );
    }

    _pad2(s) {
        return String(s).padStart(2, "0");
    }

    _fmtDateVN(s) {
        if (!s) return "";
        const [yy, mm, dd] = String(s).split("-");
        if (!yy || !mm || !dd) return String(s);
        return `${dd}/${mm}/${yy}`;
    }
    _fmtNum(v, digits = 0) {
        const n = Number(v || 0);
        return new Intl.NumberFormat("vi-VN", {
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
        }).format(Number.isFinite(n) ? n : 0);
    }

    _uiMonthFromServer(v) {
        if (!v) return "";
        const n = parseInt(String(v), 10);
        return Number.isFinite(n) ? String(n) : String(v);
    }

    _normalizeMonthKey(v) {
        if (!v) return false;
        const n = parseInt(String(v), 10);
        if (!Number.isFinite(n)) return false;

        const s1 = String(n);
        const s2 = this._pad2(s1);

        if (this._monthKeys?.has(s1)) return s1;
        if (this._monthKeys?.has(s2)) return s2;
        return s1;
    }

    _normalizeQuarterKey(v) {
        if (!v) return false;
        const n = parseInt(String(v), 10);
        if (!Number.isFinite(n)) return false;
        const s = String(n);
        if (this._quarterKeys?.has(s)) return s;
        return s;
    }

    _rangeText() {
        const df = this.orders?.computed_date_from || "";
        const dt = this.orders?.computed_date_to || "";
        const dfVN = df ? this._fmtDateVN(df) : "";
        const dtVN = dt ? this._fmtDateVN(dt) : "";
        if (dfVN && dtVN) return `${dfVN} → ${dtVN}`;
        if (dfVN) return `Từ ${dfVN}`;
        if (dtVN) return `Đến ${dtVN}`;
        return "";
    }

    onChangeDate() {
        const f = this.state.filters;
        f.year = "";
        f.month = "";
        f.quarter = "";
    }

    onChangeMonth() {
        const f = this.state.filters;
        if (!f.month) return;
        f.quarter = "";
        f.date_from = "";
        f.date_to = "";
        if (!f.year) f.year = this.defaults.nowY;
    }

    onChangeQuarter() {
        const f = this.state.filters;
        if (!f.quarter) return;
        f.month = "";
        f.date_from = "";
        f.date_to = "";
        if (!f.year) f.year = this.defaults.nowY;
    }

    onChangeYear() {
        const f = this.state.filters;
        f.date_from = "";
        f.date_to = "";
    }

    _detectPeriodType() {
        const f = this.state.filters;
        if (f.date_from || f.date_to) return "custom";
        if (f.month) return "month";
        if (f.quarter) return "quarter";
        if (f.year) return "year";
        return "custom";
    }
    onScrollInvrep(ev) {
        const scrolled = ev.target.scrollTop > 2;
        if (this.state.is_scrolled !== scrolled) {
            this.state.is_scrolled = scrolled;
        }
    }

    get filter_label() {
        const o = this.orders || {};
        const pt = String(o.period_type || "custom");

        let locText = "All internal locations";
        const locId = o.location_id ? parseInt(o.location_id, 10) : 0;
        if (locId) {
            const loc = (this.locations || []).find((x) => x.id === locId);
            if (loc) locText = loc.complete_name;
        }

        const range = this._rangeText();

        if (pt === "month") {
            const m = this._uiMonthFromServer(o.month);
            return `Tháng ${m}/${o.year || ""} (${range}) • ${locText}`;
        }
        if (pt === "quarter") return `Quý ${o.quarter || ""}/${o.year || ""} (${range}) • ${locText}`;
        if (pt === "year") return `Năm ${o.year || ""} (${range}) • ${locText}`;

        if (range) return `${range} • ${locText}`;
        return `Toàn bộ thời gian • ${locText}`;
    }

    // Paging
    get total() {
        return this.all_lines?.length || 0;
    }
    get total_pages() {
        const ps = parseInt(this.state.page_size || 50, 10) || 50;
        return Math.max(1, Math.ceil(this.total / ps));
    }
    get current_page() {
        const p = parseInt(this.state.page || 1, 10) || 1;
        return Math.min(Math.max(p, 1), this.total_pages);
    }
    get start_index() {
        const ps = parseInt(this.state.page_size || 50, 10) || 50;
        return (this.current_page - 1) * ps;
    }
    get end_index() {
        const ps = parseInt(this.state.page_size || 50, 10) || 50;
        return Math.min(this.start_index + ps, this.total);
    }
    get paged_lines() {
        return (this.all_lines || []).slice(this.start_index, this.end_index);
    }
    prev_page() {
        if (this.current_page > 1) this.state.page = this.current_page - 1;
    }
    next_page() {
        if (this.current_page < this.total_pages) this.state.page = this.current_page + 1;
    }
    onPageSizeChange() {
        this.state.page_size = parseInt(this.state.page_size || "50", 10) || 50;
        this.state.page = 1;
    }
    goToPage() {
        const p = parseInt(this.state.page || "1", 10) || 1;
        this.state.page = Math.min(Math.max(p, 1), this.total_pages);
    }

    async load_data() {
        const data = await jsonrpc("/web/dataset/call_kw/dynamic.inventory.report/inventory_report", {
            model: "dynamic.inventory.report",
            method: "inventory_report",
            args: [[this.wizard_id]],
            kwargs: {},
        });

        this.orders = data.orders || {};
        this.all_lines = data.report_lines || [];
        this.totals = data.totals || {}; // ✅ NEW
        this.state.page = 1;

        const o = this.orders || {};
        const f = this.state.filters;
        const pt = String(o.period_type || "custom");

        f.location_id = o.location_id ? String(o.location_id) : "";

        if (pt === "month") {
            f.year = o.year ? String(o.year) : this.defaults.nowY;
            f.month = this._uiMonthFromServer(o.month) || this.defaults.nowM;
            f.quarter = "";
            f.date_from = "";
            f.date_to = "";
        } else if (pt === "quarter") {
            f.year = o.year ? String(o.year) : this.defaults.nowY;
            f.quarter = o.quarter ? String(parseInt(String(o.quarter), 10)) : this.defaults.nowQ;
            f.month = "";
            f.date_from = "";
            f.date_to = "";
        } else if (pt === "year") {
            f.year = o.year ? String(o.year) : this.defaults.nowY;
            f.month = "";
            f.quarter = "";
            f.date_from = "";
            f.date_to = "";
        } else {
            f.year = "";
            f.month = "";
            f.quarter = "";
            f.date_from = o.date_from || "";
            f.date_to = o.date_to || "";
        }
    }

    async apply_filter() {
        const f = this.state.filters;
        this.state.error = "";
        this.state.is_applying = true;

        try {
            if (f.date_from && !f.date_to) f.date_to = f.date_from;
            if (f.date_to && !f.date_from) f.date_from = f.date_to;

            if (f.date_from && f.date_to && f.date_from > f.date_to) {
                this.state.error = "Ngày bắt đầu không được lớn hơn ngày kết thúc.";
                return;
            }

            const pt = this._detectPeriodType();

            let yearVal = f.year ? parseInt(String(f.year), 10) : NaN;
            if (!Number.isFinite(yearVal) && (pt === "month" || pt === "quarter" || pt === "year")) {
                yearVal = parseInt(this.defaults.nowY, 10);
                f.year = String(yearVal);
            }

            const monthKey = pt === "month" ? this._normalizeMonthKey(f.month) : false;
            const quarterKey = pt === "quarter" ? this._normalizeQuarterKey(f.quarter) : false;

            const filter_data = {
                period_type: pt,
                year: (pt !== "custom" && Number.isFinite(yearVal)) ? yearVal : false,
                month: monthKey,
                quarter: quarterKey,
                date_from: pt === "custom" ? (f.date_from || false) : false,
                date_to: pt === "custom" ? (f.date_to || false) : false,
                location_id: f.location_id ? parseInt(String(f.location_id), 10) : false,
            };

            await jsonrpc("/web/dataset/call_kw/dynamic.inventory.report/write", {
                model: "dynamic.inventory.report",
                method: "write",
                args: [[this.wizard_id], filter_data],
                kwargs: {},
            });

            await this.load_data();
        } catch (e) {
            this.state.error = (e && e.message) ? e.message : "Có lỗi khi áp dụng bộ lọc.";
            throw e;
        } finally {
            this.state.is_applying = false;
        }
    }

    async reset_filters() {
        const f = this.state.filters;
        f.date_from = "";
        f.date_to = "";
        f.year = this.defaults.nowY;
        f.month = "";
        f.quarter = "";
        f.location_id = "";
        await this.apply_filter();
    }

    async print_pdf(e) {
        e.preventDefault();
        const data = await jsonrpc("/web/dataset/call_kw/dynamic.inventory.report/inventory_report", {
            model: "dynamic.inventory.report",
            method: "inventory_report",
            args: [[this.wizard_id]],
            kwargs: {},
        });

        return this.action.doAction({
            type: "ir.actions.report",
            report_type: "qweb-pdf",
            report_name: "inventory_report_generator.inventory_pdf_report",
            report_file: "inventory_report_generator.inventory_pdf_report",
            data: { report_data: data },
            context: {
                active_model: "dynamic.inventory.report",
                landscape: 1,
                inventory_pdf_report: true,
            },
            display_name: "Inventory Report",
        });
    }

    async print_xlsx() {
        const data = await jsonrpc("/web/dataset/call_kw/dynamic.inventory.report/inventory_report", {
            model: "dynamic.inventory.report",
            method: "inventory_report",
            args: [[this.wizard_id]],
            kwargs: {},
        });

        await download({
            url: "/inventory_dynamic_xlsx_reports",
            data: {
                model: "dynamic.inventory.report",
                options: JSON.stringify(data.orders),
                output_format: "xlsx",
                report_data: JSON.stringify(data.report_lines),
                report_name: "Inventory Report",
                dfr_data: JSON.stringify(data), // ✅ có totals bên trong
            },
        });
    }
}

InventoryReport.template = "InventoryReport";
registry.category("actions").add("inv_r", InventoryReport);
