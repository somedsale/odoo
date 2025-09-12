from odoo import models, fields, api,_

class ProjectCashFlow(models.Model):
    _name = 'project.cash.flow'
    _description = 'Dòng tiền dự án'

    name = fields.Char(string='Mã dòng tiền', required=True, copy=False, readonly=True,
                       default=lambda self: _('New'))
    date = fields.Date(string='Ngày', required=True, default=fields.Date.context_today)
    project_id = fields.Many2one('project.project', string='Dự án')
    partner_id = fields.Many2one('res.partner', string='Đối tác')
    type = fields.Selection([
        ('in', 'Thu'),
        ('out', 'Chi'),
    ], string='Loại dòng tiền', required=True)

    amount = fields.Monetary(string='Số tiền', required=True)
    currency_id = fields.Many2one('res.currency', string='Tiền tệ', default=lambda self: self.env.company.currency_id.id)

    receipt_id = fields.Many2one('account.receipt', string='Phiếu thu')
    account_payment_id = fields.Many2one('account.payment.request', string='Phiếu chi')

    note = fields.Text(string='Ghi chú')
    total_in_all = fields.Monetary(string="Tổng Thu Toàn Bộ", compute="_compute_totals_all", store=True)
    total_out_all = fields.Monetary(string="Tổng Chi Toàn Bộ", compute="_compute_totals_all", store=True)
    balance_all = fields.Monetary(string="Số dư Toàn Bộ", compute="_compute_totals_all", store=True)

    @api.depends()
    def _compute_totals_all(self):
        total_in = sum(self.env['project.cash.flow'].search([]).filtered(lambda r: r.type=='in').mapped('amount'))
        total_out = sum(self.env['project.cash.flow'].search([]).filtered(lambda r: r.type=='out').mapped('amount'))
        balance = total_in - total_out
        for rec in self:
            rec.total_in_all = total_in
            rec.total_out_all = total_out
            rec.balance_all = balance
    @api.onchange('receipt_id')
    def _onchange_receipt_id(self):
        """Khi chọn phiếu thu thì tự gán loại dòng tiền là Thu (in)"""
        if self.receipt_id:
            self.type = 'in'
            self.partner_id = self.receipt_id.partner_id
            self.amount = self.receipt_id.amount
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('project.cash.flow') or _('New')
        return super().create(vals)
