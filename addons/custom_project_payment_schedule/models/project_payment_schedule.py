from odoo import models, fields, api

class ProjectPaymentSchedule(models.Model):
    _name = 'project.payment.schedule'
    _description = 'Tiến độ thanh toán dự án'
    _order = 'project_id, sequence asc'

    project_id = fields.Many2one('project.project', string="Dự án", required=True, ondelete='cascade')
    sequence = fields.Integer('Đợt', readonly=True)
    milestone_id = fields.Many2one('project.payment.milestone', string="Mốc thanh toán", required=True)
    date_planned = fields.Date('Ngày dự kiến thu')
    amount = fields.Float('Số tiền dự kiến', required=True)
    description = fields.Char('Ghi chú')
    partner_id = fields.Many2one(related='project_id.partner_id', string="Khách hàng", store=True, readonly=True)
    state = fields.Selection([
        ('pending', 'Chưa thu'),
        ('partial', 'Đã thu một phần'),
        ('done', 'Đã thu đủ'),
    ], string='Trạng thái', compute='_compute_state', store=True)

    actual_amount = fields.Float('Đã thu', compute='_compute_actual_amount', store=True)
    balance_amount = fields.Float('Còn lại', compute='_compute_actual_amount', store=True)
    currency_id = fields.Many2one('res.currency', string='Tiền tệ', default=lambda self: self.env.company.currency_id)

    receipt_ids = fields.One2many('account.receipt', 'schedule_id', string='Phiếu thu liên quan')
    name = fields.Char('Tên đợt', compute='_compute_name', store=True)

    @api.model
    def create(self, vals):
        if vals.get('project_id') and not vals.get('sequence'):
            existing_count = self.search_count([('project_id', '=', vals['project_id'])])
            vals['sequence'] = existing_count + 1
        return super().create(vals)

    @api.depends('sequence', 'milestone_id.name')
    def _compute_name(self):
        for rec in self:
            if rec.milestone_id and rec.milestone_id.name:
                rec.name = f"Đợt {rec.sequence} - {rec.milestone_id.name}"
            else:
                rec.name = f"Đợt {rec.sequence}"

    @api.depends('receipt_ids.state', 'receipt_ids.amount')
    def _compute_actual_amount(self):
        for rec in self:
            receipts = rec.receipt_ids.filtered(lambda r: r.state == 'posted')
            rec.actual_amount = sum(r.amount for r in receipts)
            rec.balance_amount = rec.amount - rec.actual_amount

    @api.depends('actual_amount', 'amount')
    def _compute_state(self):
        for rec in self:
            if rec.actual_amount == 0:
                rec.state = 'pending'
            elif rec.actual_amount < rec.amount:
                rec.state = 'partial'
            else:
                rec.state = 'done'
