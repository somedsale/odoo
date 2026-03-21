# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import api, fields, models


class ProjectWorkFinalization(models.Model):
    _name = "project.work.finalization"
    _description = "Project Work Finalization"
    _order = "assignment_id, period_no, id"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    active = fields.Boolean(default=True)

    project_id = fields.Many2one(
        "project.project",
        string="Dự án",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="project_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related="project_id.company_id.currency_id",
        store=True,
        readonly=True,
    )

    work_item_id = fields.Many2one(
        "project.work.item",
        string="Hạng mục",
        required=True,
        ondelete="cascade",
        index=True,
    )
    assignment_id = fields.Many2one(
        "project.work.assignment",
        string="Phân công",
        required=True,
        ondelete="cascade",
        index=True,
    )
    user_id = fields.Many2one(
        related="assignment_id.user_id",
        store=True,
        readonly=True,
        string="Người được phân công",
    )

    period_no = fields.Integer(string="Kỳ thanh/quyết toán", required=True, default=1, index=True)
    date_start = fields.Date(string="Ngày bắt đầu mốc")
    period_start = fields.Date(string="Từ ngày", compute="_compute_period_bounds", store=True)
    period_end = fields.Date(string="Đến ngày", compute="_compute_period_bounds", store=True)

    qty_prev_cum = fields.Float(
        string="QT đến hết kỳ trước",
        compute="_compute_qty_metrics",
        store=True,
        digits="Product Unit of Measure",
    )
    current_qty = fields.Float(
        string="QT kỳ này",
        digits="Product Unit of Measure",
        default=0.0,
        tracking=True,
    )
    qty_cum = fields.Float(
        string="QT đến hết kỳ này",
        compute="_compute_qty_metrics",
        store=True,
        digits="Product Unit of Measure",
    )
    note = fields.Text(string="Ghi chú")

    @api.depends("date_start", "period_no", "assignment_id.date_start", "project_id.date_start")
    def _compute_period_bounds(self):
        for rec in self:
            start = rec.date_start or rec.assignment_id.date_start or rec.project_id.date_start
            if start and rec.period_no:
                period_start = start + timedelta(days=(rec.period_no - 1) * 7)
                period_end = period_start + timedelta(days=6)
            else:
                period_start = False
                period_end = False
            rec.period_start = period_start
            rec.period_end = period_end

    @api.depends(
        "current_qty",
        "period_no",
        "assignment_id",
        "assignment_id.finalization_line_ids.current_qty",
        "assignment_id.finalization_line_ids.period_no",
        "assignment_id.finalization_line_ids.active",
    )
    def _compute_qty_metrics(self):
        for rec in self:
            lines = rec.assignment_id.finalization_line_ids.filtered(
                lambda l: l.active
            ).sorted(key=lambda l: (l.period_no, l.id))

            prev_cum = sum(
                l.current_qty for l in lines
                if l.period_no < rec.period_no and l.id != rec.id
            )

            rec.qty_prev_cum = prev_cum
            rec.qty_cum = prev_cum + (rec.current_qty or 0.0)

    _sql_constraints = [
        (
            "uniq_finalization_assignment_period",
            "unique(assignment_id, period_no)",
            "Mỗi phân công chỉ có một dòng thanh/quyết toán cho mỗi kỳ.",
        ),
    ]