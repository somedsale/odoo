from odoo import models, fields, api

class ProjectPaymentSchedule(models.Model):
    _name = 'project.payment.schedule'
    _description = 'Tiến độ thanh toán dự án'
    _order = 'date_due asc'

    project_id = fields.Many2one('project.project', string="Dự án", required=True, ondelete='cascade')
    date_due = fields.Date('Ngày đến hạn', required=True)
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
    @api.onchange('schedule_id')
    def _onchange_schedule_id(self):
        if self.schedule_id and self.schedule_id.project_id:
            self.partner_id = self.schedule_id.project_id.partner_id
   
    @api.depends('amount')
    def _compute_balance_amount(self):
        for rec in self:
            rec.balance_amount = rec.amount

    @api.depends('receipt_ids.state', 'receipt_ids.amount')
    def _compute_actual_amount(self):
        for rec in self:
            # Chỉ cộng các phiếu thu đã được "ghi sổ"
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