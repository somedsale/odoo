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

    // 👉 Thêm dòng này để template gọi được fmtVND()
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
      },
      employees_with_remain: [],
      proposal_pending: [],
    });

    this.remainChartRef = useRef("remainChart");
    this._charts = { remain: null };
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

      this.state.kpis = {
        cash_in: fmtVND(cashIn),
        cash_out: fmtVND(cashOut),
        net_cash: fmtVND(net),
        advance_remain_total: fmtVND(advRemain),
      };

      // Dư tạm ứng
      const empRemain = data?.employees_with_remain || [];
      this.state.employees_with_remain = empRemain
        .sort((a, b) => b.remain_total - a.remain_total)
        .slice(0, 10);

      // ✅ Phiếu đề xuất cần xử lý
      this.state.proposal_pending = data?.proposal_pending || [];

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
    if (this._charts.remain) {
      this._charts.remain.destroy();
      this._charts.remain = null;
    }
  }

  renderCharts() {
    if (this._rendering) return;
    this._rendering = true;

    this._destroyCharts();
    if (!window.Chart || !this.remainChartRef.el) {
      this._rendering = false;
      return;
    }

    const list = this.state.employees_with_remain;
    if (!list.length) {
      this._rendering = false;
      return;
    }

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
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: true, position: "top" },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.label}: ${fmtVND(ctx.parsed.y)}`,
            },
          },
        },
        scales: {
          x: {
            ticks: {
              autoSkip: false,
              maxRotation: 45,
              minRotation: 30,
            },
          },
          y: {
            ticks: {
              callback: (v) => fmtVND(v),
            },
          },
        },
        onClick: (evt, elements) => {
          if (!elements?.length) return;
          const idx = elements[0].index;
          const empId = ids[idx];
          if (!empId) return;

          const { date_from, date_to } = this.state.filters;
          this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Tạm ứng và hoàn ứng của ") + labels[idx],
            res_model: "account.employee.advance",
            views: [[false, "list"], [false, "form"]],
            domain: [
              ["employee_id", "=", empId],
            ],
            target: "current",
          });
        },
      },
    });

    this._rendering = false;
  }

  // -----------------------------
  // Navigation
  // -----------------------------
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
      ],
      target: "current",
    });
  }
  openAdvances() {
    const { date_from, date_to } = this.state.filters;
    this.action.doAction({
      type: "ir.actions.act_window",
      name: _t("Tất cả phiếu tạm ứng trong kỳ"),
      res_model: "account.payment.request",
      views: [[false, "list"], [false, "form"]],
      domain: [
        ["is_advance", "=", true],
        ["date_payment", ">=", date_from],
        ["date_payment", "<=", date_to],
      ],
      target: "current",
    });
  }
}

registry.category("actions").add("accounting_dashboard_main", AccountingDashboard);
export default AccountingDashboard;
