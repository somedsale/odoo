from odoo import models, fields, api

class ProjectExpenseCustom(models.Model):
    _name = 'project.expense.custom'
    _description = 'Chi phí dự án'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "create_date desc"
    name = fields.Char(string="Tên dự án", related="project_id.name", store=True, readonly=True)
    project_id = fields.Many2one('project.project', string="Dự án", required=True, index=True)
    currency_id = fields.Many2one('res.currency', string="Tiền tệ", default=lambda self: self.env.company.currency_id)
    payment_request_ids = fields.One2many('account.payment.request', 'project_expense_id', string="Yêu cầu chi tiền")
    total_spent = fields.Float(string="Tổng đã chi", compute='_compute_costs')
    total_not_spent = fields.Float(string="Tổng chưa chi", compute='_compute_costs')
    total_cost = fields.Float(string="Tổng chi phí", compute='_compute_costs')

    @api.depends('payment_request_ids.total', 'payment_request_ids.status_expense')
    def _compute_costs(self):
        for record in self:
            spent = sum(pr.total for pr in record.payment_request_ids if pr.status_expense == 'paid')
            not_spent = sum(pr.total for pr in record.payment_request_ids if pr.status_expense == 'not yet')
            record.total_spent = spent
            record.total_not_spent = not_spent
            record.total_cost = spent + not_spent

    @api.model
    def create_or_update_expense(self, project_id):
        expense = self.search([('project_id', '=', project_id)], limit=1)
        if not expense:
            self.create({'project_id': project_id})

    @api.model
    def _load_all_projects(self):
        for project in self.env['project.project'].search([]):
            self.create_or_update_expense(project.id)
    def action_view_payment_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Yêu cầu chi tiền',
            'res_model': 'account.payment.request',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.project_id.id)],
            'context': {'default_project_id': self.project_id.id},
        }
