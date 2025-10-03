from odoo import api, fields, models

class CustomerDebtSummary(models.Model):
    _name = "customer.debt.summary"
    _description = "Tổng hợp công nợ KH"
    _auto = True

    partner_id = fields.Many2one('res.partner', string="Khách hàng", readonly=True)
    project_id = fields.Many2one('project.project', string="Dự án", readonly=True)
    contract_id = fields.Many2one('customer.contract', string="Hợp đồng", readonly=True)
    amount_total = fields.Monetary(string="Tổng HĐ", currency_field="currency_id", readonly=True)
    amount_invoiced = fields.Monetary(string="Đã xuất HĐ", currency_field="currency_id", readonly=True)
    amount_paid = fields.Monetary(string="Đã thanh toán", currency_field="currency_id", readonly=True)
    residual = fields.Monetary(string="Còn nợ", currency_field="currency_id", readonly=True)
    currency_id = fields.Many2one('res.currency', string="Tiền tệ", readonly=True)

    @api.model
    def load_data(self):
        self.search([]).unlink()
        groups = self.env['customer.invoice'].read_group(
            domain=[],
            fields=[
                'partner_id',
                'project_id',
                'contract_id',
                'currency_id',
                'amount_total:sum',
            ],
            groupby=['partner_id', 'project_id', 'contract_id', 'currency_id'],
            lazy=False,
        )
        records = []
        for g in groups:
            total = g.get('amount_total_sum') or 0.0
            paid = 0.0   # TODO: lấy từ payment nếu bạn có module payment
            residual = total - paid
            records.append({
                'partner_id': g['partner_id'][0] if g.get('partner_id') else False,
                'project_id': g['project_id'][0] if g.get('project_id') else False,
                'contract_id': g['contract_id'][0] if g.get('contract_id') else False,
                'currency_id': g['currency_id'][0] if g.get('currency_id') else False,
                'amount_total': total,
                'amount_invoiced': total,
                'amount_paid': paid,
                'residual': residual,
            })
        self.create(records)
    @api.model
    def default_get(self, fields_list):
        self.load_data()
        return super().default_get(fields_list)