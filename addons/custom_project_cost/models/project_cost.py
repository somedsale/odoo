from odoo import models, fields, api

class ProjectCost(models.Model):
    _name = 'custom.project.cost'
    _description = 'Tổng hợp chi phí dự án'

    cost_not_spent = fields.Float(string='Chưa chi', compute='_compute_project_costs', store=False)
    cost_spent = fields.Float(string='Đã chi', compute='_compute_project_costs', store=False)
    cost_total = fields.Float(string='Tổng chi phí', compute='_compute_project_costs', store=False)
    project_id = fields.Many2one('project.project', string='Dự án', required=True)
    currency_id = fields.Many2one('res.currency', string='Tiền tệ', default=lambda self: self.env.company.currency_id)

    account_payment_request_ids = fields.One2many(
        'account.payment.request',
        'project_id',
        string='Yêu cầu chi tiền'
    )

    @api.depends('account_payment_request_ids.total', 'account_payment_request_ids.status_expense')
    def _compute_project_costs(self):
        for project in self:
            payment_requests = project.account_payment_request_ids
            project.cost_spent = sum(pr.total for pr in payment_requests if pr.status_expense == 'paid')
            project.cost_not_spent = sum(pr.total for pr in payment_requests if pr.status_expense != 'paid')
            project.cost_total = project.cost_spent + project.cost_not_spent
