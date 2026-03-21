# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectWorkAssignment(models.Model):
    _name = "project.work.assignment"
    _description = "Work Assignment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    active = fields.Boolean(default=True)
    name = fields.Char(string="Công việc", compute="_compute_name", store=True)
    project_id = fields.Many2one("project.project", string="Dự án", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="project_id.company_id", store=True, readonly=True)

    work_item_id = fields.Many2one("project.work.item", string="Work Item", required=True, ondelete="cascade")
    user_id = fields.Many2one("res.users", string="Người được phân công", required=True)

    # chỉ giữ 1 field description thôi, tránh khai báo trùng
    description = fields.Text(related="work_item_id.description", store=True, readonly=True)

    date_start = fields.Date(string="Ngày bắt đầu", related="project_id.date_start", store=True, readonly=True)

    work_item_name = fields.Char(related="work_item_id.name", store=True, readonly=True)
    product_id = fields.Many2one(related="work_item_id.product_id", store=True, readonly=True)
    uom_id = fields.Many2one(related="work_item_id.uom_id", store=True, readonly=True)
    qty_plan = fields.Float(related="work_item_id.qty_plan", store=True, readonly=True, digits="Product Unit of Measure")
    qty_settlement = fields.Float(related="work_item_id.qty_settlement", store=True, readonly=True, digits="Product Unit of Measure")
    price_unit = fields.Float(related="work_item_id.so_line_id.price_unit", store=True, readonly=True, digits="Product Price")
    so_line_id = fields.Many2one(
        related="work_item_id.so_line_id",
        string="Dòng đơn bán",
        store=True,
        readonly=True,
    )
    tax_id = fields.Many2many(
    related="work_item_id.so_line_id.tax_id",
    string="Thuế",
    store=False,
    readonly=True,
    )
    price_subtotal = fields.Monetary(
    related="work_item_id.so_line_id.price_subtotal",
    string="Thành tiền trước thuế",
    store=True,
    readonly=True,
    currency_field="currency_id",
    )

    price_total = fields.Monetary(
        related="work_item_id.so_line_id.price_total",
        string="Thành tiền sau thuế",
        store=True,
        readonly=True,
        currency_field="currency_id",
    )
    progress_ids = fields.One2many("project.work.progress", "assignment_id", string="Lịch sử kỳ")
    qty_done = fields.Float(string="Đã thực hiện", compute="_compute_qty_done", store=True, digits="Product Unit of Measure")
    qty_remaining = fields.Float(string="Còn lại", compute="_compute_qty_done", store=True, digits="Product Unit of Measure")
    qty_item_done = fields.Float(related="work_item_id.qty_done", store=True, readonly=True, digits="Product Unit of Measure")
    qty_item_remaining = fields.Float(related="work_item_id.qty_remaining", store=True, readonly=True, digits="Product Unit of Measure")
    value_completed = fields.Monetary(string="Giá trị hoàn thành", compute="_compute_qty_done", store=True)
    currency_id = fields.Many2one(related="project_id.company_id.currency_id", store=True, readonly=True)
    progress_percent = fields.Float(string="% Hoàn thành", related="work_item_id.progress_percent", store=True)
    attachment_ids = fields.Many2many("ir.attachment", related="project_id.attachment_ids", string="Tài liệu đính kèm", store=False, readonly=True)
    section_name = fields.Char(related="work_item_id.section_name", store=True, readonly=True)

    @api.depends("work_item_id", "work_item_id.name")
    def _compute_name(self):
        for rec in self:
            rec.name = rec.work_item_id.name or ""

    @api.depends("qty_plan", "progress_ids.qty_cum", "progress_ids.period_no", "price_unit")
    def _compute_qty_done(self):
        Progress = self.env["project.work.progress"]
        for rec in self:
            last = Progress.search([("assignment_id", "=", rec.id)], order="period_no desc", limit=1)
            done = last.qty_cum if last else 0.0
            rec.qty_done = done
            rec.qty_remaining = max(0.0, (rec.qty_plan or 0.0) - done)
            rec.value_completed = (done * rec.price_unit) if rec.price_unit else 0.0

    current_period_no = fields.Integer(string="Kỳ hiện tại", compute="_compute_current_period", store=False)
    current_period_start = fields.Date(string="Từ ngày", compute="_compute_current_period", store=False)
    current_period_end = fields.Date(string="Đến ngày", compute="_compute_current_period", store=False)

    prev_qty_cum = fields.Float(string="Lũy kế kỳ trước", compute="_compute_current_period", store=False, digits="Product Unit of Measure")
    current_qty_cum = fields.Float(string="Lũy kế kỳ hiện tại", compute="_compute_current_period", store=False, digits="Product Unit of Measure")
    current_qty_period = fields.Float(string="Sản lượng kỳ (tính)", compute="_compute_current_period", store=False, digits="Product Unit of Measure")

    current_qty_week = fields.Float(
        string="Sản lượng trong kỳ",
        compute="_compute_current_period",
        inverse="_inverse_current_period",
        store=False,
        digits="Product Unit of Measure",
    )
    current_note = fields.Text(
        string="Ghi chú",
        compute="_compute_current_period",
        inverse="_inverse_current_period",
        store=False,
    )

    def _get_period_bounds(self, start_date, period_no):
        start = fields.Date.to_date(start_date)
        p1_end = start + timedelta(days=(5 - start.weekday()) % 7)  # Saturday=5
        if period_no == 1:
            return start, p1_end

        p2_start = p1_end + timedelta(days=(7 - p1_end.weekday()) % 7)
        pn_start = p2_start + timedelta(days=(period_no - 2) * 7)
        pn_end = pn_start + timedelta(days=5)
        return pn_start, pn_end

    def _get_current_period_no(self, start_date, today):
        start = fields.Date.to_date(start_date)
        today = fields.Date.to_date(today)
        p1_start, p1_end = self._get_period_bounds(start, 1)
        if today <= p1_end:
            return 1
        p2_start = p1_end + timedelta(days=(7 - p1_end.weekday()) % 7)
        if today < p2_start:
            return 2
        offset = (today - p2_start).days
        return 2 + (offset // 7)

    @api.depends(
        "date_start",
        "progress_ids.qty_cum",
        "progress_ids.note",
        "progress_ids.period_no",
        "project_id.stage_id",
        "project_id.report_closed_period_no",
    )
    def _compute_current_period(self):
        Progress = self.env["project.work.progress"]
        today = fields.Date.context_today(self)

        for rec in self:
            if not rec.date_start:
                rec.current_period_no = 0
                rec.current_period_start = False
                rec.current_period_end = False
                rec.prev_qty_cum = 0.0
                rec.current_qty_cum = 0.0
                rec.current_qty_period = 0.0
                rec.current_qty_week = 0.0
                rec.current_note = ""
                continue

            if rec.project_id and rec.project_id._is_project_completed():
                cur_no = rec._get_frozen_period_no()
            else:
                cur_no = rec._get_current_period_no(rec.date_start, today)

            rec.current_period_no = cur_no
            ps, pe = rec._get_period_bounds(rec.date_start, cur_no)
            rec.current_period_start = ps
            rec.current_period_end = pe

            prev_line = Progress.search(
                [("assignment_id", "=", rec.id), ("period_no", "<", cur_no)],
                order="period_no desc, id desc",
                limit=1,
            )
            prev_cum = prev_line.qty_cum if prev_line else 0.0

            cur_line = Progress.search(
                [("assignment_id", "=", rec.id), ("period_no", "=", cur_no)],
                order="id desc",
                limit=1,
            )
            cur_cum = cur_line.qty_cum if cur_line else prev_cum

            if cur_cum < prev_cum:
                cur_cum = prev_cum

            rec.prev_qty_cum = prev_cum
            rec.current_qty_cum = cur_cum
            rec.current_qty_period = max(0.0, cur_cum - prev_cum)
            rec.current_qty_week = rec.current_qty_period
            rec.current_note = (cur_line.note if cur_line else "") or ""

    def _inverse_current_period(self):
        Progress = self.env["project.work.progress"]
        today = fields.Date.context_today(self)

        for rec in self:
            if not rec.date_start:
                continue

            if rec.project_id and rec.project_id._is_project_completed():
                continue

            cur_no = rec._get_current_period_no(rec.date_start, today)

            prev_line = Progress.search(
                [("assignment_id", "=", rec.id), ("period_no", "<", cur_no)],
                order="period_no desc, id desc",
                limit=1,
            )
            prev_cum = prev_line.qty_cum if prev_line else 0.0

            week_qty = rec.current_qty_week or 0.0
            if week_qty < 0:
                week_qty = 0.0

            new_cum = prev_cum + week_qty

            line = Progress.search(
                [("assignment_id", "=", rec.id), ("period_no", "=", cur_no)],
                order="id desc",
                limit=1,
            )
            vals = {
                "assignment_id": rec.id,
                "period_no": cur_no,
                "qty_cum": new_cum,
                "note": rec.current_note or False,
            }
            if line:
                line.write(vals)
            else:
                Progress.create(vals)

    def _get_frozen_period_no(self):
        self.ensure_one()

        if self.project_id and self.project_id.report_closed_period_no:
            return self.project_id.report_closed_period_no

        Progress = self.env["project.work.progress"]
        last_line = Progress.search(
            [("assignment_id", "=", self.id)],
            order="period_no desc, id desc",
            limit=1,
        )
        if last_line:
            return last_line.period_no or 1

        if self.date_start:
            today = fields.Date.context_today(self)
            return self._get_current_period_no(self.date_start, today)

        return 1
    def action_repair_cumulative(self):
        Progress = self.env["project.work.progress"].sudo()
        for rec in self:
            lines = Progress.search([("assignment_id", "=", rec.id)], order="period_no asc")
            prev = 0.0
            for ln in lines:
                if (ln.qty_cum or 0.0) < prev:
                    ln.qty_cum = prev
                prev = ln.qty_cum or 0.0
        return True

    # ===== API cho OWL =====

    def get_assignment_report_rows(self):
        """Trả dữ liệu cho màn OWL trên 1 project."""
        self.ensure_one()

        assignments = self.env["project.work.assignment"].search([
            ("project_id", "=", self.id),
            ("user_id", "=", self.env.user.id),
            ("active", "=", True),
        ], order="section_name, id")

        rows = []
        for rec in assignments:
            max_total = rec.qty_settlement or rec.qty_plan or 0.0
            rows.append({
                "id": rec.id,
                "section_name": rec.section_name or "",
                "work_item_name": rec.work_item_name or "",
                "product_name": rec.product_id.display_name if rec.product_id else "",
                "uom_name": rec.uom_id.display_name if rec.uom_id else "",
                "qty_settlement": rec.qty_settlement or 0.0,
                "qty_plan": rec.qty_plan or 0.0,
                "prev_qty_cum": rec.prev_qty_cum or 0.0,
                "current_qty_week": rec.current_qty_week or 0.0,
                "current_note": rec.current_note or "",
                "current_qty_cum": rec.current_qty_cum or 0.0,
                "qty_remaining": rec.qty_remaining or 0.0,
                "current_period_no": rec.current_period_no or 0,
                "current_period_start": rec.current_period_start and rec.current_period_start.isoformat(),
                "current_period_end": rec.current_period_end and rec.current_period_end.isoformat(),
                "max_total": max_total,
            })

        return {
            "project": {
                "id": self.id,
                "name": self.name,
                "partner_name": self.partner_id.display_name if self.partner_id else "",
                "manager_name": self.user_id.display_name if self.user_id else "",
                "my_assignment_count": len(rows),
            },
            "rows": rows,
        }

    def save_assignment_report_rows(self, rows):
        """rows = [{'id': 1, 'current_qty_week': 10, 'current_note': '...'}]"""
        self.ensure_one()

        if not isinstance(rows, list):
            raise UserError(_("Dữ liệu lưu không hợp lệ."))

        assignments = self.env["project.work.assignment"].browse([
            row.get("id") for row in rows if row.get("id")
        ]).exists()

        for rec in assignments:
            if rec.project_id != self or rec.user_id != self.env.user:
                raise UserError(_("Bạn không có quyền cập nhật hạng mục này."))

        row_map = {row["id"]: row for row in rows if row.get("id")}

        for rec in assignments:
            vals = row_map.get(rec.id, {})
            week_qty = vals.get("current_qty_week", 0.0) or 0.0
            note = vals.get("current_note", "") or ""

            if week_qty < 0:
                week_qty = 0.0

            max_total = rec.qty_settlement or rec.qty_plan or 0.0
            max_allowed = max(0.0, max_total - (rec.prev_qty_cum or 0.0)) if max_total else week_qty
            if max_total:
                week_qty = min(week_qty, max_allowed)

            rec.write({
                "current_qty_week": week_qty,
                "current_note": note,
            })

        self.invalidate_recordset()
        return self.get_assignment_report_rows()