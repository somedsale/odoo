from odoo import models, fields, api

class CostAdditionalExpense(models.Model):
    _name = 'cost.additional.expense'
    _description = 'Phiếu chi phí bổ sung'
    _order = 'id desc'

    name = fields.Char(string='Tên chi phí', required=True)

    price_unit = fields.Monetary(string='Số tiền gốc')

    tax_id = fields.Many2one(
        'account.tax',
        string='Thuế áp dụng',
        domain=[('type_tax_use', '=', 'sale')]
    )

    price_subtotal = fields.Monetary(
        string='Thành tiền (chưa thuế)',
        compute='_compute_total_price',
        store=True
    )
    price_tax = fields.Monetary(
        string='Thuế',
        compute='_compute_total_price',
        store=True
    )
    price_total = fields.Monetary(
        string='Tổng cộng (sau thuế)',
        compute='_compute_total_price',
        store=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    @api.depends('price_unit', 'tax_id', 'currency_id')
    def _compute_total_price(self):
        for rec in self:
            subtotal = rec.price_unit or 0.0
            if rec.tax_id:
                res = rec.tax_id.compute_all(
                    rec.price_unit,
                    currency=rec.currency_id,
                    quantity=1
                )
                rec.price_subtotal = res['total_excluded']
                rec.price_tax = sum(t.get('amount', 0.0) for t in res['taxes'])
                rec.price_total = res['total_included']
            else:
                rec.price_subtotal = subtotal
                rec.price_tax = 0.0
                rec.price_total = subtotal
