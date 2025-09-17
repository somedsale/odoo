# -*- coding: utf-8 -*-
from odoo import models, fields, api, _, exceptions
from odoo.exceptions import UserError, ValidationError

# =========================
# Wizard tạo Hóa đơn NCC
# =========================
class PurchaseCreateSupplierInvoiceWizard(models.TransientModel):
    _name = 'purchase.create.supplier.invoice.wizard'
    _description = 'Tạo hóa đơn NCC từ Đơn mua hàng'

    purchase_id = fields.Many2one('purchase.order', string="Đơn mua hàng", required=True, readonly=True)

    contract_id = fields.Many2one(
        'supplier.contract', string="Hợp đồng", required=True,
        domain="[('partner_id', '=', partner_id), ('project_id', '=', project_id)]"
    )
    settlement_id = fields.Many2one('supplier.settlement', string="Hồ sơ quyết toán")

    date = fields.Date("Ngày hóa đơn", required=True, default=fields.Date.context_today)
    due_date = fields.Date("Ngày đến hạn")
    name = fields.Char("Số hóa đơn", required=True)

    amount = fields.Monetary("Số tiền", required=True, currency_field="currency_id")
    currency_id = fields.Many2one('res.currency', required=True, default=lambda self: self.env.company.currency_id)

    note = fields.Text("Diễn giải")

    # tự mang từ PO sang để domain hợp đồng
    partner_id = fields.Many2one('res.partner', string="Nhà cung cấp", readonly=True)
    project_id = fields.Many2one('project.project', string="Dự án", readonly=True)

    # Chọn những Phiếu chi sẽ gán vào Hóa đơn
    payment_request_ids = fields.Many2many(
        'account.payment.request', 'wiz_supplier_invoice_apr_rel', 'wiz_id', 'apr_id',
        string="Phiếu chi sẽ liên kết",
        domain="[('purchase_id', '=', purchase_id), ('invoice_id', '=', False), ('state', 'in', ['confirmed','post','done'])]"
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        po = self.env['purchase.order'].browse(self.env.context.get('active_id'))
        if po:
            res.update({
                'purchase_id': po.id,
                'partner_id': po.partner_id.id,
                'project_id': (po.project_id.id if hasattr(po, 'project_id') and po.project_id else False),
                'currency_id': po.currency_id.id,
                # Gợi ý số tiền còn phải trả (tuỳ bạn, có thể dùng amount_total)
                'amount': getattr(po, 'amount_to_pay', 0.0) or po.amount_total,
                'note': _("Hóa đơn NCC cho PO %s - %s") % (po.name, po.partner_id.display_name),
            })
        return res

    def action_confirm(self):
        self.ensure_one()
        po = self.purchase_id
        if not po or po.state not in ('purchase', 'done'):
            raise UserError(_("Chỉ tạo hóa đơn từ Đơn mua hàng đã xác nhận."))

        # Tạo Hóa đơn NCC
        vals = {
            'name': self.name,
            'contract_id': self.contract_id.id,
            'settlement_id': self.settlement_id.id if self.settlement_id else False,
            'date': self.date,
            'due_date': self.due_date,
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'note': self.note,
            'purchase_id': po.id,  # liên kết PO
        }
        inv = self.env['supplier.invoice'].create(vals)

        # Gán các Phiếu chi được chọn vào Hóa đơn
        if self.payment_request_ids:
            self.payment_request_ids.write({'invoice_id': inv.id})

        # Mở form Hóa đơn vừa tạo
        return {
            "type": "ir.actions.act_window",
            "name": _("Hóa đơn NCC"),
            "res_model": "supplier.invoice",
            "view_mode": "form",
            "res_id": inv.id,
            "target": "current",
        }


# =========================
# Purchase Order (tiện ích)
# =========================
class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    supplier_invoice_count = fields.Integer(
        string="Số hóa đơn NCC", compute='_compute_supplier_invoice_count'
    )

    def _compute_supplier_invoice_count(self):
        for po in self:
            po.supplier_invoice_count = self.env['supplier.invoice'].search_count([('purchase_id', '=', po.id)])

    def action_view_supplier_invoices(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Hóa đơn NCC"),
            "res_model": "supplier.invoice",
            "view_mode": "tree,form",
            "domain": [("purchase_id", "=", self.id)],
            "context": {"default_purchase_id": self.id,
                        "default_partner_id": self.partner_id.id,
                        "default_project_id": getattr(self, 'project_id', False) and self.project_id.id or False},
        }

    def action_open_create_supplier_invoice_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Tạo hóa đơn NCC"),
            "res_model": "purchase.create.supplier.invoice.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"active_id": self.id},
        }
