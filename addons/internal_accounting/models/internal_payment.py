from odoo import models, fields, api

class InternalPayment(models.Model):
    _name = 'internal.payment'
    _description = 'Phiếu Thu/Chi Nội Bộ'
    _order = 'id desc'
    name = fields.Char(string='Mã phiếu', required=True, copy=False, readonly=True, default='Mới')
    payment_type = fields.Selection([
        ('inbound', 'Phiếu Thu'),
        ('outbound', 'Phiếu Chi')
    ], string='Loại phiếu', required=True, default='outbound')
    partner_id = fields.Many2one('res.partner', string='Đối tác', required=False)
    amount = fields.Float(string='Số tiền', required=True)
    payment_date = fields.Date(string='Ngày thanh toán', default=fields.Date.today)
    proposal_id = fields.Many2one('proposal.sheet', string='Đề xuất liên quan')
    description = fields.Text(string='Mô tả')
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('waiting_approval', 'Chờ duyệt'),
        ('approved', 'Đã duyệt'),
        ('paid', 'Đã chi')
    ], default='draft', string='Trạng thái')

    def action_submit(self):
        self.write({'state': 'waiting_approval'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_paid(self):
        self.write({'state': 'paid'})

    @api.model
    def create(self, vals):
        if vals.get('name', 'Mới') == 'Mới':
            vals['name'] = self.env['ir.sequence'].next_by_code('internal.payment') or 'Mới'
        return super().create(vals)
