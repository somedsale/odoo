# -*- coding: utf-8 -*-
from odoo import api, fields, models
from datetime import datetime, date, timedelta
import calendar


class PlannedPaymentWizard(models.TransientModel):
    _name = "planned.payment.wizard"
    _description = "Wizard: Planned Payment - select lines then print"

    # ===== NEW: kiểu lọc thời gian =====
    date_mode = fields.Selection([
        ("range", "Khoảng ngày"),
        ("month", "Theo tháng"),
        ("quarter", "Theo quý"),
        ("year", "Theo năm"),
    ], string="Kiểu lọc", default="range", required=True)

    year = fields.Integer(string="Năm", default=lambda self: fields.Date.context_today(self).year)
    month = fields.Selection([(str(i), f"Tháng {i}") for i in range(1, 13)], string="Tháng")
    quarter = fields.Selection([("1", "Quý I"), ("2", "Quý II"), ("3", "Quý III"), ("4", "Quý IV")], string="Quý")

    date_from = fields.Date(string="Từ ngày")
    date_to = fields.Date(string="Đến ngày")

    include_po = fields.Boolean(string="Lấy từ PO", default=True)
    include_expense = fields.Boolean(string="Lấy từ phiếu đề xuất", default=True)

    state_filter_ids = fields.Many2many(
        "proposal.sheet.state.option",
        string="Trạng thái phiếu đề xuất",
        domain=[("active", "=", True)],
    )

    line_ids = fields.One2many("planned.payment.wizard.line", "wizard_id", string="Dòng dự kiến")

    PLANNED_PO_STATUSES = ("in_progress", "not_shipped")

    # =========================
    # Helpers
    # =========================
    def _action_open_self(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Dự kiến thanh toán",
            "res_model": "planned.payment.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _get_date_range(self):
        """Trả về (df, dt) theo mode; đảm bảo dt >= df."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        y = self.year or today.year

        if self.date_mode == "range":
            df = self.date_from or today
            dt = self.date_to or df
        elif self.date_mode == "month":
            m = int(self.month or today.month)
            last_day = calendar.monthrange(y, m)[1]
            df = date(y, m, 1)
            dt = date(y, m, last_day)
        elif self.date_mode == "quarter":
            q = int(self.quarter or ((today.month - 1) // 3 + 1))
            start_m = (q - 1) * 3 + 1
            end_m = start_m + 2
            end_day = calendar.monthrange(y, end_m)[1]
            df = date(y, start_m, 1)
            dt = date(y, end_m, end_day)
        else:  # year
            df = date(y, 1, 1)
            dt = date(y, 12, 31)

        if dt < df:
            df, dt = dt, df
        return df, dt

    @api.onchange("date_mode", "year", "month", "quarter")
    def _onchange_date_mode(self):
        """Auto set date_from/date_to khi chọn tháng/quý/năm."""
        for w in self:
            if w.date_mode == "range":
                return
            df, dt = w._get_date_range()
            w.date_from = df
            w.date_to = dt

    # =========================
    # Actions
    # =========================
    def action_reload(self):
        self.ensure_one()
        self._load_candidates(clear_existing=True)
        return self._action_open_self()

    def action_select_all(self):
        self.ensure_one()
        self.line_ids.write({"include": True})
        return self._action_open_self()  # ✅ không reload (reload sẽ unlink mất)

    def action_unselect_all(self):
        self.ensure_one()
        self.line_ids.write({"include": False})
        return self._action_open_self()  # ✅ không reload

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref("expense_proposal.action_report_planned_payment_wiz_pdf").report_action(self)

    def action_print_html(self):
        self.ensure_one()
        return self.env.ref("expense_proposal.action_report_planned_payment_wiz_html").report_action(self)

    # =========================
    # LOAD CANDIDATES
    # =========================
    def _load_candidates(self, clear_existing=False):
        self.ensure_one()
        if clear_existing:
            self.line_ids.unlink()

        ProposalSheet = self.env["proposal.sheet"]
        PurchaseLine = self.env["purchase.order.line"]
        WizardLine = self.env["planned.payment.wizard.line"]

        epoch = datetime(1970, 1, 1)

        # ✅ dùng range theo mode
        df, dt = self._get_date_range()

        def _amount_from_any(line):
            for f in ("amount", "price_total", "price_subtotal"):
                if hasattr(line, f):
                    return float(getattr(line, f) or 0.0)
            qty = getattr(line, "product_qty", 0.0) or getattr(line, "quantity", 0.0) or 0.0
            pu = getattr(line, "price_unit", 0.0) or 0.0
            return float(qty * pu)

        def _note_from_any(line, parent_doc=None):
            note = getattr(line, "note", "") or ""
            if not note and parent_doc:
                for f in ("note", "notes", "narration"):
                    if hasattr(parent_doc, f):
                        note = getattr(parent_doc, f) or ""
                        if note:
                            break
            return note

        def _line_name(line):
            if getattr(line, "content", False):
                return line.content or ""
            if getattr(line, "expense_id", False):
                return line.expense_id.display_name or ""
            if getattr(line, "name", False):
                return line.name or ""
            return ""

        def _vendor_display_and_partner(line, po_partner=None):
            partner = False
            if getattr(line, "object", False):
                obj = line.object
                name = (obj.display_name or getattr(obj, "name", "") or "").strip()
                if obj._name == "res.partner":
                    partner = obj
                return (name or "khác", partner)

            if getattr(line, "vendor_id", False):
                partner = line.vendor_id
                return ((partner.display_name or "").strip() or "khác", partner)

            if getattr(line, "partner_id", False):
                partner = line.partner_id
                return ((partner.display_name or "").strip() or "khác", partner)

            if po_partner:
                return ((po_partner.display_name or "").strip() or "khác", po_partner)

            return ("khác", False)

        def _date_from_any(line, po_date=None):
            d = getattr(line, "date", False)
            if d:
                return d
            if po_date:
                return po_date.date()
            return False

        # =========================
        # A) proposal.sheet (date_proposal là Date -> dùng df/dt trực tiếp)
        # =========================
        if self.include_expense:
            sheet_domain = [("type", "in", ["expense"])]

            if self.state_filter_ids:
                keys = self.state_filter_ids.mapped("key")
                sheet_domain.append(("state", "in", keys))
            else:
                sheet_domain.append(("state", "!=", "draft"))

            sheet_domain.append(("date_proposal", ">=", df))
            sheet_domain.append(("date_proposal", "<=", dt))

            sheets = ProposalSheet.search(sheet_domain, order="project_id, date_proposal, id")

            for s in sheets:
                project_id = s.project_id.id if s.project_id else False
                doc_ref = getattr(s, "name", False) or s.display_name

                for l in s.expense_noproject_line_ids:
                    vendor_name, vendor_partner = _vendor_display_and_partner(l)
                    WizardLine.create({
                        "wizard_id": self.id,
                        "include": True,
                        "project_id": project_id,
                        "vendor_id": vendor_partner.id if vendor_partner else False,
                        "vendor_name": vendor_name,
                        "date": _date_from_any(l),
                        "name": _line_name(l),
                        "amount": _amount_from_any(l),
                        "note": _note_from_any(l, parent_doc=s),
                        "document_ref": doc_ref,
                        "source_model": l._name,
                        "source_id": l.id,
                    })

                for l in s.expense_line_ids:
                    vendor_name, vendor_partner = _vendor_display_and_partner(l)
                    WizardLine.create({
                        "wizard_id": self.id,
                        "include": True,
                        "project_id": project_id,
                        "vendor_id": vendor_partner.id if vendor_partner else False,
                        "vendor_name": vendor_name,
                        "date": _date_from_any(l),
                        "name": _line_name(l),
                        "amount": _amount_from_any(l),
                        "category": "expense",
                        "note": _note_from_any(l, parent_doc=s),
                        "document_ref": doc_ref,
                        "source_model": l._name,
                        "source_id": l.id,
                    })

        # =========================
        # B) purchase.order.line (date_order là Datetime -> FIX end date)
        # =========================
        if self.include_po:
            dt_from = fields.Datetime.to_datetime(df)  # 00:00
            dt_to_exclusive = fields.Datetime.to_datetime(dt) + timedelta(days=1)  # < ngày kế tiếp 00:00

            po_domain = [
                ("display_type", "=", False),
                ("order_id.state", "!=", "cancel"),
                ("order_id.shipping_status", "in", list(self.PLANNED_PO_STATUSES)),
                ("order_id.date_order", ">=", dt_from),
                ("order_id.date_order", "<", dt_to_exclusive),  # ✅ chuẩn, không hụt date_to
            ]

            po_lines = PurchaseLine.search(po_domain, order="order_id, id")

            def _po_sort_key(l):
                proj = getattr(l.order_id, "project_id", False)
                proj_id = proj.id if proj else 0
                d = l.order_id.date_order or epoch
                return (proj_id, d, l.order_id.id, l.id)

            po_lines = po_lines.sorted(_po_sort_key)

            for pol in po_lines:
                po = pol.order_id
                project_id = po.project_id.id if getattr(po, "project_id", False) else False
                vendor_name, vendor_partner = _vendor_display_and_partner(pol, po_partner=po.partner_id)

                WizardLine.create({
                    "wizard_id": self.id,
                    "include": True,
                    "project_id": project_id,
                    "vendor_id": vendor_partner.id if vendor_partner else False,
                    "vendor_name": vendor_name,
                    "date": _date_from_any(pol, po_date=po.date_order),
                    "name": _line_name(pol),
                    "category": "material",
                    "amount": _amount_from_any(pol),
                    "note": _note_from_any(pol, parent_doc=po),
                    "document_ref": po.name,
                    "source_model": pol._name,
                    "source_id": pol.id,
                })

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for r in recs:
            r._load_candidates(clear_existing=True)
        return recs



class PlannedPaymentWizardLine(models.TransientModel):
    _name = "planned.payment.wizard.line"
    _description = "Wizard Line: Planned Payment"

    wizard_id = fields.Many2one("planned.payment.wizard", required=True, ondelete="cascade")
    include = fields.Boolean(string="Chọn", default=True)

    project_id = fields.Many2one("project.project", string="Công trình")
    vendor_id = fields.Many2one("res.partner", string="Đối tượng chi")
    vendor_name = fields.Char(string="Tên đối tượng chi")

    date = fields.Date(string="Ngày")
    name = fields.Char(string="Nội dung")

    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)
    amount = fields.Monetary(string="Giá trị", currency_field="currency_id")

    document_ref = fields.Char(string="Chứng từ")
    note = fields.Char(string="Ghi chú")
    category = fields.Selection([
    ("expense", "Chi phí"),
    ("material", "Vật tư"),
], string="Loại")

    source_model = fields.Char()
    source_id = fields.Integer()
    source_display = fields.Char(string="Nguồn", compute="_compute_source_display", store=False)

    @api.depends("source_model", "source_id")
    def _compute_source_display(self):
        for r in self:
            r.source_display = f"{r.source_model},{r.source_id}" if (r.source_model and r.source_id) else ""
