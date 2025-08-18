from odoo import models, fields, api

class ProjectExpenseDashboard(models.Model):
    _name = 'project.expense.dashboard'
    _description = 'Dashboard quản lý chi phí dự án'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    name = fields.Char(string="Tên dashboard", compute="_compute_name", store=True)

    project_id = fields.Many2one(
        'project.project',
        string='Dự án',
        required=True,
        ondelete='cascade',
    )
    cost_estimate_id = fields.Many2one('cost.estimate', string="Dự toán", required=False)
    cost_estimate_line_ids = fields.One2many(
        related='cost_estimate_id.line_ids',
        string="Dòng dự toán",
        readonly=True,
    )
    total_estimate = fields.Float(string="Tổng dự toán", compute="_compute_total_estimate", store=True)
    total_actual = fields.Float(string="Tổng chi thực tế", compute="_compute_total_actual", store=True)
    progress = fields.Float( compute="_compute_progress", store=True)
    currency_id = fields.Many2one('res.currency', string="Tiền tệ", default=lambda self: self.env.company.currency_id, readonly=True)
    payment_request_count = fields.Integer(
    compute="_compute_payment_request_count",
)
    payment_request_pending_count = fields.Integer(
    compute="_compute_payment_request_count",
)
    total_actual_with_item = fields.Float(
    string="Tổng chi có hạng mục",
    compute="_compute_total_actual_split",
    store=True
)
    total_actual_without_item = fields.Float(
        string="Tổng chi không hạng mục",
        compute="_compute_total_actual_split",   
        store=True
    )

    @api.depends(
        'project_id',
        'project_id.account_payment_request_ids.total',
        'project_id.account_payment_request_ids.status_expense',
        'project_id.account_payment_request_ids.cost_estimate_line_id',
    )
    def _compute_total_actual_split(self):
        for record in self:
            if record.project_id:
                payments_with_item = record.project_id.account_payment_request_ids.filtered(
                    lambda p: p.status_expense == 'paid' and p.cost_estimate_line_id
                )
                payments_without_item = record.project_id.account_payment_request_ids.filtered(
                    lambda p: p.status_expense == 'paid' and not p.cost_estimate_line_id
                )
                record.total_actual_with_item = sum(payments_with_item.mapped('total'))
                record.total_actual_without_item = sum(payments_without_item.mapped('total'))
            else:
                record.total_actual_with_item = 0.0
                record.total_actual_without_item = 0.0
    @api.depends('project_id.name')
    def _compute_name(self):
        for rec in self:
            if rec.project_id:
                rec.name = rec.project_id.display_name
            else:
                rec.name = ""

    @api.depends('project_id')
    def _compute_payment_request_count(self):
        for record in self:
            if record.project_id:
                record.payment_request_count = self.env['account.payment.request'].search_count([
                    ('project_id', '=', record.project_id.id),
                    ('status_expense', '=', 'paid')
                ])
                record.payment_request_pending_count = self.env['account.payment.request'].search_count([
                    ('project_id', '=', record.project_id.id),
                    ('status_expense', '=', 'not yet')
                ])
            else:
                record.payment_request_count = 0
                record.payment_request_pending_count = 0


    @api.depends('cost_estimate_id','cost_estimate_id.total_cost')
    def _compute_total_estimate(self):
        for record in self:
            record.total_estimate = record.cost_estimate_id.total_cost if record.cost_estimate_id and hasattr(record.cost_estimate_id, 'total_cost') else 0.0

    @api.depends('project_id')
    def _compute_total_actual(self):
        ProjectRequest = self.env['account.payment.request']
        for record in self:
            if record.project_id:
                payments = ProjectRequest.search([
                    ('project_id', '=', record.project_id.id),
                    ('state', '=', 'done')
                ])
                record.total_actual = sum(p.total for p in payments)
            else:
                record.total_actual = 0.0         
    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            estimate = self.env['cost.estimate'].search([('project_id', '=', self.project_id.id)])
            if estimate:
                self.cost_estimate_id = estimate.id
            else:
                self.cost_estimate_id = False
        else:
            self.cost_estimate_id = False

    @api.depends('total_estimate', 'total_actual')
    def _compute_progress(self):
        for record in self:
            if record.total_estimate > 0:
                record.progress = (record.total_actual / record.total_estimate) * 100
            else:
                record.progress = 0.0
    def action_view_payment_requests(self):
            self.ensure_one()
            return self.env.ref('custom_account_payment_request.action_account_payment_request_without_searchpanel').read()[0] | {
                'domain': [
                    ('project_id', '=', self.project_id.id),
                    ('status_expense', '=', 'paid')
                ],
                'context': {'default_project_id': self.project_id.id},
                'target': 'current',
            }
    def action_view_payment_pending_requests(self):
            self.ensure_one()
            return self.env.ref('custom_account_payment_request.action_account_payment_request_without_searchpanel').read()[0] | {
                'domain': [
                    ('project_id', '=', self.project_id.id),
                    ('status_expense', '=', 'not yet')
                ],
                'context': {'default_project_id': self.project_id.id},
                'target': 'current',
            }