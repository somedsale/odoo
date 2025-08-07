# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AccountReceipt(models.Model):
    _name = 'account.receipt'
    _description = 'Phiếu Thu Kế Toán'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Số phiếu thu', required=True, readonly=True, default=lambda self: self.env['ir.sequence'].next_by_code('account.receipt'))
    date = fields.Date(string='Ngày thu', required=True, default=fields.Date.today)
    project_id = fields.Many2one('project.project', string='Dự án')
    partner_id = fields.Many2one('res.partner', string='Khách hàng', required=True)
    amount = fields.Float(string='Số tiền', required=True)
    currency_id = fields.Many2one('res.currency', string='Tiền tệ', default=lambda self: self.env.company.currency_id)
    x_payment_method_id = fields.Many2one('payment.method', string='Phương thức thanh toán', required=True)
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('posted', 'Đã ghi sổ'),
        ('cancel', 'Đã hủy')
    ], string='Trạng thái', default='draft', readonly=True)
    note = fields.Text(string='Ghi chú')

    @api.model
    def create(self, vals):
        if not vals.get('name'):
            vals['name'] = self.env['ir.sequence'].next_by_code('account.receipt') or '/'
        return super(AccountReceipt, self).create(vals)

    def action_post(self):
        self.write({'state': 'posted'})
        return True

    def action_cancel(self):
        self.write({'state': 'cancel'})
        return True