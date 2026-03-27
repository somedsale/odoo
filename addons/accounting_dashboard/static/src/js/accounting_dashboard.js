/** @odoo-module **/

import { Component, onWillStart, onMounted, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const STORAGE_KEY = "ad_accounting_dashboard_filters_v5";

const fmtVND = (n) => `${(Number(n) || 0).toLocaleString("vi-VN")} đ`;
const fmtDate = (dateStr) => {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (isNaN(d)) return dateStr;
  return d.toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
};

class AccountingDashboard extends Component {
  static template = "ad.AccountingDashboard";

  setup() {
    this.orm = useService("orm");
    this.action = useService("action");
    this.notification = useService("notification");

    this.fmtVND = fmtVND;
    this.fmtDate = fmtDate;

    const today = new Date();
    const toISO = (d) => this._toISODateLocal(d);

    this.state = useState({
      filters: {
        period_type: "custom", // custom | month | quarter | year
        year: String(today.getFullYear()),
        month: String(today.getMonth() + 1).padStart(2, "0"),
        quarter: String(Math.floor(today.getMonth() / 3) + 1),
        date_from: toISO(new Date(today.getTime() - 29 * 24 * 3600 * 1000)),
        date_to: toISO(today),
      },
      kpis: {
        cash_in: "0 ₫",
        cash_out: "0 ₫",
        net_cash: "0 ₫",
        advance_remain_total: "0 ₫",
        total_supplier_invoice: "0 ₫",
        total_customer_invoice: "0 ₫",
      },
      employees_with_remain: [],
      proposal_pending_count: 0,
      payment_proposals_pending_count: 0,
      daily_cash_flow: [],
      supplier_invoices: [],
      customer_invoices: [],
    });

    this.remainChartRef = useRef("remainChart");
    this.dailyFlowChartRef = useRef("dailyFlowChart");
    this._charts = { remain: null, dailyFlow: null };
    this._rendering = false;

    this._restoreFiltersFromStorage();
    this._syncDatesFromPreset(false);

    onWillStart(async () => await this.fetchData());
    onMounted(() => this.renderCharts());
  }

  // -----------------------------
  // Date utils
  // -----------------------------
  _toISODateLocal(date) {
    if (!(date instanceof Date) || isNaN(date.getTime())) return "";
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  }

  _getPeriodRange(periodType, year, month, quarter) {
    const y = parseInt(year, 10) || new Date().getFullYear();
    let from;
    let to;

    if (periodType === "month") {
      const m = Math.min(Math.max(parseInt(month, 10) || 1, 1), 12);
      from = new Date(y, m - 1, 1);
      to = new Date(y, m, 0);
    } else if (periodType === "quarter") {
      const q = Math.min(Math.max(parseInt(quarter, 10) || 1, 1), 4);
      const startMonth = (q - 1) * 3;
      from = new Date(y, startMonth, 1);
      to = new Date(y, startMonth + 3, 0);
    } else if (periodType === "year") {
      from = new Date(y, 0, 1);
      to = new Date(y, 11, 31);
    } else {
      return null;
    }

    return {
      date_from: this._toISODateLocal(from),
      date_to: this._toISODateLocal(to),
    };
  }

  _syncDatesFromPreset(notify = false) {
    const { period_type, year, month, quarter } = this.state.filters;
    if (period_type === "custom") return;

    const range = this._getPeriodRange(period_type, year, month, quarter);
    if (range) {
      this.state.filters.date_from = range.date_from;
      this.state.filters.date_to = range.date_to;

      if (notify) {
        this.notification.add(_t("Đã cập nhật khoảng ngày theo bộ lọc thời gian."), {
          type: "info",
        });
      }
    }
  }

  get yearOptions() {
    const current = new Date().getFullYear();
    const years = [];
    for (let y = current + 2; y >= current - 2; y--) {
      years.push(String(y));
    }
    return years;
  }

  get monthOptions() {
    return [
      { value: "01", label: _t("Tháng 1") },
      { value: "02", label: _t("Tháng 2") },
      { value: "03", label: _t("Tháng 3") },
      { value: "04", label: _t("Tháng 4") },
      { value: "05", label: _t("Tháng 5") },
      { value: "06", label: _t("Tháng 6") },
      { value: "07", label: _t("Tháng 7") },
      { value: "08", label: _t("Tháng 8") },
      { value: "09", label: _t("Tháng 9") },
      { value: "10", label: _t("Tháng 10") },
      { value: "11", label: _t("Tháng 11") },
      { value: "12", label: _t("Tháng 12") },
    ];
  }

  get quarterOptions() {
    return [
      { value: "1", label: _t("Quý 1") },
      { value: "2", label: _t("Quý 2") },
      { value: "3", label: _t("Quý 3") },
      { value: "4", label: _t("Quý 4") },
    ];
  }

  // -----------------------------
  // LocalStorage helpers
  // -----------------------------
  _restoreFiltersFromStorage() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (!saved) return;

      this.state.filters.period_type = saved.period_type || this.state.filters.period_type;
      this.state.filters.year = saved.year || this.state.filters.year;
      this.state.filters.month = saved.month || this.state.filters.month;
      this.state.filters.quarter = saved.quarter || this.state.filters.quarter;
      this.state.filters.date_from = saved.date_from || this.state.filters.date_from;
      this.state.filters.date_to = saved.date_to || this.state.filters.date_to;
    } catch (_) { }
  }

  _saveFiltersToStorage() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...this.state.filters }));
  }

  // -----------------------------
  // Helpers
  // -----------------------------
  get periodLabel() {
    const { period_type, year, month, quarter, date_from, date_to } = this.state.filters;

    if (period_type === "month") {
      return `Tháng ${parseInt(month || "1", 10)}/${year}`;
    }
    if (period_type === "quarter") {
      return `Quý ${quarter}/${year}`;
    }
    if (period_type === "year") {
      return `Năm ${year}`;
    }

    if (!date_from || !date_to) return _t("Không xác định");
    return `${fmtDate(date_from)} → ${fmtDate(date_to)}`;
  }

  // -----------------------------
  // Filter events
  // -----------------------------
  onPeriodTypeChange(ev) {
    this.state.filters.period_type = ev.target.value;
    if (this.state.filters.period_type !== "custom") {
      this._syncDatesFromPreset();
    }
  }

  onYearChange(ev) {
    this.state.filters.year = ev.target.value;
    this._syncDatesFromPreset();
  }

  onMonthChange(ev) {
    this.state.filters.month = ev.target.value;
    this._syncDatesFromPreset();
  }

  onQuarterChange(ev) {
    this.state.filters.quarter = ev.target.value;
    this._syncDatesFromPreset();
  }

  onDateFromChange(ev) {
    this.state.filters.date_from = ev.target.value;
    this.state.filters.period_type = "custom";
  }

  onDateToChange(ev) {
    this.state.filters.date_to = ev.target.value;
    this.state.filters.period_type = "custom";
  }

  // -----------------------------
  // Fetch data
  // -----------------------------
  async fetchData() {
    const { date_from, date_to } = this.state.filters;
    try {
      const data = await this.orm.call("wt.account.dashboard", "get_dashboard_data", [], { date_from, date_to });

      const cashIn = Number(data?.cash_in ?? 0);
      const cashOut = Number(data?.cash_out ?? 0);
      const net = Number(data?.net_cash ?? cashIn - cashOut);
      const advRemain = Number(data?.employee_advance_remain_total ?? 0);
      const totalSupp = Number(data?.total_supplier_invoice ?? 0);
      const totalCust = Number(data?.total_customer_invoice ?? 0);

      this.state.kpis = {
        cash_in: fmtVND(cashIn),
        cash_out: fmtVND(cashOut),
        net_cash: fmtVND(net),
        advance_remain_total: fmtVND(advRemain),
        total_supplier_invoice: fmtVND(totalSupp),
        total_customer_invoice: fmtVND(totalCust),
      };

      const empRemain = data?.employees_with_remain || [];
      this.state.employees_with_remain = empRemain
        .sort((a, b) => b.remain_total - a.remain_total)
        .slice(0, 10);

      this.state.proposal_pending_count = data?.proposal_pending_count || 0;
      this.state.payment_proposals_pending_count = data?.payment_proposals_pending_count || 0;
      this.state.supplier_invoices = data?.supplier_invoices || [];
      this.state.customer_invoices = data?.customer_invoices || [];
      this.state.daily_cash_flow = data?.daily_cash_flow || [];

      this.renderCharts();
    } catch (e) {
      console.error(e);
      this.notification.add(_t("Không thể tải dữ liệu dashboard kế toán."), { type: "danger" });
    }
  }

  // -----------------------------
  // Filters
  // -----------------------------
  applyFilter() {
    const { date_from, date_to } = this.state.filters;
    if (date_from && date_to && date_from > date_to) {
      this.notification.add(_t("Ngày bắt đầu phải ≤ ngày kết thúc."), { type: "warning" });
      return;
    }
    this._saveFiltersToStorage();
    this.fetchData();
  }

  // -----------------------------
  // Charts
  // -----------------------------
  _destroyCharts() {
    Object.values(this._charts).forEach((ch) => ch?.destroy());
    this._charts = { remain: null, dailyFlow: null };
  }

  renderCharts() {
    if (this._rendering) return;
    this._rendering = true;
    this._destroyCharts();

    const list = this.state.employees_with_remain || [];
    if (window.Chart && this.remainChartRef.el && list.length) {
      const labels = list.map((e) => e.employee_name);
      const data = list.map((e) => e.remain_total);
      const ids = list.map((e) => e.employee_id);

      this._charts.remain = new Chart(this.remainChartRef.el, {
        type: "bar",
        data: {
          labels,
          datasets: [{
            label: _t("Còn dư tạm ứng"),
            data,
            backgroundColor: [
              "#3B82F6", "#10B981", "#F59E0B", "#EF4444",
              "#6366F1", "#84CC16", "#EC4899", "#F97316",
              "#06B6D4", "#8B5CF6",
            ],
            borderRadius: 6,
          }],
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => `${ctx.label}: ${fmtVND(ctx.parsed.x)}`,
              },
            },
          },
          scales: {
            x: { ticks: { callback: (v) => fmtVND(v) } },
            y: { ticks: { autoSkip: false } },
          },
          onClick: (evt, elements) => {
            if (!elements?.length) return;
            const idx = elements[0].index;
            const empId = ids[idx];
            if (!empId) return;
            this.action.doAction({
              type: "ir.actions.act_window",
              name: _t("Tạm ứng của ") + labels[idx],
              res_model: "account.employee.advance",
              views: [[false, "list"], [false, "form"]],
              domain: [["employee_id", "=", empId]],
              target: "current",
            });
          },
        },
      });
    }

    const dailyData = this.state.daily_cash_flow || [];
    if (window.Chart && this.dailyFlowChartRef?.el && dailyData.length) {
      const labels = dailyData.map((r) => new Date(r.date).toLocaleDateString("vi-VN"));
      const cashIn = dailyData.map((r) => r.cash_in);
      const cashOut = dailyData.map((r) => r.cash_out);

      this._charts.dailyFlow = new Chart(this.dailyFlowChartRef.el, {
        type: "line",
        data: {
          labels,
          datasets: [
            {
              label: _t("Tiền thu"),
              data: cashIn,
              borderColor: "#16a34a",
              backgroundColor: "rgba(22,163,74,0.1)",
              fill: true,
              tension: 0.3,
            },
            {
              label: _t("Tiền chi"),
              data: cashOut,
              borderColor: "#dc2626",
              backgroundColor: "rgba(220,38,38,0.1)",
              fill: true,
              tension: 0.3,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: "top" },
            tooltip: {
              callbacks: {
                label: (ctx) => `${ctx.dataset.label}: ${fmtVND(ctx.parsed.y)}`,
              },
            },
          },
          scales: {
            y: { ticks: { callback: (v) => fmtVND(v) } },
          },
          onClick: (evt, activeEls) => {
            if (!activeEls.length) return;
            const idx = activeEls[0].index;
            const clickedDate = dailyData[idx].date;
            const datasetLabel = activeEls[0].datasetIndex === 0 ? "receipt" : "payment";

            if (datasetLabel === "receipt") {
              this.openDailyReceipts(clickedDate);
            } else {
              this.openDailyPayments(clickedDate);
            }
          },
        },
      });
    }

    this._rendering = false;
  }

  // -----------------------------
  // Navigation
  // -----------------------------
  openPayments() {
    const { date_from, date_to } = this.state.filters;
    this.action.doAction({
      type: "ir.actions.act_window",
      name: _t("Tất cả phiếu chi trong kỳ"),
      res_model: "account.payment.request",
      views: [[false, "list"], [false, "form"]],
      domain: [
        ["date_payment", ">=", date_from],
        ["date_payment", "<=", date_to],
        ["status_expense", "in", ["paid"]],
      ],
      target: "current",
    });
  }

  openReceipts() {
    const { date_from, date_to } = this.state.filters;
    this.action.doAction({
      type: "ir.actions.act_window",
      name: _t("Tất cả phiếu thu trong kỳ"),
      res_model: "account.receipt",
      views: [[false, "list"], [false, "form"]],
      domain: [
        ["date", ">=", date_from],
        ["date", "<=", date_to],
        ["state", "in", ["posted"]],
      ],
      target: "current",
    });
  }

  openProposals() {
    const { date_from, date_to } = this.state.filters;
    this.action.doAction({
      type: "ir.actions.act_window",
      name: _t("Phiếu đề xuất cần xử lý"),
      res_model: "proposal.sheet",
      views: [[false, "list"], [false, "form"]],
      domain: [
        ["state", "in", ["reviewed_accounting", "waiting_accounting_paid"]],
        ["date_proposal", ">=", date_from],
        ["date_proposal", "<=", date_to],
      ],
      target: "current",
    });
  }

  openPaymentProposals() {
    const { date_from, date_to } = this.state.filters;
    this.action.doAction({
      type: "ir.actions.act_window",
      name: _t("Giải chi kế toán cần xử lý"),
      res_model: "account.payment.proposal",
      views: [[false, "list"], [false, "form"]],
      domain: [
        ["state", "in", ["dept_approved", "director_approved"]],
        ["date_request", ">=", date_from],
        ["date_request", "<=", date_to],
      ],
      target: "current",
    });
  }

  openAdvances() {
    this.action.doAction({
      type: "ir.actions.act_window",
      name: _t("Theo dõi tạm ứng và hoàn ứng"),
      res_model: "account.employee.advance",
      views: [[false, "list"], [false, "form"]],
      domain: [["remain_total", ">", 0]],
      target: "current",
    });
  }

  async openDailyReceipts(dateStr) {
    await this.action.doAction({
      type: "ir.actions.act_window",
      name: _t("Phiếu thu ngày ") + dateStr,
      res_model: "account.receipt",
      target: "current",
      views: [[false, "list"], [false, "form"]],
      domain: [["date", "=", dateStr], ["state", "in", ["posted"]]],
    });
  }

  async openDailyPayments(dateStr) {
    await this.action.doAction({
      type: "ir.actions.act_window",
      name: _t("Phiếu chi ngày ") + dateStr,
      res_model: "account.payment.request",
      target: "current",
      views: [[false, "list"], [false, "form"]],
      domain: [
        ["date_payment", "=", dateStr],
        ["state", "in", ["approved", "post", "paid", "done"]],
      ],
    });
  }

  openCustomerInvoices() {
    const { date_from, date_to } = this.state.filters;
    this.action.doAction({
      type: "ir.actions.act_window",
      name: _t("Hóa đơn đầu ra (Khách hàng)"),
      res_model: "customer.invoice",
      target: "current",
      views: [[false, "list"], [false, "form"]],
      domain: [
        ["date", ">=", date_from],
        ["date", "<=", date_to],
      ],
    });
  }

  openSupplierInvoices() {
    const { date_from, date_to } = this.state.filters;
    this.action.doAction({
      type: "ir.actions.act_window",
      name: _t("Hóa đơn đầu vào (Nhà cung cấp)"),
      res_model: "supplier.invoice",
      target: "current",
      views: [[false, "list"], [false, "form"]],
      domain: [
        ["date", ">=", date_from],
        ["date", "<=", date_to],
      ],
    });
  }

  openDetailSupplierInvoice(invId) {
    this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "supplier.invoice",
      res_id: invId,
      views: [[false, "form"]],
      target: "current",
    });
  }

  openDetailCustomerInvoice(invId) {
    this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "customer.invoice",
      res_id: invId,
      views: [[false, "form"]],
      target: "current",
    });
  }
}

registry.category("actions").add("accounting_dashboard_main", AccountingDashboard);
export default AccountingDashboard;