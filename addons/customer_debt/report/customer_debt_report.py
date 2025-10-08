from odoo import models, api

class ReportCustomerDebtSummary(models.AbstractModel):
    _name = 'report.customer_debt.customer_debt_summary_report'
    _description = 'Report: Tổng hợp công nợ khách hàng'

    @api.model
    def _get_report_values(self, docids, data=None):
        DebtSummary = self.env['customer.debt.summary']
        docs = DebtSummary.search([])

        grouped = []
        for rec in docs:
            # Các hợp đồng của khách hàng
            contracts = rec.contract_ids.sorted(lambda c: (c.project_id.name or '', c.name))
            enriched_contracts = []
            for c in contracts:
                # Tính tổng giá trị quyết toán
                settlement_total = sum(c.settlement_ids.mapped('amount_settlement'))
                enriched_contracts.append({
                    'id': c.id,
                    'project': c.project_id,
                    'name': c.name,
                    'amount_total': c.amount_total,
                    'amount_final': settlement_total,
                    'amount_invoiced': c.amount_invoiced,
                    'amount_paid': c.amount_receipt,
                    'amount_due': c.amount_due,
                    'warranty_amount': c.warranty_amount,
                    'warranty_period': f"{c.warranty_time or 0} tháng",
                    'note': '',
                })

            grouped.append({
                'partner': rec.partner_id,
                'summary': rec,
                'contracts': enriched_contracts,
            })

        return {
            'doc_ids': docs.ids,
            'doc_model': 'customer.debt.summary',
            'docs': grouped,
            'user_id': self.env.user,
            'res_company': self.env.company,
        }
