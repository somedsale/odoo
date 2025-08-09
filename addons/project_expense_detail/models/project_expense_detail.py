# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ProjectExpenseDetail(models.Model):
    _name = 'project.expense.detail'
    _description = 'Chi phí chi tiết theo dự án và dự toán'
    _order = 'project_id'

    project_id = fields.Many2one(
        'project.project', string='Dự án', required=True)
    estimate_line_id = fields.Many2one('cost.estimate.line', string='Đầu mục', required=True)
    
    category = fields.Selection([
        ('material', 'Vật tư'),
        ('labor', 'Nhân công'),
        ('machine', 'Máy móc'),
        ('service', 'Dịch vụ khác')
    ], string='Loại chi phí', required=True)
    quantity = fields.Float(string='Số lượng', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Đơn vị tính')
    price_unit = fields.Float(string='Đơn giá')
    total_amount = fields.Monetary(
        string='Thành tiền', compute='_compute_total', store=True)
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id.id)
    note = fields.Text(string='Ghi chú')

    @api.depends('quantity', 'price_unit')
    def _compute_total(self):
        for rec in self:
            rec.total_amount = rec.quantity * rec.price_unit

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        # Lấy kết quả group nhưng KHÔNG để Odoo tự sum quantity
        # => bỏ 'quantity' ra khỏi fields khi gọi super
        fields_no_sum = [f for f in fields if f != 'quantity']
        res = super().read_group(domain, fields_no_sum, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)

        if not groupby:
            return res

        if 'estimate_line_id' in groupby:
            est_ids = set()
            for r in res:
                val = r.get('estimate_line_id')
                if val:
                    est_ids.add(val[0] if isinstance(val, (list, tuple)) else val)
            if est_ids:
                est_qty_map = dict(
                    self.env['cost.estimate.line']
                    .sudo()
                    .browse(list(est_ids))
                    .mapped(lambda l: (l.id, l.quantity))
                )
                for r in res:
                    val = r.get('estimate_line_id')
                    if val:
                        est_id = val[0] if isinstance(val, (list, tuple)) else val
                        est_qty = est_qty_map.get(est_id, 0.0)
                        # Gán giá trị quantity thủ công
                        r['quantity'] = est_qty
                        r['estimate_line_qty'] = est_qty
        return res


    
