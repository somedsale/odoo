/** @odoo-module **/

import { Component, onWillStart, onMounted, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const STORAGE_KEY = "ad_accounting_dashboard_filters_v1";

class AccountingDashboard extends Component {
  static template = "ad.AccountingDashboard";

  setup() {
    this.orm = useService("orm");
    this.action = useService("action");
    this.notification = useService("notification");

    const today = new Date();
    const toISO = (d) => d.toISOString().slice(0, 10);

    /* ----- State mặc định (dữ liệu ảo) ----- */
    this.state = useState({
      filters: {
        date_from: toISO(new Date(today.getTime() - 29 * 24 * 3600 * 1000)), // 30 ngày
        date_to: toISO(today),
      },
      kpis: [
        { title: _t("Doanh thu kỳ"), value: "3.000.000.000", sub: "▲ 10% • 10,8%" },
        { title: _t("LN gộp"), value: "320.000.000", sub: "▲ 400%" },
        { title: _t("Tiền mặt + NH"), value: "2.500.000.000", sub: _t("Số dư hiện tại") },
        { title: _t("Phải thu (AR)"), value: "600.000.000", sub: "400 / 150.000" },
        { title: _t("Dòng tiền thuần"), value: "-50.000.000", sub: "VTD • +150.000 VND" },
      ],
      tables: {
        ar: Array.from({ length: 6 }, (_, i) => ({
          partner: "Công ty A",
          number: `INV/2025/00${i + 1}`,
          due: "20-11-2025",
          remain: "—",
          age: "— ngày",
        })),
        ap: Array.from({ length: 6 }, (_, i) => ({
          vendor: `Nhà CC ${i + 1}`,
          number: `BILL/2025/0${i + 1}`,
          due: "18-11-2025",
          remain: "—",
          age: "— ngày",
        })),
        schedule: Array.from({ length: 6 }, (_, i) => ({
          day: `${10 + i}-11-2025`,
          doc: `PAY/REQ/${100 + i}`,
          partner: "Công ty B",
          amount: "—",
          state: _t("Chờ duyệt"),
        })),
      },
      sideCards: [
        {
          title: _t("Thuế VAT"),
          items: [
            [_t("VAT đầu ra"), "80.000.000"],
            [_t("VAT đầu vào"), "100.000.000"],
          ],
        },
        {
          title: _t("Kho & Giá trị tồn"),
          items: [
            [_t("Vòng trưởng"), "2.000.000.000"],
            [_t("Tồn chậm luân chuyển"), "120.000.000"],
          ],
        },
        {
          title: _t("Khoản vay & Lãi"),
          items: [
            [_t("Dư nợ"), "4.500.000"],
            [_t("Kỳ trả kế tiếp"), "30/07/2024"],
          ],
        },
        {
          title: _t("Tạm ứng NV"),
          items: [[_t("Dư hồ sơ cần quyết toán"), "50.000.000"]],
        },
      ],
      charts: {
        sales_trend: { labels: [], data: [] },     // có Chart.js sẽ vẽ
        kqkd_monthly: { labels: [], data: [] },    // có Chart.js sẽ vẽ
      },
    });

    /* refs cho canvas chart */
    this.salesTrendRef = useRef("salesTrend");
    this.kqkdRef = useRef("kqkdMonthly");
    this._charts = { sales: null, kqkd: null };

    /* khôi phục filter từ localStorage */
    this._restoreFiltersFromStorage();

    onWillStart(async () => {
      await this.fetchData();      // giả lập gọi ORM nếu cần
    });

    onMounted(() => {
      this.renderCharts();         // thử vẽ chart nếu có Chart.js
    });
  }

  /* ===== helper: localStorage ===== */
  _restoreFiltersFromStorage() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const saved = JSON.parse(raw);
      if (saved?.date_from && saved?.date_to) {
        this.state.filters.date_from = saved.date_from;
        this.state.filters.date_to = saved.date_to;
      }
    } catch (_) { }
  }
  _saveFiltersToStorage() {
    try {
      const { date_from, date_to } = this.state.filters;
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ date_from, date_to }));
    } catch (_) { }
  }

  get periodLabel() {
    const { date_from, date_to } = this.state.filters;
    if (!date_from || !date_to) return _t("Không xác định");
    const fmt = (s) => new Date(s).toLocaleDateString("vi-VN");
    return `${fmt(date_from)} → ${fmt(date_to)}`;
  }

  /* ===== data fetch (fake/orm) ===== */
  async fetchData() {
    const { date_from, date_to } = this.state.filters;
    try {
      // TODO: gọi ORM thật nếu bạn có model server
      // const data = await this.orm.call("wt.account.dashboard", "get_dashboard_data", [], { date_from, date_to });
      // this.state.kpis = data.kpis || this.state.kpis; ...
      // Ở đây mình chỉ giữ dữ liệu ảo, nhưng cập nhật labels/data mẫu để có thể vẽ Chart nếu có.
      this.state.charts.sales_trend = {
        labels: ["2025-11-01", "2025-11-02", "2025-11-03", "2025-11-04", "2025-11-05"],
        data: [30, 52, 40, 60, 55],
      };
      this.state.charts.kqkd_monthly = {
        labels: ["T7", "T8", "T9", "T10", "T11"],
        data: [80, 95, 70, 110, 105],
      };
      this.renderCharts();
    } catch (e) {
      console.error(e);
      this.notification.add(_t("Không thể tải dữ liệu dashboard kế toán."), { type: "danger" });
    }
  }

  applyFilter() {
    const { date_from, date_to } = this.state.filters;
    if (date_from && date_to && date_from > date_to) {
      this.notification.add(_t("Ngày bắt đầu phải ≤ ngày kết thúc."), { type: "warning" });
      return;
    }
    this._saveFiltersToStorage();
    this.fetchData();
  }

  /* ===== charts ===== */
  _destroyCharts() {
    if (this._charts.sales) { this._charts.sales.destroy(); this._charts.sales = null; }
    if (this._charts.kqkd) { this._charts.kqkd.destroy(); this._charts.kqkd = null; }
  }

  renderCharts() {
    this._destroyCharts();
    // Nếu chưa nạp Chart.js thì bỏ qua (vẫn không lỗi)
    if (typeof Chart === "undefined") return;

    const fmtVN = (s) => {
      if (!s) return "";
      const [y, m, d] = String(s).split("-");
      return `${d}/${m}/${y}`;
    };

    // 1) Sales Trend
    if (this.salesTrendRef.el) {
      this._charts.sales = new Chart(this.salesTrendRef.el, {
        type: "line",
        data: {
          labels: this.state.charts.sales_trend.labels,
          datasets: [{
            label: _t("Doanh thu"),
            data: this.state.charts.sales_trend.data,
            borderColor: "#3B82F6",
            backgroundColor: "rgba(99,102,241,0.12)",
            fill: true, tension: 0.3,
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          scales: {
            x: {
              ticks: { callback: (_, idx) => fmtVN(this.state.charts.sales_trend.labels[idx]) },
            },
          },
        },
      });
    }

    // 2) KQKD theo tháng (bar)
    if (this.kqkdRef.el) {
      this._charts.kqkd = new Chart(this.kqkdRef.el, {
        type: "bar",
        data: {
          labels: this.state.charts.kqkd_monthly.labels,
          datasets: [{
            label: _t("KQKD"),
            data: this.state.charts.kqkd_monthly.data,
            backgroundColor: "#10B981",
          }],
        },
        options: { responsive: true, maintainAspectRatio: false },
      });
    }
  }

  /* ===== mở action (ví dụ) ===== */
  openARSoon() { /* TODO: mở danh sách AR */ }
  openAPSoon() { /* TODO: mở danh sách AP */ }
}

registry
  .category("actions")
  .add("accounting_dashboard_main", AccountingDashboard);

