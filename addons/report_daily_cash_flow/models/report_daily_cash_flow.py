# -*- coding: utf-8 -*-
from odoo import models, api


class DailyCashFlowReport(models.AbstractModel):
    _name = "report.report_daily_cash_flow.daily_cash_flow_report_template"
    _description = "Cash Flow Report PDF"

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}

        payments = self.env["account.payment.request"].browse(
            data.get("account_payment_ids", [])
        )

        receipts = self.env["account.receipt"].browse(
            data.get("account_receipt_ids", [])
        )

        currency = self.env["res.currency"].browse(data.get("currency_id"))

        payments = payments.sorted(
            key=lambda p: (
                p.payment_type != "bank",
                p.date_payment,
                p.id,
            )
        )

        receipts = receipts.sorted(
            key=lambda r: (
                r.payment_method != "bank",
                r.date,
                r.id,
            )
        )

        return {
            "doc_ids": docids,
            "doc_model": "daily.cash.flow.wizard",

            "period_label": data.get("period_label"),
            "date_from": data.get("date_from"),
            "date_to": data.get("date_to"),

            "payments": payments,
            "receipts": receipts,

            "opening_bank": data.get("opening_bank", 0.0),
            "opening_cash": data.get("opening_cash", 0.0),

            "sum_receipt_bank": data.get("sum_receipt_bank", 0.0),
            "sum_receipt_cash": data.get("sum_receipt_cash", 0.0),
            "sum_payment_bank": data.get("sum_payment_bank", 0.0),
            "sum_payment_cash": data.get("sum_payment_cash", 0.0),

            "closing_bank": data.get("closing_bank", 0.0),
            "closing_cash": data.get("closing_cash", 0.0),

            "currency_id": currency,
            "user_id": self.env.user,
            "res_company": self.env.company,
            "env": self.env,
        }