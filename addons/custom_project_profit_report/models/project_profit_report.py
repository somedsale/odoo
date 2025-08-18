from odoo import models, fields, api
class ProjectProfitReport(models.Model):
    _name = 'project.profit.report'
    _description = 'Báo cáo lời lỗ công trình'
    _auto = False  # không tạo table, dùng cho report tính toán

    project_id = fields.Many2one('project.project', string='Dự án')
    num_contract = fields.Integer(string='Số HD')
    material_cost = fields.Monetary(string='Chi phí vật tư', currency_field='currency_id')
    machine_cost = fields.Monetary(string='Chi phí máy', currency_field='currency_id')
    other_cost = fields.Monetary(string='Chi phí khác', currency_field='currency_id')
    labor_cost = fields.Monetary(string='Chi phí nhân công', currency_field='currency_id')
    revenue = fields.Monetary(string='Doanh thu', currency_field='currency_id' )
    expense = fields.Monetary(string='Chi phí', currency_field='currency_id' )
    profit = fields.Monetary(string='Lợi nhuận', currency_field='currency_id' )
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    @api.model
    def _compute_records(self):
        # Lấy tất cả project để tính toán
        projects = self.env['project.project'].search([('id', '!=', 4)])
        records = []
        for p in projects:
            revenue = 0.0
            expense = 0.0
            contract = self.env['contract.management'].search([('project_id','=',p.id)], limit=1)
            if contract and contract.sale_order_id:
                revenue = contract.sale_order_id.amount_total
            payments = self.env['account.payment.request'].search([
                ('proposal_sheet_id.project_id','=',p.id),
                ('proposal_sheet_id.type','in',['expense','material'])
            ])
            num_contract = contract.num_contract if contract else ''
            expense = sum(payments.mapped('total'))
            material_cost = sum(payments.filtered(lambda x: x.proposal_sheet_id.type == 'material').mapped('total'))
            all_expense_lines = payments.mapped('proposal_sheet_id.expense_line_ids')
            labor_cost = sum(all_expense_lines.filtered(lambda l: l.expense_id.type == 'labor').mapped('price_total'))
            machine_cost = sum(all_expense_lines.filtered(lambda l: l.expense_id.type == 'equipment').mapped('price_total'))
            other_cost = sum(all_expense_lines.filtered(lambda l: l.expense_id.type == 'other').mapped('price_total'))

            profit = revenue - expense
            records.append({
                'project_id': p,
                'revenue': revenue,
                'num_contract': num_contract,
                'material_cost': material_cost,
                'labor_cost': labor_cost,
                'machine_cost': machine_cost,
                'other_cost': other_cost,
                'expense': expense,
                'profit': profit,
            })
        return records
