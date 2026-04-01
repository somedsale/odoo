/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { View } from "@web/views/view";
import { ProjectWorkProjectFormOwl } from "../form/project_work_project_form_owl";
import { CostEstimateStandardScreen } from "../js/cost_estimate_standard_screen";
import { ProjectExpenseStandardScreen } from "../js/project_expense_standard_screen";
import { ProjectInvoiceStandardScreen } from "../js/project_invoice_standard_screen";
import { ProjectTaskStandardScreen } from "../js/project_task_standard_screen";

function num(x) {
  const n = Number(x);
  return Number.isFinite(n) ? n : 0;
}

export class ProjectWorkDashboard extends Component {
  static template = "project_work_from_so.ProjectWorkDashboard";
  static components = {
    View,
    ProjectWorkProjectFormOwl,
    CostEstimateStandardScreen,
    ProjectExpenseStandardScreen,
    ProjectInvoiceStandardScreen,
    ProjectTaskStandardScreen,
  };

  setup() {
    this.orm = useService("orm");
    this.action = useService("action");
    this.notification = useService("notification");
    this.router = useService("router");

    this._nf0 = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 });

    const ctx = this.props?.action?.context || {};
    this.formViewId = ctx.form_view_id || false;
    this.treeViewId = ctx.tree_view_id || false;

    const hash = this.router.current?.hash || {};

    const initialSelectedId =
      num(hash.project_id) > 0
        ? num(hash.project_id)
        : num(ctx.active_id) > 0
          ? num(ctx.active_id)
          : null;

    const initialIsCreateMode =
      hash.create === 1 ||
      hash.create === "1" ||
      hash.create === true ||
      hash.create === "true";

    const initialMode =
      hash.mode === "detail" || initialSelectedId || initialIsCreateMode
        ? "detail"
        : "list";

    this.state = useState({
      loading: true,

      // mode: list | detail
      mode: initialMode,
      isCreateMode: initialIsCreateMode,

      // list data
      query: hash.query || "",
      projects: [],
      listLoading: false,
      selectedMap: {},

      // selected project
      selectedId: initialSelectedId,

      // cache field availability
      projectFields: null,
      catNameCache: new Map(),

      filterPartnerId: num(hash.partner_id) || null,
      filterStageId: num(hash.stage_id) || null,
      sortBy: hash.sort_by || "id",
      sortDir: hash.sort_dir || "desc",

      // pagination
      page: num(hash.page) || 1,
      pageSize: num(hash.page_size) || 20,
    });

    onWillStart(async () => {
      await this._prepareProjectFields();
      await this.loadProjects();

      if (this.state.selectedId || this.state.isCreateMode) {
        this.state.mode = "detail";
      }

      this._ensureValidPage();
      this._syncUrl();
      this.state.loading = false;
    });
  }

  // =========================================================
  // URL HASH SYNC
  // =========================================================
  _syncUrl() {
    const currentHash = this.router.current?.hash || {};

    const nextHash = {
      ...currentHash,
      mode: this.state.mode || "list",
      create: this.state.isCreateMode ? 1 : undefined,
      query: this.state.query || undefined,
      partner_id: this.state.filterPartnerId || undefined,
      stage_id: this.state.filterStageId || undefined,
      sort_by: this.state.sortBy || "id",
      sort_dir: this.state.sortDir || "desc",
      page: this.state.page || 1,
      page_size: this.state.pageSize || 20,
      project_id:
        this.state.mode === "detail" && this.state.selectedId
          ? this.state.selectedId
          : undefined,
    };

    for (const key of Object.keys(nextHash)) {
      if (
        nextHash[key] === undefined ||
        nextHash[key] === null ||
        nextHash[key] === ""
      ) {
        delete nextHash[key];
      }
    }

    this.router.pushState(nextHash);
  }

  // ========= Helpers =========
  money(v) {
    return this._nf0.format(num(v));
  }
  formatDate(value) {
    if (!value) return "";
    try {
      const d = new Date(value);
      if (Number.isNaN(d.getTime())) return value;
      const dd = String(d.getDate()).padStart(2, "0");
      const mm = String(d.getMonth() + 1).padStart(2, "0");
      const yyyy = d.getFullYear();
      return `${dd}/${mm}/${yyyy}`;
    } catch {
      return value || "";
    }
  }
  pickFirstDate(r, names = []) {
    for (const name of names) {
      if (r && r[name]) {
        return this.formatDate(r[name]);
      }
    }
    return "";
  }
  // ========= Pagination + Filter =========
  get filteredProjects() {
    const q = (this.state.query || "").trim().toLowerCase();
    const partnerId = this.state.filterPartnerId || null;
    const stageId = this.state.filterStageId || null;

    let rows = [...(this.state.projects || [])];

    if (q) {
      rows = rows.filter((p) =>
        [
          p.name,
          p.partner_name,
          p.stage_name,
          p.location,
          p.category_text,
          p.signature_date,
          p.date_start,
          p.date,
        ]
          .filter(Boolean)
          .some((v) => String(v).toLowerCase().includes(q)),
      );
    }
    if (partnerId) {
      rows = rows.filter(
        (p) => Number(p.partner_id || 0) === Number(partnerId),
      );
    }

    if (stageId) {
      rows = rows.filter((p) => Number(p.stage_id || 0) === Number(stageId));
    }

    const sortBy = this.state.sortBy || "id";
    const dir = (this.state.sortDir || "desc") === "asc" ? 1 : -1;

    rows.sort((a, b) => {
      let va = a?.[sortBy];
      let vb = b?.[sortBy];

      if (sortBy === "id") {
        va = Number(a.id || 0);
        vb = Number(b.id || 0);
      }

      const isTextField = [
        "name",
        "partner_name",
        "stage_name",
        "location",
        "category_text",
        "signature_date",
        "date_start",
        "date",
      ].includes(sortBy);

      if (isTextField) {
        va = String(va || "").toLowerCase();
        vb = String(vb || "").toLowerCase();
        return va.localeCompare(vb, "vi") * dir;
      }

      va = Number(va || 0);
      vb = Number(vb || 0);
      if (va === vb) return 0;
      return (va > vb ? 1 : -1) * dir;
    });

    return rows;
  }

  get totalPages() {
    const total = this.filteredProjects.length;
    return Math.max(1, Math.ceil(total / (this.state.pageSize || 20)));
  }

  get pagedProjects() {
    const page = Math.min(Math.max(this.state.page || 1, 1), this.totalPages);
    const size = this.state.pageSize || 20;
    const start = (page - 1) * size;
    return this.filteredProjects.slice(start, start + size);
  }

  get pageStart() {
    const total = this.filteredProjects.length;
    if (!total) return 0;
    return (this.state.page - 1) * this.state.pageSize + 1;
  }

  get pageEnd() {
    const total = this.filteredProjects.length;
    if (!total) return 0;
    return Math.min(this.state.page * this.state.pageSize, total);
  }

  get pageNumbers() {
    const total = this.totalPages;
    const current = this.state.page;
    const pages = [];

    if (total <= 7) {
      for (let i = 1; i <= total; i++) pages.push(i);
      return pages;
    }

    pages.push(1);

    if (current > 3) pages.push("...");

    const start = Math.max(2, current - 1);
    const end = Math.min(total - 1, current + 1);
    for (let i = start; i <= end; i++) {
      pages.push(i);
    }

    if (current < total - 2) pages.push("...");

    pages.push(total);
    return pages;
  }

  goToPage(page) {
    const p = Number(page) || 1;
    this.state.page = Math.min(Math.max(p, 1), this.totalPages);
    this._syncUrl();
  }

  prevPage() {
    if (this.state.page > 1) {
      this.state.page -= 1;
      this._syncUrl();
    }
  }

  nextPage() {
    if (this.state.page < this.totalPages) {
      this.state.page += 1;
      this._syncUrl();
    }
  }

  firstPage() {
    this.state.page = 1;
    this._syncUrl();
  }

  lastPage() {
    this.state.page = this.totalPages;
    this._syncUrl();
  }

  _ensureValidPage() {
    if (this.state.page < 1) this.state.page = 1;
    if (this.state.page > this.totalPages) this.state.page = this.totalPages;
  }

  get pageTokens() {
    const total = this.totalPages;
    const current = this.state.page;
    const tokens = [];

    if (total <= 7) {
      for (let i = 1; i <= total; i++) {
        tokens.push({ key: `p_${i}`, label: i, page: i, ellipsis: false });
      }
      return tokens;
    }

    tokens.push({ key: "p_1", label: 1, page: 1, ellipsis: false });

    if (current > 3) {
      tokens.push({ key: "e_left", label: "…", page: null, ellipsis: true });
    }

    const start = Math.max(2, current - 1);
    const end = Math.min(total - 1, current + 1);
    for (let i = start; i <= end; i++) {
      tokens.push({ key: `p_${i}`, label: i, page: i, ellipsis: false });
    }

    if (current < total - 2) {
      tokens.push({ key: "e_right", label: "…", page: null, ellipsis: true });
    }

    tokens.push({
      key: `p_${total}`,
      label: total,
      page: total,
      ellipsis: false,
    });

    return tokens;
  }

  onClickPage(ev) {
    const page = Number(ev.currentTarget.dataset.page || 0);
    if (!page) return;
    this.goToPage(page);
  }

  // ========= Data loading =========
  async _prepareProjectFields() {
    const wanted = [
      "name",
      "partner_id",
      "stage_id",
      "location",
      "sales_category_ids",

      "signature_date",
      "date_start",
      "date",

      "value_contract_tax",
      "value_settlement",
      "value_remaining",
      "value_completed",
      "progress_percent",

      "value_accepted",
      "value_acceptance_remaining",
      "acceptance_percent",

      "value_finalized",
      "value_finalization_remaining",
      "finalization_percent",

      "claim_value_done",
      "claim_value_remaining",
      "claim_progress_percent",

      "acceptance_progress_percent",

      "customer_invoice_amount_total",
      "customer_invoice_received_total",
      "customer_invoice_untaxed_total",
      "customer_invoice_remaining_total",
      "payment_process_percent",
      "payment_vs_acceptance_percent",
      "payment_vs_completed_percent",
      "payment_vs_invoice_percent",
    ];

    let available = new Set(["name", "partner_id"]);
    try {
      const fg = await this.orm.call(
        "project.project",
        "fields_get",
        [wanted, ["type"]],
        {},
      );
      for (const f of wanted) {
        if (fg && fg[f]) available.add(f);
      }
    } catch (e) {
      console.warn("[PWF Dashboard] fields_get fail:", e);
    }

    this.state.projectFields = Array.from(available);
  }
  async _resolveCategoryNames(ids) {
    const need = [...new Set(ids)].filter(
      (id) => id && !this.state.catNameCache.has(id),
    );
    if (!need.length) return;

    try {
      const pairs = await this.orm.call(
        "sale.order.category",
        "name_get",
        [need],
        {},
      );
      for (const [id, name] of pairs || []) {
        this.state.catNameCache.set(id, name);
      }
    } catch (e) {
      console.warn("[PWF Dashboard] name_get category fail:", e);
    }
  }

  _categoryText(m2mIds) {
    const ids = Array.isArray(m2mIds) ? m2mIds : [];
    const names = ids
      .map((id) => this.state.catNameCache.get(id))
      .filter(Boolean);
    if (!names.length) return "";
    if (names.length <= 2) return names.join(", ");
    return `${names.slice(0, 2).join(", ")} (+${names.length - 2})`;
  }

  async loadProjects() {
    try {
      this.state.listLoading = true;

      const fields = this.state.projectFields || ["name", "partner_id"];
      const domain = [];

      const rows = await this.orm.searchRead(
        "project.project",
        domain,
        fields,
        { order: "id desc", limit: 300 },
      );

      const validIds = new Set((rows || []).map((r) => r.id));
      const cleaned = {};
      for (const [k, v] of Object.entries(this.state.selectedMap || {})) {
        const id = Number(k);
        if (v && validIds.has(id)) {
          cleaned[id] = true;
        }
      }
      this.state.selectedMap = cleaned;

      const allCatIds = [];
      if (fields.includes("sales_category_ids")) {
        for (const r of rows || []) {
          const ids = r.sales_category_ids || [];
          if (ids.length) allCatIds.push(...ids);
        }
      }
      await this._resolveCategoryNames(allCatIds);

      this.state.projects = (rows || []).map((r, idx) => {
        const value_contract_tax = num(r.value_contract_tax);
        const value_settlement = num(r.value_settlement);
        const value_remaining = num(r.value_remaining);
        const value_completed = num(r.value_completed);
        const progress_percent = num(r.progress_percent);

        const value_accepted = fields.includes("value_accepted")
          ? num(r.value_accepted)
          : num(r.value_accepted);

        const value_acceptance_remaining = fields.includes(
          "value_acceptance_remaining",
        )
          ? num(r.value_acceptance_remaining)
          : num(r.value_acceptance_remaining);

        const acceptance_progress_percent = fields.includes(
          "acceptance_percent",
        )
          ? num(r.acceptance_percent)
          : num(r.acceptance_progress_percent);

        const claim_value_done = fields.includes("value_finalized")
          ? num(r.value_finalized)
          : num(r.claim_value_done);

        const claim_value_remaining = fields.includes(
          "value_finalization_remaining",
        )
          ? num(r.value_finalization_remaining)
          : num(r.claim_value_remaining);

        const claim_progress_percent = fields.includes("finalization_percent")
          ? num(r.finalization_percent)
          : num(r.claim_progress_percent);

        const customer_invoice_amount_total = num(
          r.customer_invoice_amount_total,
        );
        const customer_invoice_received_total = num(
          r.customer_invoice_received_total,
        );
        const customer_invoice_untaxed_total = num(
          r.customer_invoice_untaxed_total,
        );
        const customer_invoice_remaining_total = num(
          r.customer_invoice_remaining_total,
        );
        const payment_process_percent = num(r.payment_process_percent);
        const payment_vs_acceptance_percent = num(
          r.payment_vs_acceptance_percent,
        );
        const payment_vs_completed_percent = num(
          r.payment_vs_completed_percent,
        );
        const payment_vs_invoice_percent = num(r.payment_vs_invoice_percent);
        const signature_date = this.formatDate(r.signature_date);
        const date_start = this.formatDate(r.date_start);
        const date = this.formatDate(r.date);
        return {
          id: r.id,
          stt: idx + 1,
          name: r.name || "",
          partner_name: (r.partner_id && r.partner_id[1]) || "",
          stage_name: (r.stage_id && r.stage_id[1]) || "",
          location: r.location || "",
          category_text: this._categoryText(r.sales_category_ids || []),
          partner_id: (r.partner_id && r.partner_id[0]) || null,
          stage_id: (r.stage_id && r.stage_id[0]) || null,

          value_contract_tax,
          value_settlement,
          value_remaining,
          value_completed,
          progress_percent,

          value_accepted,
          value_acceptance_remaining,
          acceptance_progress_percent,

          claim_value_done,
          claim_value_remaining,
          claim_progress_percent,

          customer_invoice_amount_total,
          customer_invoice_received_total,
          customer_invoice_untaxed_total,
          customer_invoice_remaining_total,
          payment_process_percent,
          payment_vs_acceptance_percent,
          payment_vs_completed_percent,
          payment_vs_invoice_percent,

          signature_date,
          date_start,
          date,
        };
      });

      if (
        this.state.selectedId &&
        !this.state.projects.some((p) => p.id === this.state.selectedId)
      ) {
        this.state.selectedId = null;
        if (!this.state.isCreateMode) {
          this.state.mode = "list";
        }
      }

      this._ensureValidPage();
      this._syncUrl();
    } catch (e) {
      console.error("[PWF Dashboard] loadProjects error:", e);
      this.notification.add("Không tải được danh sách dự án.", {
        type: "danger",
      });
      this.state.projects = [];
      this.state.page = 1;
      this._syncUrl();
    } finally {
      this.state.listLoading = false;
    }
  }

  // ========= UI events =========
  onSearch(ev) {
    this.state.query = ev.target.value || "";
    this.state.page = 1;
    this._syncUrl();
  }

  openDetail(ev) {
    const pid = Number(ev.currentTarget?.dataset?.projectId || 0);
    if (!pid) return;
    this.state.selectedId = pid;
    this.state.mode = "detail";
    this.state.isCreateMode = false;
    this._syncUrl();
  }

  createProject() {
    this.state.selectedId = null;
    this.state.mode = "detail";
    this.state.isCreateMode = true;
    this._syncUrl();
  }

  async backToList() {
    this.state.mode = "list";
    this.state.selectedId = null;
    this.state.isCreateMode = false;
    await this.loadProjects();
    this._syncUrl();
  }

  async onProjectSaved(newProjectId = null) {
    this.state.isCreateMode = false;
    await this.loadProjects();

    if (newProjectId) {
      this.state.selectedId = Number(newProjectId);
      this.state.mode = "detail";
    } else {
      this.state.selectedId = null;
      this.state.mode = "list";
    }
    this._syncUrl();
  }

  openProjectInWindow() {
    if (!this.state.selectedId) return;

    this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "project.project",
      res_id: this.state.selectedId,
      views: this.formViewId ? [[this.formViewId, "form"]] : [[false, "form"]],
      target: "current",
    });
  }

  noop() {}

  isSelected(id) {
    return !!this.state.selectedMap[id];
  }

  get selectedRows() {
    const map = this.state.selectedMap || {};
    return (this.state.projects || []).filter((r) => !!map[r.id]);
  }

  get selectedCount() {
    return this.selectedRows.length;
  }

  get selectedTotals() {
    const totals = {
      value_contract_tax: 0,
      value_remaining: 0,
      value_completed: 0,
      claim_value_done: 0,
      claim_value_remaining: 0,
      value_accepted: 0,
      value_acceptance_remaining: 0,
      customer_invoice_untaxed_total: 0,
      customer_invoice_amount_total: 0,
      customer_invoice_received_total: 0,
      customer_invoice_remaining_total: 0,
    };

    for (const r of this.selectedRows) {
      totals.value_contract_tax += num(r.value_contract_tax);
      totals.value_remaining += num(r.value_remaining);
      totals.value_completed += num(r.value_completed);
      totals.claim_value_done += num(r.claim_value_done);
      totals.claim_value_remaining += num(r.claim_value_remaining);
      totals.value_accepted += num(r.value_accepted);
      totals.value_acceptance_remaining += num(r.value_acceptance_remaining);
      totals.customer_invoice_untaxed_total += num(
        r.customer_invoice_untaxed_total,
      );
      totals.customer_invoice_amount_total += num(
        r.customer_invoice_amount_total,
      );
      totals.customer_invoice_received_total += num(
        r.customer_invoice_received_total,
      );
      totals.customer_invoice_remaining_total += num(
        r.customer_invoice_remaining_total,
      );
    }
    return totals;
  }

  get allPageSelected() {
    const pageRows = this.pagedProjects || [];
    if (!pageRows.length) return false;
    return pageRows.every((r) => !!this.state.selectedMap[r.id]);
  }

  onToggleRowSelect(ev) {
    ev.stopPropagation();
    const id = Number(ev.currentTarget.dataset.id || 0);
    if (!id) return;

    const checked = !!ev.currentTarget.checked;
    const next = { ...(this.state.selectedMap || {}) };

    if (checked) {
      next[id] = true;
    } else {
      delete next[id];
    }

    this.state.selectedMap = next;
  }

  onToggleSelectPage(ev) {
    ev.stopPropagation();
    const checked = !!ev.currentTarget.checked;
    const next = { ...(this.state.selectedMap || {}) };

    for (const r of this.pagedProjects || []) {
      if (checked) {
        next[r.id] = true;
      } else {
        delete next[r.id];
      }
    }

    this.state.selectedMap = next;
  }

  clearSelected() {
    this.state.selectedMap = {};
  }

  stageBadgeClass(stageName) {
    const s = String(stageName || "")
      .trim()
      .toLowerCase();

    if (!s) return "is-default";
    if (s.includes("đang thực hiện")) return "is-doing";
    if (s.includes("hoàn tất") || s.includes("hoàn thành")) return "is-done";
    if (s.includes("đã hủy") || s.includes("hủy")) return "is-cancel";
    if (s.includes("tạm ngừng") || s.includes("đang tạm ngừng"))
      return "is-paused";
    if (s.includes("dự án cũ")) return "is-old";

    return "is-default";
  }

  get partnerOptions() {
    const map = new Map();
    for (const p of this.state.projects || []) {
      if (p.partner_id && p.partner_name) {
        map.set(p.partner_id, p.partner_name);
      }
    }
    return [...map.entries()]
      .map(([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label, "vi"));
  }

  get stageOptions() {
    const map = new Map();
    for (const p of this.state.projects || []) {
      if (p.stage_id && p.stage_name) {
        map.set(p.stage_id, p.stage_name);
      }
    }
    return [...map.entries()]
      .map(([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label, "vi"));
  }

  onChangePartnerFilter(ev) {
    const v = ev.target.value;
    this.state.filterPartnerId = v ? Number(v) : null;
    this.state.page = 1;
    this._syncUrl();
  }

  onChangeStageFilter(ev) {
    const v = ev.target.value;
    this.state.filterStageId = v ? Number(v) : null;
    this.state.page = 1;
    this._syncUrl();
  }

  onChangeSortBy(ev) {
    this.state.sortBy = ev.target.value || "id";
    this.state.page = 1;
    this._syncUrl();
  }

  onChangeSortDir(ev) {
    this.state.sortDir = ev.target.value || "desc";
    this.state.page = 1;
    this._syncUrl();
  }

  onChangePageSize(ev) {
    const newSize = parseInt(ev.target.value, 10) || 20;
    this.state.pageSize = newSize;
    this.state.page = 1;
    this._syncUrl();
  }

  resetFiltersAndSort() {
    this.state.query = "";
    this.state.filterPartnerId = null;
    this.state.filterStageId = null;
    this.state.sortBy = "id";
    this.state.sortDir = "desc";
    this.state.page = 1;
    this._syncUrl();
  }
  openTaskScreen(projectId) {
    this.state.selectedId = Number(projectId || 0);
    this.state.mode = "task_standard";
  }
  openCostEstimateScreen(projectId) {
    this.state.selectedId = Number(projectId || 0);
    this.state.mode = "cost_estimate_standard";
  }

  backToProjectDetail() {
    this.state.mode = "detail";
  }

  openExpenseDashboardScreen(projectId) {
    this.state.selectedId = Number(projectId || 0);
    this.state.mode = "expense_standard";
  }
  openInvoiceDashboardScreen(projectId) {
    this.state.selectedId = Number(projectId || 0);
    this.state.mode = "invoice_standard";
  }

  async openTasksAction() {
    try {
      if (!this.state.selectedId) {
        this.notification.add("Chưa chọn dự án.", {
          type: "warning",
        });
        return;
      }

      const action = await this.orm.call(
        "project.project",
        "action_view_tasks_custom",
        [[this.state.selectedId]],
      );

      if (!action) return;

      if (!Array.isArray(action.views)) {
        action.views = [
          [false, "list"],
          [false, "form"],
        ];
      }
      if (!action.view_mode) {
        action.view_mode = "list,form";
      }

      this.action.doAction(action);
    } catch (e) {
      console.error(e);
      this.notification.add("Không mở được danh sách nhiệm vụ.", {
        type: "danger",
      });
    }
  }
}

registry
  .category("actions")
  .add("project_work_project_dashboard", ProjectWorkDashboard);
