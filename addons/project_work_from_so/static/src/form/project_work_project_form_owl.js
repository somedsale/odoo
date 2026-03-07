/** @odoo-module **/

import { Component, useState, onWillStart, markup } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

function num(x) {
  const n = Number(x);
  return Number.isFinite(n) ? n : 0;
}

export class ProjectWorkProjectFormOwl extends Component {
  static template = "project_work_from_so.ProjectWorkProjectFormOwl";
  static props = {
    projectId: Number,
    onBack: { type: Function, optional: true },
    formViewId: { type: Number, optional: true }, // fallback mở form chuẩn
  };

  setup() {
    this.orm = useService("orm");
    this.action = useService("action");
    this.notification = useService("notification");

    this._nf0 = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 });
    this._autoSyncedOnOpen = false;

    this.state = useState({
      loading: true,
      saving: false,
      project: null,
      attachments: [],
      uploadingAttachments: false,
      // form fields editable (project.project)
      form: {
        name: "",
        partner_id: null,
        date_start: false,
        date: false,
        contract_id: null,
        stage_id: null,
        description: "",
      },

      // counters for smart buttons
      stats: {
        task_count_custom: 0,
        work_item_count: 0,
        cost_estimate_count: 0,
        project_expense_custom_count: 0,
        claim_report_count: 0,
        acceptance_report_count: 0,
        customer_invoice_count: 0,
      },

      // readonly displays
      display: {
        signature_date: false,
        location: "",
        sale_order_name: "",
        partner_name: "",
        contract_name: "",
        value_contract: 0,
        value_settlement: 0,
        value_completed: 0,
        value_remaining: 0,

        progress_percent: 0,
        claim_progress_percent: 0,
        acceptance_progress_percent: 0,

        claim_value_done: 0,
        claim_value_remaining: 0,
        acceptance_value_done: 0,
        acceptance_value_remaining: 0,

        sales_category_text: "",
      },

      // related rows
      work_items: [],
      tasks: [],

      // select options
      partnerOptions: [],
      stageOptions: [],
      contractOptions: [],
      userOptions: [],

      // multi-select work items for batch assignment
      selectedWorkItemMap: {},

      // batch assignment values
      batchAssign: {
        assigned_user_id: null,
        claim_user_id: null,
        acceptance_user_id: null,
      },
    });

    onWillStart(async () => {
      await this.loadAll();
    });
  }

  // =========================
  // Helpers
  // =========================
  money(v) {
    return this._nf0.format(num(v));
  }

  noop() {}

  _m2oId(v) {
    if (!v) return null;
    if (Array.isArray(v)) return Number(v[0]) || null;
    if (typeof v === "number") return v;
    if (typeof v === "object" && v.id) return Number(v.id) || null;
    return null;
  }

  _m2oName(v) {
    if (!v) return "";
    if (Array.isArray(v)) return v[1] || "";
    if (typeof v === "object") return v.display_name || v.name || "";
    return "";
  }

  _userNameById(userId) {
    const u = (this.state.userOptions || []).find(
      (x) => Number(x.id) === Number(userId),
    );
    return u?.name || "";
  }

  _clampPercent(v) {
    const n = num(v);
    if (!Number.isFinite(n)) return 0;
    if (n < 0) return 0;
    if (n > 100) return 100;
    return n;
  }

  _progressToneClass(v) {
    const n = num(v);
    if (n >= 100) return "is-done";
    if (n >= 70) return "is-good";
    if (n >= 30) return "is-mid";
    return "is-low";
  }

  _actionWithFallbackViews(
    action,
    fallbackViews = [
      [false, "list"],
      [false, "form"],
    ],
    fallbackViewMode = "list,form",
  ) {
    if (!action) return action;
    const next = { ...action };
    if (!Array.isArray(next.views)) {
      next.views = fallbackViews;
    }
    if (!next.view_mode) {
      next.view_mode = fallbackViewMode;
    }
    return next;
  }

  async _doActionSafe(action, fallbackViews, fallbackViewMode) {
    if (!action) return;
    const safeAction = this._actionWithFallbackViews(
      action,
      fallbackViews,
      fallbackViewMode,
    );
    return this.action.doAction(safeAction);
  }

  // =========================
  // Initial load
  // =========================
  async loadAll() {
    try {
      this.state.loading = true;

      // Load options first
      await Promise.all([
        this._loadPartners(),
        this._loadStages(),
        this._loadContracts(),
        this._loadUsers(),
      ]);

      // First load
      await this._loadProject();

      // Auto sync from contract/SO on open
      await this._autoSyncProjectAndWorkItemsOnOpen();

      // Reload after sync
      await this._loadProject();
    } catch (e) {
      console.error("[PWF Owl Form] loadAll error:", e);
      this.notification.add("Không tải được dữ liệu form dự án.", {
        type: "danger",
      });
    } finally {
      this.state.loading = false;
    }
  }

  // =========================
  // Auto sync on open
  // =========================
  async _autoSyncProjectAndWorkItemsOnOpen() {
    if (this._autoSyncedOnOpen) return;
    this._autoSyncedOnOpen = true;

    const pid = this.props.projectId;
    if (!pid) return;

    const hasContract = !!this.state.form?.contract_id;
    const hasSaleOrder = !!this._m2oId(this.state.project?.sale_order_id);
    if (!hasContract && !hasSaleOrder) return;

    try {
      // Preferred method: sync header + work items
      await this.orm.call(
        "project.project",
        "action_sync_project_data_from_contract_so",
        [[pid]],
      );
    } catch (e) {
      console.warn(
        "[PWF Owl Form] action_sync_project_data_from_contract_so fail, fallback sync work items:",
        e,
      );
      try {
        // Fallback: sync only work items
        await this.orm.call(
          "project.project",
          "action_sync_work_items_from_so",
          [[pid]],
        );
      } catch (e2) {
        console.warn(
          "[PWF Owl Form] fallback action_sync_work_items_from_so fail:",
          e2,
        );
      }
    }
  }

  // =========================
  // Ensure selected options exist (when not in top limit)
  // =========================
  async _ensureSelectedPartnerOption(partnerId) {
    if (!partnerId) return;
    const exists = (this.state.partnerOptions || []).some(
      (p) => Number(p.id) === Number(partnerId),
    );
    if (exists) return;

    try {
      const [rec] = await this.orm.read("res.partner", [partnerId], ["name"]);
      if (rec) {
        this.state.partnerOptions = [
          { id: rec.id, name: rec.name || `#${rec.id}` },
          ...(this.state.partnerOptions || []),
        ];
      }
    } catch (e) {
      console.warn("[PWF Owl Form] ensure partner option fail:", e);
    }
  }

  async _ensureSelectedStageOption(stageId) {
    if (!stageId) return;
    const exists = (this.state.stageOptions || []).some(
      (s) => Number(s.id) === Number(stageId),
    );
    if (exists) return;

    try {
      const [rec] = await this.orm.read(
        "project.project.stage",
        [stageId],
        ["name", "sequence"],
      );
      if (rec) {
        this.state.stageOptions = [
          { id: rec.id, name: rec.name || `#${rec.id}` },
          ...(this.state.stageOptions || []),
        ];
      }
    } catch (e) {
      console.warn("[PWF Owl Form] ensure stage option fail:", e);
    }
  }

  async _ensureSelectedContractOption(contractId) {
    if (!contractId) return;
    const exists = (this.state.contractOptions || []).some(
      (c) => Number(c.id) === Number(contractId),
    );
    if (exists) return;

    try {
      const [rec] = await this.orm.read(
        "contract.management",
        [contractId],
        ["name", "num_contract", "sale_order_id"],
      );
      if (rec) {
        this.state.contractOptions = [
          {
            id: rec.id,
            // ✅ ưu tiên num_contract
            name: rec.num_contract || rec.name || `HĐ #${rec.id}`,
            sale_order_name: Array.isArray(rec.sale_order_id)
              ? rec.sale_order_id[1] || ""
              : "",
          },
          ...(this.state.contractOptions || []),
        ];
      }
    } catch (e) {
      console.warn("[PWF Owl Form] ensure contract option fail:", e);
    }
  }

  async _ensureSelectedUserOption(userId) {
    if (!userId) return;
    const exists = (this.state.userOptions || []).some(
      (u) => Number(u.id) === Number(userId),
    );
    if (exists) return;

    try {
      const [rec] = await this.orm.read("res.users", [userId], ["name"]);
      if (rec) {
        this.state.userOptions = [
          { id: rec.id, name: rec.name || `#${rec.id}` },
          ...(this.state.userOptions || []),
        ];
      }
    } catch (e) {
      console.warn("[PWF Owl Form] ensure user option fail:", e);
    }
  }

  async _ensureUsersForWorkItems(rows) {
    const ids = new Set();
    for (const wi of rows || []) {
      const assignedId = this._m2oId(wi.assigned_user_id);
      const claimId = this._m2oId(wi.claim_user_id);
      const acceptanceId = this._m2oId(wi.acceptance_user_id);
      if (assignedId) ids.add(assignedId);
      if (claimId) ids.add(claimId);
      if (acceptanceId) ids.add(acceptanceId);
    }
    if (!ids.size) return;
    await Promise.all([...ids].map((id) => this._ensureSelectedUserOption(id)));
  }

  // =========================
  // Load project
  // =========================
  async _loadProject() {
    const pid = this.props.projectId;
    if (!pid) return;

    const fields = [
      "name",
      "partner_id",
      "date_start",
      "date",
      "contract_id",
      "stage_id",
      "description",
      "signature_date",
      "location",
      "sale_order_id",

      "value_contract",
      "value_settlement",
      "value_completed",
      "value_remaining",

      "progress_percent",
      "claim_progress_percent",
      "acceptance_progress_percent",

      "claim_value_done",
      "claim_value_remaining",
      "acceptance_value_done",
      "acceptance_value_remaining",
      "value_arise",
      "sales_category_ids",
      "customer_invoice_amount_total",
      "customer_invoice_received_total",
      "customer_invoice_untaxed_total",
      "customer_invoice_remaining_total",
      "payment_process_percent",

      "task_count_custom",
      "work_item_count",
      "cost_estimate_count",
      "project_expense_custom_count",
      "claim_report_count",
      "acceptance_report_count",
        "customer_invoice_count",
    ];

    const [rec] = await this.orm.read("project.project", [pid], fields);
    if (!rec) return;

    this.state.project = rec;

    const partnerId = this._m2oId(rec.partner_id);
    const contractId = this._m2oId(rec.contract_id);
    const stageId = this._m2oId(rec.stage_id);

    await Promise.all([
      this._ensureSelectedPartnerOption(partnerId),
      this._ensureSelectedContractOption(contractId),
      this._ensureSelectedStageOption(stageId),
    ]);
    let contractDisplayName = this._m2oName(rec.contract_id);
    if (contractId) {
      try {
        const [c] = await this.orm.read(
          "contract.management",
          [contractId],
          ["num_contract", "name"],
        );
        if (c) {
          contractDisplayName = c.num_contract || c.name || contractDisplayName;
        }
      } catch {
        // fallback giữ nguyên
      }
    }
    this.state.form = {
      name: rec.name || "",
      partner_id: partnerId,
      date_start: rec.date_start || false,
      date: rec.date || false,
      contract_id: contractId,
      stage_id: stageId,
      description: markup(rec.description || ""),
    };

    this.state.stats = {
      task_count_custom: num(rec.task_count_custom),
      work_item_count: num(rec.work_item_count),
      cost_estimate_count: num(rec.cost_estimate_count),
      project_expense_custom_count: num(rec.project_expense_custom_count),
      claim_report_count: num(rec.claim_report_count),
      acceptance_report_count: num(rec.acceptance_report_count),
        customer_invoice_count: num(rec.customer_invoice_count),
    };

    let salesCategoryText = "";
    try {
      if (rec.sales_category_ids?.length) {
        const pairs = await this.orm.call(
          "sale.order.category",
          "name_get",
          [rec.sales_category_ids],
          {},
        );
        salesCategoryText = (pairs || []).map((x) => x[1]).join(", ");
      }
    } catch {
      salesCategoryText = "";
    }

    this.state.display = {
      signature_date: rec.signature_date || false,
      location: rec.location || "",
      sale_order_name: this._m2oName(rec.sale_order_id),
      partner_name: this._m2oName(rec.partner_id),
      contract_name: contractDisplayName,

      value_contract: num(rec.value_contract),
      value_settlement: num(rec.value_settlement),
      value_completed: num(rec.value_completed),
      value_remaining: num(rec.value_remaining),
      value_arise: num(rec.value_arise),
      progress_percent: num(rec.progress_percent),
      claim_progress_percent: num(rec.claim_progress_percent),
      acceptance_progress_percent: num(rec.acceptance_progress_percent),

      claim_value_done: num(rec.claim_value_done),
      claim_value_remaining: num(rec.claim_value_remaining),
      acceptance_value_done: num(rec.acceptance_value_done),
      acceptance_value_remaining: num(rec.acceptance_value_remaining),
      customer_invoice_amount_total: num(rec.customer_invoice_amount_total),
      customer_invoice_received_total: num(rec.customer_invoice_received_total),
      customer_invoice_untaxed_total: num(rec.customer_invoice_untaxed_total),
        customer_invoice_remaining_total: num(rec.customer_invoice_remaining_total),
      payment_process_percent: num(rec.payment_process_percent),
      sales_category_text: salesCategoryText,
    };

    await Promise.all([
      this._loadWorkItems(),
      this._loadTasks(),
      this._loadAttachments(),
    ]);
  }

  // =========================
  // Load options
  // =========================
  async _loadPartners() {
    try {
      const rows = await this.orm.searchRead(
        "res.partner",
        [["is_company", "=", true]],
        ["name"],
        { limit: 200, order: "name asc" },
      );
      this.state.partnerOptions = (rows || []).map((r) => ({
        id: r.id,
        name: r.name || "",
      }));
    } catch (e) {
      console.warn("[PWF Owl Form] load partners fail:", e);
      this.state.partnerOptions = [];
    }
  }

  async _loadStages() {
    try {
      const rows = await this.orm.searchRead(
        "project.project.stage",
        [],
        ["name", "sequence"],
        { limit: 200, order: "sequence asc, id asc" },
      );
      this.state.stageOptions = (rows || []).map((r) => ({
        id: r.id,
        name: r.name || "",
      }));
    } catch (e) {
      console.warn("[PWF Owl Form] load stages fail:", e);
      this.state.stageOptions = [];
    }
  }

  async _loadContracts() {
    try {
      const rows = await this.orm.searchRead(
        "contract.management",
        [],
        ["name", "num_contract", "sale_order_id"],
        { limit: 200, order: "id desc" },
      );
      this.state.contractOptions = (rows || []).map((r) => ({
        id: r.id,
        // ✅ ưu tiên số hợp đồng
        name: r.num_contract || r.name || `HĐ #${r.id}`,
        sale_order_name: Array.isArray(r.sale_order_id)
          ? r.sale_order_id[1] || ""
          : "",
      }));
    } catch (e) {
      console.warn("[PWF Owl Form] load contracts fail:", e);
      this.state.contractOptions = [];
    }
  }

  async _loadUsers() {
    try {
      const rows = await this.orm.searchRead(
        "res.users",
        [["share", "=", false]],
        ["name"],
        { limit: 200, order: "name asc" },
      );
      this.state.userOptions = (rows || []).map((u) => ({
        id: u.id,
        name: u.name || "",
      }));
    } catch (e) {
      console.warn("[PWF Owl Form] load users fail:", e);
      this.state.userOptions = [];
    }
  }

  // =========================
  // Load related lists
  // =========================
  async _loadWorkItems() {
    const pid = this.props.projectId;
    if (!pid) {
      this.state.work_items = [];
      return;
    }

    try {
      const rows = await this.orm.searchRead(
        "project.work.item",
        [["project_id", "=", pid]],
        [
          "sequence",
          "name",
          "product_id",
          "description",
          "assigned_user_id",
          "claim_user_id",
          "acceptance_user_id",
          "qty_plan",
          "qty_arise",
          "qty_settlement",
          "qty_done",
          "qty_remaining",
          "progress_percent",
        ],
        { order: "sequence asc, id asc", limit: 500 },
      );

      await this._ensureUsersForWorkItems(rows || []);
      this.state.work_items = rows || [];

      // Clean selected map (keep only existing rows)
      const validIds = new Set((this.state.work_items || []).map((r) => r.id));
      const cleaned = {};
      for (const [k, v] of Object.entries(
        this.state.selectedWorkItemMap || {},
      )) {
        const id = Number(k);
        if (v && validIds.has(id)) cleaned[id] = true;
      }
      this.state.selectedWorkItemMap = cleaned;
    } catch (e) {
      console.warn("[PWF Owl Form] load work items fail:", e);
      this.state.work_items = [];
    }
  }

  async _loadTasks() {
    const pid = this.props.projectId;
    if (!pid) {
      this.state.tasks = [];
      return;
    }

    try {
      const rows = await this.orm.searchRead(
        "project.task",
        [["project_id", "=", pid]],
        ["name", "user_ids", "date_deadline", "priority"],
        { order: "id desc", limit: 300 },
      );
      this.state.tasks = rows || [];
    } catch (e) {
      console.warn("[PWF Owl Form] load tasks fail:", e);
      this.state.tasks = [];
    }
  }

  // =========================
  // Project form events
  // =========================
  onInput(ev) {
    const field = ev.target.dataset.field;
    if (!field) return;
    this.state.form[field] = ev.target.value;
  }

  onSelectMany2one(ev) {
    const field = ev.target.dataset.field;
    if (!field) return;
    const v = ev.target.value;
    this.state.form[field] = v ? Number(v) : null;
  }

  async saveForm() {
    try {
      this.state.saving = true;

      const pid = this.props.projectId;
      const vals = {
        name: this.state.form.name || "",
        partner_id: this.state.form.partner_id || false,
        date_start: this.state.form.date_start || false,
        date: this.state.form.date || false,
        contract_id: this.state.form.contract_id || false,
        stage_id: this.state.form.stage_id || false,
        description: this.state.form.description || false,
      };

      await this.orm.write("project.project", [pid], vals);
      this.notification.add("Đã lưu dự án.", { type: "success" });

      // nếu user đổi contract thì cho phép auto-sync lại lần sau
      this._autoSyncedOnOpen = false;
      await this._loadProject();
    } catch (e) {
      console.error("[PWF Owl Form] save error:", e);
      this.notification.add("Lưu dự án thất bại.", { type: "danger" });
    } finally {
      this.state.saving = false;
    }
  }

  // =========================
  // Work item row selection (for batch assign)
  // =========================
  isWorkItemSelected(workItemId) {
    return !!this.state.selectedWorkItemMap[workItemId];
  }

  get selectedWorkItemIds() {
    return Object.keys(this.state.selectedWorkItemMap || {})
      .filter((k) => !!this.state.selectedWorkItemMap[k])
      .map((k) => Number(k));
  }

  get selectedWorkItemCount() {
    return this.selectedWorkItemIds.length;
  }

  get allWorkItemsSelected() {
    const rows = this.state.work_items || [];
    if (!rows.length) return false;
    return rows.every((r) => !!this.state.selectedWorkItemMap[r.id]);
  }

  onToggleSelectAllWorkItems(ev) {
    ev.stopPropagation();
    const checked = !!ev.currentTarget.checked;
    const next = { ...(this.state.selectedWorkItemMap || {}) };

    for (const wi of this.state.work_items || []) {
      if (checked) next[wi.id] = true;
      else delete next[wi.id];
    }
    this.state.selectedWorkItemMap = next;
  }

  onToggleSelectWorkItem(ev) {
    ev.stopPropagation();
    const workItemId = Number(ev.currentTarget.dataset.workItemId || 0);
    if (!workItemId) return;

    const checked = !!ev.currentTarget.checked;
    const next = { ...(this.state.selectedWorkItemMap || {}) };

    if (checked) next[workItemId] = true;
    else delete next[workItemId];

    this.state.selectedWorkItemMap = next;
  }

  clearSelectedWorkItems() {
    this.state.selectedWorkItemMap = {};
  }
  onInputHtmlDescription(ev) {
    // Vì đây là contenteditable => lấy innerHTML thay vì value
    const html = ev.currentTarget?.innerHTML || "";
    this.state.form.description = html;
  }
  // =========================
  // Work item editable fields
  // =========================
  async onChangeWorkItemNumberField(ev) {
    const workItemId = Number(ev.currentTarget.dataset.workItemId || 0);
    const field = ev.currentTarget.dataset.field;
    if (!workItemId || !field) return;

    const raw = (ev.currentTarget.value || "").trim();
    const value = raw === "" ? 0 : Number(raw);

    if (!Number.isFinite(value)) {
      this.notification.add("Giá trị số không hợp lệ.", { type: "warning" });
      await this._loadWorkItems();
      return;
    }

    try {
      await this.orm.write("project.work.item", [workItemId], {
        [field]: value,
      });

      // cập nhật local row để UI phản hồi ngay
      const row = (this.state.work_items || []).find(
        (x) => Number(x.id) === Number(workItemId),
      );
      if (row) {
        row[field] = value;

        // cập nhật tạm qty_settlement tại client
        if (field === "qty_plan" || field === "qty_arise") {
          row.qty_settlement = num(row.qty_plan) + num(row.qty_arise);
        }
      }

      // refresh compute totals/percent ở project
      await this._loadProject();
    } catch (e) {
      console.error(e);
      this.notification.add("Không cập nhật được khối lượng.", {
        type: "danger",
      });
      await this._loadWorkItems();
    }
  }

  async onChangeWorkItemTextField(ev) {
    const workItemId = Number(ev.currentTarget.dataset.workItemId || 0);
    const field = ev.currentTarget.dataset.field;
    if (!workItemId || !field) return;

    const value = ev.currentTarget.value || "";

    try {
      await this.orm.write("project.work.item", [workItemId], {
        [field]: value,
      });

      // cập nhật local state để UI phản hồi ngay
      const row = (this.state.work_items || []).find(
        (x) => Number(x.id) === Number(workItemId),
      );
      if (row) {
        row[field] = value;
      }

      this.notification.add("Đã cập nhật mô tả hạng mục.", { type: "success" });
    } catch (e) {
      console.error(e);
      this.notification.add("Không cập nhật được mô tả.", { type: "danger" });
      await this._loadWorkItems();
    }
  }

  // =========================
  // Batch assign values + apply
  // =========================
  onChangeBatchAssignUser(ev) {
    const field = ev.currentTarget.dataset.field;
    if (!field) return;
    const v = ev.currentTarget.value;
    this.state.batchAssign[field] = v ? Number(v) : null;
  }

  async applyBatchAssignSelectedWorkItems() {
    const ids = this.selectedWorkItemIds;
    if (!ids.length) {
      this.notification.add("Chưa chọn hạng mục nào.", { type: "warning" });
      return;
    }

    const vals = {};
    const batch = this.state.batchAssign || {};

    if (batch.assigned_user_id !== null)
      vals.assigned_user_id = batch.assigned_user_id || false;
    if (batch.claim_user_id !== null)
      vals.claim_user_id = batch.claim_user_id || false;
    if (batch.acceptance_user_id !== null)
      vals.acceptance_user_id = batch.acceptance_user_id || false;

    if (!Object.keys(vals).length) {
      this.notification.add("Chưa chọn người để phân công hàng loạt.", {
        type: "warning",
      });
      return;
    }

    try {
      await this.orm.write("project.work.item", ids, vals);

      // Update local rows immediately
      for (const wi of this.state.work_items || []) {
        if (!ids.includes(Number(wi.id))) continue;

        if ("assigned_user_id" in vals) {
          wi.assigned_user_id = vals.assigned_user_id
            ? [
                vals.assigned_user_id,
                this._userNameById(vals.assigned_user_id) || "",
              ]
            : false;
        }
        if ("claim_user_id" in vals) {
          wi.claim_user_id = vals.claim_user_id
            ? [vals.claim_user_id, this._userNameById(vals.claim_user_id) || ""]
            : false;
        }
        if ("acceptance_user_id" in vals) {
          wi.acceptance_user_id = vals.acceptance_user_id
            ? [
                vals.acceptance_user_id,
                this._userNameById(vals.acceptance_user_id) || "",
              ]
            : false;
        }
      }

      this.notification.add(
        `Đã phân công hàng loạt cho ${ids.length} hạng mục.`,
        { type: "success" },
      );
      // this.clearSelectedWorkItems();
    } catch (e) {
      console.error(e);
      this.notification.add("Không phân công hàng loạt được.", {
        type: "danger",
      });
      await this._loadWorkItems();
    }
  }

  // =========================
  // Inline assign per work item
  // =========================
  async _writeWorkItemUserField(
    workItemId,
    fieldName,
    userIdOrFalse,
    successMessage,
  ) {
    try {
      await this.orm.write("project.work.item", [workItemId], {
        [fieldName]: userIdOrFalse || false,
      });

      const row = (this.state.work_items || []).find(
        (x) => Number(x.id) === Number(workItemId),
      );
      if (row) {
        if (userIdOrFalse) {
          await this._ensureSelectedUserOption(userIdOrFalse);
          const userName = this._userNameById(userIdOrFalse);
          row[fieldName] = [userIdOrFalse, userName || ""];
        } else {
          row[fieldName] = false;
        }
      }

      if (successMessage) {
        this.notification.add(successMessage, { type: "success" });
      }
    } catch (e) {
      console.error(e);
      this.notification.add("Không cập nhật được phân công.", {
        type: "danger",
      });
      await this._loadWorkItems();
    }
  }

  async onChangeWorkItemAssignedUser(ev) {
    const workItemId = Number(ev.currentTarget.dataset.workItemId || 0);
    if (!workItemId) return;
    const v = ev.currentTarget.value;
    const userId = v ? Number(v) : false;

    await this._writeWorkItemUserField(
      workItemId,
      "assigned_user_id",
      userId,
      "Đã cập nhật người phụ trách.",
    );
  }

  async onChangeWorkItemClaimUser(ev) {
    const workItemId = Number(ev.currentTarget.dataset.workItemId || 0);
    if (!workItemId) return;
    const v = ev.currentTarget.value;
    const userId = v ? Number(v) : false;

    await this._writeWorkItemUserField(
      workItemId,
      "claim_user_id",
      userId,
      "Đã cập nhật người báo cáo quyết toán.",
    );
  }

  async onChangeWorkItemAcceptanceUser(ev) {
    const workItemId = Number(ev.currentTarget.dataset.workItemId || 0);
    if (!workItemId) return;
    const v = ev.currentTarget.value;
    const userId = v ? Number(v) : false;

    await this._writeWorkItemUserField(
      workItemId,
      "acceptance_user_id",
      userId,
      "Đã cập nhật người báo cáo nghiệm thu.",
    );
  }

  // =========================
  // Smart button actions
  // =========================
  async openTasksAction() {
    try {
      const action = await this.orm.call(
        "project.project",
        "action_view_tasks_custom",
        [[this.props.projectId]],
      );
      await this._doActionSafe(
        action,
        [
          [false, "list"],
          [false, "form"],
        ],
        "list,form",
      );
    } catch (e) {
      console.error(e);
      this.notification.add("Không mở được danh sách nhiệm vụ.", {
        type: "danger",
      });
    }
  }

  async openWorkItemsAction() {
    try {
      const action = await this.orm.call(
        "project.project",
        "action_view_work_items",
        [[this.props.projectId]],
      );
      await this._doActionSafe(
        action,
        [
          [false, "list"],
          [false, "form"],
        ],
        "list,form",
      );
    } catch (e) {
      console.error(e);
      this.notification.add("Không mở được danh sách hạng mục công việc.", {
        type: "danger",
      });
    }
  }

  async openCostEstimatesAction() {
    try {
      const action = await this.orm.call(
        "project.project",
        "action_view_cost_estimates",
        [[this.props.projectId]],
      );
      await this._doActionSafe(
        action,
        [
          [false, "list"],
          [false, "form"],
        ],
        "list,form",
      );
    } catch (e) {
      console.error(e);
      this.notification.add("Không mở được danh sách dự toán chi phí.", {
        type: "danger",
      });
    }
  }

  async openClaimReportsAction() {
    try {
      const action = await this.orm.call(
        "project.project",
        "action_view_claim_reports",
        [[this.props.projectId]],
      );
      await this._doActionSafe(
        action,
        [
          [false, "list"],
          [false, "form"],
        ],
        "list,form",
      );
    } catch (e) {
      console.error(e);
      this.notification.add("Không mở được báo cáo quyết toán.", {
        type: "danger",
      });
    }
  }

  async openAcceptanceReportsAction() {
    try {
      const action = await this.orm.call(
        "project.project",
        "action_view_acceptance_reports",
        [[this.props.projectId]],
      );
      await this._doActionSafe(
        action,
        [
          [false, "list"],
          [false, "form"],
        ],
        "list,form",
      );
    } catch (e) {
      console.error(e);
      this.notification.add("Không mở được báo cáo nghiệm thu.", {
        type: "danger",
      });
    }
  }
  async openInvoiceReportsAction() {
    try {
      const action = await this.orm.call(
        "project.project",
        "action_view_customer_invoices",
        [[this.props.projectId]],
      );
      await this._doActionSafe(
        action,
        [
          [false, "list"],
          [false, "form"],
        ],
        "list,form",
      );
    } catch (e) {
      console.error(e);
      this.notification.add("Không mở được báo cáo hóa đơn.", {
        type: "danger",
      });
    }
  }
  async openExpenseDashboardAction() {
    try {
      const action = await this.orm.call(
        "project.project",
        "action_view_project_expense_custom",
        [[this.props.projectId]],
      );
      await this._doActionSafe(
        action,
        [
          [false, "list"],
          [false, "form"],
        ],
        "list,form",
      );
    } catch (e) {
      console.warn(e);
      this.notification.add(
        "Chưa có method action_view_project_expense_custom hoặc đang lỗi.",
        {
          type: "warning",
        },
      );
    }
  }

  async syncWorkItemsFromSO() {
    try {
      const pid = this.props.projectId;

      try {
        await this.orm.call(
          "project.project",
          "action_sync_project_data_from_contract_so",
          [[pid]],
        );
      } catch {
        await this.orm.call(
          "project.project",
          "action_sync_work_items_from_so",
          [[pid]],
        );
      }

      this.notification.add("Đã đồng bộ dữ liệu từ hợp đồng/đơn bán.", {
        type: "success",
      });
      await this._loadProject();
    } catch (e) {
      console.error(e);
      this.notification.add(e?.message || "Không đồng bộ được dữ liệu.", {
        type: "danger",
      });
    }
  }

  openStandardForm() {
    this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "project.project",
      res_id: this.props.projectId,
      view_mode: "form",
      views: [[this.props.formViewId || false, "form"]],
      target: "current",
      context: { open_work_custom: 1 },
    });
  }

  // =========================
  // Computed getters
  // =========================
  get progressPercentRounded() {
    return Math.round(num(this.state.display.progress_percent));
  }

  get claimProgressPercentRounded() {
    return Math.round(num(this.state.display.claim_progress_percent));
  }

  get acceptanceProgressPercentRounded() {
    return Math.round(num(this.state.display.acceptance_progress_percent));
  }
  // =========================
  // Attachments
  // =========================
  async _loadAttachments() {
    const pid = this.props.projectId;
    if (!pid) {
      this.state.attachments = [];
      return;
    }

    try {
      const rows = await this.orm.searchRead(
        "ir.attachment",
        [
          ["res_model", "=", "project.project"],
          ["res_id", "=", pid],
          ["type", "=", "binary"],
        ],
        ["name", "mimetype", "file_size", "create_date", "create_uid"],
        { order: "id desc", limit: 200 },
      );
      this.state.attachments = rows || [];
    } catch (e) {
      console.warn("[PWF Owl Form] load attachments fail:", e);
      this.state.attachments = [];
    }
  }
  _fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const result = String(reader.result || "");
          const base64 = result.includes(",") ? result.split(",")[1] : result;
          resolve(base64 || "");
        } catch (err) {
          reject(err);
        }
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  formatFileSize(bytes) {
    const n = Number(bytes || 0);
    if (!Number.isFinite(n) || n <= 0) return "0 B";
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
    return `${(n / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  }

  formatDateTime(dt) {
    if (!dt) return "";
    try {
      return new Date(dt).toLocaleString("vi-VN");
    } catch {
      return dt;
    }
  }
  attachmentUrl(attId, download = true) {
    return `/web/content/${attId}?download=${download ? "true" : "false"}`;
  }

  isImageAttachment(att) {
    const mt = (att?.mimetype || "").toLowerCase();
    return mt.startsWith("image/");
  }
  attachmentImageThumbUrl(attId) {
    // thumbnail ảnh (nhanh hơn load full)
    return `/web/image/ir.attachment/${attId}/datas?width=220&height=140`;
  }
  attachmentPreviewUrl(attId) {
    // preview inline (pdf, image, file browser hỗ trợ)
    return `/web/content/${attId}?download=false`;
  }
  isPdfAttachment(att) {
    const mt = (att?.mimetype || "").toLowerCase();
    const name = (att?.name || "").toLowerCase();
    return mt === "application/pdf" || name.endsWith(".pdf");
  }

  hasInlinePreview(att) {
    return this.isImageAttachment(att) || this.isPdfAttachment(att);
  }
  async onPickAttachments(ev) {
    const files = Array.from(ev.target?.files || []);
    if (!files.length) return;

    const pid = this.props.projectId;
    if (!pid) {
      this.notification.add("Không xác định được dự án để đính kèm tệp.", {
        type: "warning",
      });
      return;
    }

    try {
      this.state.uploadingAttachments = true;

      for (const file of files) {
        const datas = await this._fileToBase64(file);

        await this.orm.call("ir.attachment", "create", [
          {
            name: file.name,
            datas: datas,
            type: "binary",
            mimetype: file.type || false,
            res_model: "project.project",
            res_id: pid,
          },
        ]);
      }

      this.notification.add(`Đã tải lên ${files.length} tệp.`, {
        type: "success",
      });
      await this._loadAttachments();
    } catch (e) {
      console.error(e);
      this.notification.add("Không tải lên được tệp đính kèm.", {
        type: "danger",
      });
    } finally {
      this.state.uploadingAttachments = false;
      // reset input để chọn lại cùng file vẫn trigger onChange
      if (ev.target) ev.target.value = "";
    }
  }

  async removeAttachment(ev) {
    const attId = Number(ev.currentTarget?.dataset?.attachmentId || 0);
    if (!attId) return;

    try {
      await this.orm.unlink("ir.attachment", [attId]);
      this.state.attachments = (this.state.attachments || []).filter(
        (a) => Number(a.id) !== attId,
      );
      this.notification.add("Đã xóa tệp đính kèm.", { type: "success" });
    } catch (e) {
      console.error(e);
      this.notification.add("Không xóa được tệp đính kèm.", { type: "danger" });
    }
  }
}
