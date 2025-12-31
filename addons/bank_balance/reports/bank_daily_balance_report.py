# -*- coding: utf-8 -*-
from odoo import models, api


class ReportBankDailyBalance(models.AbstractModel):
    _name = "report.bank_balance.bank_daily_balance_report_template"
    _description = "Bank Daily Balance Report (HTML)"

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        company = self.env["res.company"].browse(data.get("company_id")) if data.get("company_id") else self.env.company
        currency = self.env["res.currency"].browse(data.get("currency_id")) if data.get("currency_id") else company.currency_id

        lines = data.get("lines", []) or []
        total_open = sum(l.get("opening_balance", 0.0) for l in lines)
        total_r = sum(l.get("receipt_amount", 0.0) for l in lines)
        total_p = sum(l.get("payment_amount", 0.0) for l in lines)
        total_close = sum(l.get("closing_balance", 0.0) for l in lines)

        return {
            "doc_ids": docids,
            "doc_model": "bank.balance.wizard",
            "res_company": company,
            "date_label": data.get("date", ""),
            "currency_id": currency,
            "lines": lines,
            "total_open": total_open,
            "total_r": total_r,
            "total_p": total_p,
            "total_close": total_close,
        }
