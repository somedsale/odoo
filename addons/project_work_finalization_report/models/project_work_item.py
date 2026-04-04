# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectWorkItem(models.Model):
    _inherit = "project.work.item"

    finalization_user_id = fields.Many2one(
        "res.users",
        string="Người báo cáo thanh/quyết toán",
        tracking=True,
    )

    finalization_line_ids = fields.One2many(
        "project.work.finalization",
        "work_item_id",
        string="Lịch sử thanh/quyết toán",
    )

    qty_finalized = fields.Float(
        string="Khối lượng đã thanh/quyết toán",
        compute="_compute_finalization_metrics",
        store=True,
        digits="Product Unit of Measure",
    )
    qty_finalization_remaining = fields.Float(
        string="Khối lượng còn lại chưa thanh/quyết toán",
        compute="_compute_finalization_metrics",
        store=True,
        digits="Product Unit of Measure",
    )
    finalization_percent = fields.Float(
        string="% thanh/quyết toán",
        compute="_compute_finalization_metrics",
        store=True,
    )

    value_finalized_tax = fields.Monetary(
        string="Giá trị đã thanh/quyết toán sau thuế",
        compute="_compute_finalization_value_metrics",
        store=True,
        currency_field="currency_id",
    )
    value_finalization_remaining_tax = fields.Monetary(
        string="Giá trị còn lại chưa thanh/quyết toán sau thuế",
        compute="_compute_finalization_value_metrics",
        store=True,
        currency_field="currency_id",
    )

    @api.depends(
        "qty_accepted",
        "finalization_line_ids.current_qty",
        "finalization_line_ids.active",
    )
    def _compute_finalization_metrics(self):
        for rec in self:
            accepted_qty = rec.qty_accepted or 0.0

            finalized_qty = sum(
                rec.finalization_line_ids.filtered(lambda x: x.active).mapped("current_qty") or [0.0]
            )
            finalized_qty = max(0.0, finalized_qty)

            # Không cho thanh/quyết toán vượt quá khối lượng đã nghiệm thu
            finalized_qty = min(finalized_qty, accepted_qty)

            remaining_qty = max(0.0, accepted_qty - finalized_qty)

            rec.qty_finalized = finalized_qty
            rec.qty_finalization_remaining = remaining_qty
            rec.finalization_percent = (finalized_qty / accepted_qty * 100.0) if accepted_qty else 0.0

    @api.depends(
        "qty_accepted",
        "price_unit_tax",
        "qty_finalized",
        "qty_finalization_remaining",
    )
    def _compute_finalization_value_metrics(self):
        for rec in self:
            price_tax = rec.price_unit_tax or 0.0

            rec.value_finalized_tax = (rec.qty_finalized or 0.0) * price_tax
            rec.value_finalization_remaining_tax = (rec.qty_finalization_remaining or 0.0) * price_tax