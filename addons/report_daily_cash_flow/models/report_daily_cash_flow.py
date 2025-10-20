# report/daily_cash_flow_report.py
from odoo import models, api

class DailyCashFlowReport(models.AbstractModel):
    _name = 'report.report_daily_cash_flow.daily_cash_flow_report_template'
    _description = 'Daily Cash Flow Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        payments = self.env['account.payment.request'].browse(data.get('account_payment_ids', []))
        receipts = self.env['account.receipt'].browse(data.get('account_receipt_ids', []))
        currency = self.env['res.currency'].browse(data.get('currency_id'))
        payments = payments.sorted(
            key=lambda p: (p.payment_type != 'cash', p.date_payment, p.id)
        )
        receipts = receipts.sorted(
            key=lambda r: (r.payment_method != 'cash', r.date, r.id)
        )

        return {
            'doc_ids': docids,
            'doc_model': 'daily.cash.flow.wizard',
            'date_report': data.get('date_report'),
            'payments': payments,
            'receipts': receipts,
            'opening_bank': data.get('opening_bank', 0.0),
            'opening_cash': data.get('opening_cash', 0.0),
            'sum_receipt_bank': data.get('sum_receipt_bank', 0.0),
            'sum_receipt_cash': data.get('sum_receipt_cash', 0.0),
            'sum_payment_bank': data.get('sum_payment_bank', 0.0),
            'sum_payment_cash': data.get('sum_payment_cash', 0.0),
            'closing_bank': data.get('closing_bank', 0.0),
            'closing_cash': data.get('closing_cash', 0.0),
            'currency_id': currency,
        }
