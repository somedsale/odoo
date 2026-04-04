# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CustomerInvoice(models.Model):
    _inherit = "customer.invoice"

    receipt_amount_total = fields.Monetary(
        string="Đã thu",
        currency_field="currency_id",
        compute="_compute_receipt_summary",
        store=True,
    )
    receivable_remaining = fields.Monetary(
        string="Còn phải thu",
        currency_field="currency_id",
        compute="_compute_receipt_summary",
        store=True,
    )
    receipt_percent = fields.Float(
        string="Tỷ lệ thu (%)",
        compute="_compute_receipt_summary",
        store=True,
    )

    @api.depends(
        "amount_total",
        "account_receipt_ids",
        "account_receipt_ids.amount",
        "account_receipt_ids.state",
    )
    def _compute_receipt_summary(self):
        """
        Giả định account.receipt có field amount và state.
        Nếu model account.receipt của bạn dùng tên field khác (vd amount_total / payment_amount),
        sửa lại ở đây.
        """
        for rec in self:
            total_receipt = 0.0

            for r in rec.account_receipt_ids:
                # chỉ cộng phiếu thu hợp lệ (tùy nghiệp vụ)
                if "state" in r._fields:
                    if r.state in ("cancel", "draft"):
                        continue
                amt = 0.0
                if "amount" in r._fields:
                    amt = r.amount or 0.0
                elif "amount_total" in r._fields:
                    amt = r.amount_total or 0.0
                total_receipt += amt

            rec.receipt_amount_total = total_receipt
            rec.receivable_remaining = (rec.amount_total or 0.0) - total_receipt
            rec.receipt_percent = ((total_receipt / rec.amount_total) * 100.0) if rec.amount_total else 0.0