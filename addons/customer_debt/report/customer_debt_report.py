from odoo import models, api
from collections import defaultdict
import datetime

class ReportCustomerDebtSummary(models.AbstractModel):
    _name = 'report.customer_debt.customer_debt_summary_report'
    _description = 'Report: Tổng hợp công nợ khách hàng'

    @api.model
    def _get_report_values(self, docids, data=None):
        DebtSummary = self.env['customer.debt.summary']
        docs = DebtSummary.search([])

        grouped = defaultdict(lambda: defaultdict(list))

        for rec in docs:
            for c in rec.contract_ids:
                contract_type = c.contract_type or 'preparing'
                grouped[contract_type][rec.partner_id].append({
                    'id': c.id,
                    'project': c.project_id,
                    'name': c.name,
                    'amount_total': c.amount_total or 0.0,
                    'amount_final': sum(c.settlement_ids.mapped('amount_settlement')) or 0.0,
                    'amount_invoiced': c.amount_invoiced or 0.0,
                    'amount_paid': c.amount_receipt or 0.0,
                    'amount_due': rec.residual or 0.0,
                    'warranty_amount': c.warranty_amount or 0.0,
                    'warranty_period': f"{c.warranty_time or 0} tháng",
                    'contact': c.contact or '',   # 👈 thêm dòng này
                    'note': '',
                })

        totals = {}
        for ctype, partners in grouped.items():
            type_totals = {
                'amount_total': 0.0,
                'amount_final': 0.0,
                'amount_invoiced': 0.0,
                'amount_paid': 0.0,
                'amount_due': 0.0,
                'warranty_amount': 0.0,
            }
            for partner, contracts in partners.items():
                partner_totals = {k: sum(ct[k] for ct in contracts) for k in type_totals.keys()}
                partners[partner] = {'contracts': contracts, 'totals': partner_totals}
                for k in type_totals.keys():
                    type_totals[k] += partner_totals[k]
            totals[ctype] = type_totals

        return {
            'doc_ids': docs.ids,
            'doc_model': 'customer.debt.summary',
            'grouped': grouped,
            'totals': totals,
            'user_id': self.env.user,
            'res_company': self.env.company,
            'datetime': datetime,
            # ⚙️ thêm formatLang vào context
            'formatLang': self.env['ir.qweb.field.monetary'].value_to_html,
        }
