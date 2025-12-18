# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AccountReceipt(models.Model):
    _name = 'account.receipt'
    _description = 'Phiếu Thu Kế Toán'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Số phiếu thu', required=True, readonly=True, default="new")
    date = fields.Date(string='Ngày thu', required=True, default=fields.Date.today)
    project_id = fields.Many2one('project.project', string='Dự án')
    partner_type = fields.Selection([
        ('customer', 'Khách hàng'),
        ('employee', 'Nhân viên'),
    ], string="Loại đối tượng", default='customer', required=True)
    partner_id = fields.Many2one('res.partner', string='Khách hàng')
    employee_id = fields.Many2one('hr.employee', string='Nhân viên')
    amount = fields.Float(string='Số tiền', required=True)
    currency_id = fields.Many2one('res.currency', string='Tiền tệ', default=lambda self: self.env.company.currency_id)
    payment_method = fields.Selection([
        ('cash', 'Tiền mặt'),
        ('bank', 'Chuyển khoản')
    ], string='Phương thức thanh toán', default='cash', required=True)
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('posted', 'Đã ghi sổ'),
        ('cancel', 'Đã hủy')
    ], string='Trạng thái', default='draft', readonly=True)
    note = fields.Text(string='Ghi chú')
    type_revenue = fields.Selection([
        ('done_revenue', 'Doanh thu đã thực hiện'),
        ('advance', 'Doanh thu chưa thực hiện (Tạm ứng)'),
        ('loan', 'Các khoản vay'),
        ('explain', 'Giải chi'),
        ('other', 'Các khoản thu khác'),
    ], string='Loại doanh thu', required=True, default='done_revenue')
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string="Tệp đính kèm",
    )
    @api.model_create_multi
    def create(self, vals_list):
        # xử lý sequence trước
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'new':
                vals['name'] = self.env['ir.sequence'].next_by_code('account.receipt') or '/'
        records = super().create(vals_list)

        # gán res_model/res_id cho các attachment "mồ côi"
        for rec in records:
            orphan_attachments = rec.attachment_ids.filtered(
                lambda a: not a.res_model or not a.res_id
            )
            if orphan_attachments:
                orphan_attachments.sudo().write({
                    'res_model': rec._name,
                    'res_id': rec.id,
                })
        return records

    # ---------- WRITE: phiếu cũ bổ sung file ----------
    def write(self, vals):
        res = super().write(vals)
        if 'attachment_ids' in vals:
            for rec in self:
                orphan_attachments = rec.attachment_ids.filtered(
                    lambda a: not a.res_model or not a.res_id
                )
                if orphan_attachments:
                    orphan_attachments.sudo().write({
                        'res_model': rec._name,
                        'res_id': rec.id,
                    })
        return res

    def action_post(self):
        for receipt in self:
            # Chỉ tạo dòng tiền nếu có dự án
            if receipt.project_id:
                self.env['project.cash.flow'].create({
                    'project_id': receipt.project_id.id,
                    'partner_id': receipt.partner_id.id,
                    'type': 'in',
                    'amount': receipt.amount,
                    'currency_id': receipt.currency_id.id,
                    'receipt_id': receipt.id,
                    'date': receipt.date,
                })
            receipt.write({'state': 'posted'})
        return True

    def action_cancel(self):
        self.write({'state': 'cancel'})
        return True