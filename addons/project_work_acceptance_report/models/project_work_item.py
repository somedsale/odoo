# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectWorkItem(models.Model):
    _inherit = "project.work.item"

    acceptance_user_id = fields.Many2one(
        "res.users",
        string="Người báo cáo nghiệm thu",
        tracking=True,
    )

    acceptance_line_ids = fields.One2many(
        "project.work.acceptance",
        "work_item_id",
        string="Lịch sử nghiệm thu",
    )

    qty_accepted = fields.Float(
        string="Khối lượng đã nghiệm thu",
        compute="_compute_acceptance_metrics",
        store=True,
        digits="Product Unit of Measure",
    )
    qty_acceptance_remaining = fields.Float(
        string="Khối lượng còn lại chưa nghiệm thu",
        compute="_compute_acceptance_metrics",
        store=True,
        digits="Product Unit of Measure",
    )
    acceptance_percent = fields.Float(
        string="% nghiệm thu",
        compute="_compute_acceptance_metrics",
        store=True,
    )

    value_accepted_tax = fields.Monetary(
        string="Giá trị đã nghiệm thu sau thuế",
        compute="_compute_acceptance_value_metrics",
        store=True,
        currency_field="currency_id",
    )
    value_acceptance_remaining_tax = fields.Monetary(
        string="Giá trị còn lại chưa nghiệm thu sau thuế",
        compute="_compute_acceptance_value_metrics",
        store=True,
        currency_field="currency_id",
    )

    @api.depends(
        "qty_done",
        "acceptance_line_ids.current_qty",
        "acceptance_line_ids.active",
    )
    def _compute_acceptance_metrics(self):
        for rec in self:
            completed_qty = rec.qty_done or 0.0

            accepted_qty = sum(
                rec.acceptance_line_ids.filtered(lambda x: x.active).mapped("current_qty") or [0.0]
            )
            accepted_qty = max(0.0, accepted_qty)

            # Không cho nghiệm thu vượt quá sản lượng đã thực hiện
            accepted_qty = min(accepted_qty, completed_qty)

            remaining_qty = max(0.0, completed_qty - accepted_qty)

            rec.qty_accepted = accepted_qty
            rec.qty_acceptance_remaining = remaining_qty
            rec.acceptance_percent = (accepted_qty / completed_qty * 100.0) if completed_qty else 0.0

    @api.depends(
        "qty_done",
        "price_unit_tax",
        "qty_accepted",
        "qty_acceptance_remaining",
    )
    def _compute_acceptance_value_metrics(self):
        for rec in self:
            price_tax = rec.price_unit_tax or 0.0

            rec.value_accepted_tax = (rec.qty_accepted or 0.0) * price_tax
            rec.value_acceptance_remaining_tax = (rec.qty_acceptance_remaining or 0.0) * price_tax