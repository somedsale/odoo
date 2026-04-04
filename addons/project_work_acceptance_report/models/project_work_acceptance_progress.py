# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProjectWorkAcceptanceProgress(models.Model):
    _name = "project.work.acceptance.progress"
    _description = "Acceptance Progress Per Period"
    _order = "assignment_id, period_no"

    assignment_id = fields.Many2one(
        "project.work.assignment",
        string="Phân công",
        required=True,
        ondelete="cascade",
        index=True,
    )

    project_id = fields.Many2one(
        "project.project",
        related="assignment_id.project_id",
        store=True,
        readonly=True,
    )
    work_item_id = fields.Many2one(
        "project.work.item",
        related="assignment_id.work_item_id",
        store=True,
        readonly=True,
    )
    user_id = fields.Many2one(
        "res.users",
        related="assignment_id.acceptance_user_id",
        string="Người báo cáo nghiệm thu",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="project_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        related="work_item_id.uom_id",
        store=True,
        readonly=True,
    )

    period_no = fields.Integer(string="Kỳ", required=True, index=True)
    period_start = fields.Date(string="Từ ngày", compute="_compute_period", store=True)
    period_end = fields.Date(string="Đến ngày", compute="_compute_period", store=True)

    qty_cum = fields.Float(
        string="Lũy kế nghiệm thu",
        digits="Product Unit of Measure",
        default=0.0,
    )
    qty_period = fields.Float(
        string="Khối lượng nghiệm thu kỳ này",
        compute="_compute_qty_period",
        store=True,
        digits="Product Unit of Measure",
    )

    price_unit = fields.Float(string="Đơn giá", compute="_compute_price_unit", store=False)
    value_period = fields.Monetary(string="Giá trị kỳ này", compute="_compute_values", store=True)
    value_cum = fields.Monetary(string="Lũy kế giá trị nghiệm thu", compute="_compute_values", store=True)

    note = fields.Text(string="Ghi chú")

    _sql_constraints = [
        (
            "uniq_assignment_period_acceptance",
            "unique(assignment_id, period_no)",
            "Mỗi kỳ chỉ có 1 dòng nghiệm thu cho 1 phân công.",
        ),
    ]

    def _get_period_bounds(self, assignment, period_no):
        if hasattr(assignment, "_acceptance_get_period_bounds"):
            return assignment._acceptance_get_period_bounds(assignment.date_start, period_no)

        # fallback
        start = fields.Date.to_date(assignment.date_start)
        if period_no == 1:
            weekday = start.weekday()
            delta = max(0, 5 - weekday)
            return start, start + timedelta(days=delta)
        base_mon = start - timedelta(days=start.weekday())
        ps = base_mon + timedelta(weeks=period_no - 1)
        return ps, ps + timedelta(days=5)

    @api.depends("assignment_id.date_start", "period_no")
    def _compute_period(self):
        for rec in self:
            if not rec.assignment_id or not rec.assignment_id.date_start or not rec.period_no:
                rec.period_start = False
                rec.period_end = False
                continue
            ps, pe = rec._get_period_bounds(rec.assignment_id, rec.period_no)
            rec.period_start = ps
            rec.period_end = pe

    @api.depends("work_item_id")
    def _compute_price_unit(self):
        for rec in self:
            pu = 0.0
            wi = rec.work_item_id
            if wi:
                if "price_unit" in wi._fields:
                    pu = wi.price_unit or 0.0
                elif "price_subtotal" in wi._fields and (wi.qty_plan or 0.0):
                    pu = (wi.price_subtotal or 0.0) / wi.qty_plan if wi.qty_plan else 0.0
            rec.price_unit = pu

    def _prev_cum_for(self, assignment_id, period_no):
        prev = self.search(
            [("assignment_id", "=", assignment_id), ("period_no", "<", period_no)],
            order="period_no desc, id desc",
            limit=1,
        )
        return prev.qty_cum if prev else 0.0

    @api.depends("qty_cum", "period_no", "assignment_id", "assignment_id.acceptance_progress_ids.qty_cum")
    def _compute_qty_period(self):
        for rec in self:
            prev_cum = rec._prev_cum_for(rec.assignment_id.id, rec.period_no) if rec.assignment_id and rec.period_no else 0.0
            rec.qty_period = max(0.0, (rec.qty_cum or 0.0) - (prev_cum or 0.0))

    @api.depends("qty_period", "qty_cum", "work_item_id")
    def _compute_values(self):
        for rec in self:
            pu = rec.price_unit or 0.0
            rec.value_period = (rec.qty_period or 0.0) * pu
            rec.value_cum = (rec.qty_cum or 0.0) * pu

    def _reported_cum_for(self, assignment, period_no):
        Progress = self.env["project.work.progress"]
        p = Progress.search(
            [("assignment_id", "=", assignment.id), ("period_no", "<=", period_no)],
            order="period_no desc, id desc",
            limit=1,
        )
        return p.qty_cum if p else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        safe_list = []
        for vals in vals_list:
            assignment_id = vals.get("assignment_id")
            period_no = vals.get("period_no")
            qty_cum = vals.get("qty_cum", 0.0) or 0.0
            if assignment_id and period_no:
                prev_cum = self._prev_cum_for(assignment_id, period_no)
                if qty_cum < prev_cum:
                    qty_cum = prev_cum
                vals["qty_cum"] = qty_cum
            safe_list.append(vals)
        recs = super().create(safe_list)
        recs._check_not_exceed_reported()
        return recs

    def write(self, vals):
        for rec in self:
            safe_vals = dict(vals)
            new_qty = safe_vals.get("qty_cum", rec.qty_cum or 0.0) or 0.0
            prev_cum = rec._prev_cum_for(rec.assignment_id.id, rec.period_no)
            if new_qty < prev_cum:
                new_qty = prev_cum
                safe_vals["qty_cum"] = new_qty
            super(ProjectWorkAcceptanceProgress, rec).write(safe_vals)
        self._check_not_exceed_reported()
        return True

    @api.constrains("qty_cum")
    def _check_monotonic(self):
        for rec in self:
            prev_cum = rec._prev_cum_for(rec.assignment_id.id, rec.period_no)
            if (rec.qty_cum or 0.0) < prev_cum:
                raise ValidationError(
                    f"Lũy kế nghiệm thu kỳ {rec.period_no} phải >= lũy kế kỳ {rec.period_no - 1}."
                )

    @api.constrains("qty_cum", "period_no")
    def _check_not_exceed_reported(self):
        for rec in self:
            if not rec.assignment_id or not rec.period_no:
                continue
            reported_cum = rec._reported_cum_for(rec.assignment_id, rec.period_no)
            if (rec.qty_cum or 0.0) > (reported_cum or 0.0):
                raise ValidationError(
                    f"Không thể nhập lũy kế nghiệm thu ({rec.qty_cum}) vượt lũy kế sản lượng báo cáo ({reported_cum}) "
                    f"ở kỳ {rec.period_no}."
                )