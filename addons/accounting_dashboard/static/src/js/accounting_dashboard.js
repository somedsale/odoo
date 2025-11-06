/** @odoo-module **/

import { Component, onWillStart, onMounted, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const STORAGE_KEY = "ad_accounting_dashboard_filters_v4";
const fmtVND = (n) => (Number(n) || 0).toLocaleString("vi-VN", { style: "currency", currency: "VND" });

class AccountingDashboard extends Component {
  static template = "ad.AccountingDashboard";

  setup() {
    this.orm = useService("orm");
    this.action = useService("action");
    this.notification = useService("notification");

    this.fmtVND = fmtVND;

    const today = new Date();
    const toISO = (d) => d.toISOString().slice(0, 10);

    this.state = useState({
      filters: {
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
    onWillStart(async () => await this.fetchData());
    onMounted(() => this.renderCharts());
  }

  // -----------------------------
  // LocalStorage helpers
  // -----------------------------
  _restoreFiltersFromStorage() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (saved?.date_from && saved?.date_to) {
        this.state.filters.date_from = saved.date_from;
        this.state.filters.date_to = saved.date_to;
      }
    } catch (_) { }
  }

  _saveFiltersToStorage() {
    const { date_from, date_to } = this.state.filters;
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ date_from, date_to }));
  }

  // -----------------------------
  // Helpers
  // -----------------------------
  get periodLabel() {
    const { date_from, date_to } = this.state.filters;
    if (!date_from || !date_to) return _t("Không xác định");
    const fmt = (s) => new Date(s).toLocaleDateString("vi-VN");
    return `${fmt(date_from)} → ${fmt(date_to)}`;
  }

  // -----------------------------
  // Fetch data
  // -----------------------------
  async fetchData() {
    const { date_from, date_to } = this.state.filters;
    try {
      const data = await this.orm.call("wt.account.dashboard", "get_dashboard_data", [], { date_from, date_to });

      // KPI
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

      // Dư tạm ứng
      const empRemain = data?.employees_with_remain || [];
      this.state.employees_with_remain = empRemain
        .sort((a, b) => b.remain_total - a.remain_total)
        .slice(0, 10);

      // ✅ Các bảng dữ liệu
      this.state.proposal_pending_count = data?.proposal_pending_count || 0;
      this.state.payment_proposals_pending_count = data?.payment_proposals_pending_count || 0;
      this.state.supplier_invoices = data?.supplier_invoices || [];
      this.state.customer_invoices = data?.customer_invoices || [];

      // ✅ Dữ liệu dòng tiền thu–chi
      this.state.daily_cash_flow = data?.daily_cash_flow || [];

      // Render biểu đồ
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
    this._charts = {};
  }

  renderCharts() {
    if (this._rendering) return;
    this._rendering = true;
    this._destroyCharts();

    // 1️⃣ Biểu đồ nhân viên còn dư (ngang)
    const list = this.state.employees_with_remain || [];
    if (window.Chart && this.remainChartRef.el && list.length) {
      const labels = list.map((e) => e.employee_name);
      const data = list.map((e) => e.remain_total);
      const ids = list.map((e) => e.employee_id);

      this._charts.remain = new Chart(this.remainChartRef.el, {
        type: "bar",
        data: {
          labels,
          datasets: [
            {
              label: _t("Còn dư tạm ứng"),
              data,
              backgroundColor: [
                "#3B82F6", "#10B981", "#F59E0B", "#EF4444",
                "#6366F1", "#84CC16", "#EC4899", "#F97316",
                "#06B6D4", "#8B5CF6",
              ],
              borderRadius: 6,
            },
          ],
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
            x: {
              ticks: { callback: (v) => fmtVND(v) },
            },
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

    // 2️⃣ Biểu đồ dòng tiền thu – chi – ròng
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
      domain: [["date_payment", ">=", date_from], ["date_payment", "<=", date_to], ['status_expense', 'in', ['paid']]],
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
      domain: [["date", ">=", date_from], ["date", "<=", date_to], ['state', 'in', ['posted']]],
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
}

registry.category("actions").add("accounting_dashboard_main", AccountingDashboard);
export default AccountingDashboard;
