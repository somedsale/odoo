from odoo import api, fields, models


class BidProject(models.Model):
    _name = 'bid.project'
    _description = 'Dự án dự thầu'
    _order = 'id desc'

    name = fields.Char(string='Tên dự án dự thầu', required=True)
    note = fields.Text(string='Ghi chú')
    section_ids = fields.One2many('bid.section', 'project_id', string='Hạng mục')
    line_ids = fields.One2many('bid.line', 'project_id', string='Vật tư', readonly=True)
    amount_total = fields.Float(string='Tổng tiền dự thầu', compute='_compute_amount_total', store=True)
    supplier_best_amount_total = fields.Float(string='Tổng giá NCC tốt nhất', compute='_compute_amount_total', store=True)
    saving_amount_total = fields.Float(string='Chênh lệch so với dự thầu', compute='_compute_amount_total', store=True)
    section_count = fields.Integer(string='Số hạng mục', compute='_compute_counts')
    line_count = fields.Integer(string='Số dòng vật tư', compute='_compute_counts')
    supplier_quote_count = fields.Integer(string='Số báo giá NCC', compute='_compute_counts')

    @api.depends('section_ids.amount_total', 'section_ids.supplier_best_amount_total')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.section_ids.mapped('amount_total'))
            rec.supplier_best_amount_total = sum(rec.section_ids.mapped('supplier_best_amount_total'))
            rec.saving_amount_total = rec.amount_total - rec.supplier_best_amount_total

    def _compute_counts(self):
        Quote = self.env['bid.supplier.quote']
        for rec in self:
            rec.section_count = len(rec.section_ids)
            rec.line_count = len(rec.line_ids)
            rec.supplier_quote_count = Quote.search_count([('project_id', '=', rec.id)])

    def action_open_owl_project_view(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'name': 'Xem dự án OWL',
            'tag': 'bid_estimation_project_view_action',
            'params': {
                'project_id': self.id,
            },
        }

    def action_open_sections(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Hạng mục',
            'res_model': 'bid.section',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_open_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vật tư',
            'res_model': 'bid.line',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_open_supplier_quotes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Báo giá nhà cung cấp',
            'res_model': 'bid.supplier.quote',
            'view_mode': 'tree,form,pivot,graph',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }


class BidSection(models.Model):
    _name = 'bid.section'
    _description = 'Hạng mục dự thầu'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Thứ tự', default=10)
    project_id = fields.Many2one('bid.project', string='Dự án', required=True, ondelete='cascade')
    name = fields.Char(string='Tên hạng mục', required=True)
    code = fields.Char(string='Mã sheet')
    item_ids = fields.One2many('bid.item', 'section_id', string='Đầu mục')
    line_ids = fields.One2many('bid.line', 'section_id', string='Vật tư')
    amount_total = fields.Float(string='Tổng tiền dự thầu', compute='_compute_amount_total', store=True)
    supplier_best_amount_total = fields.Float(string='Tổng giá NCC tốt nhất', compute='_compute_amount_total', store=True)
    saving_amount_total = fields.Float(string='Chênh lệch so với dự thầu', compute='_compute_amount_total', store=True)

    @api.depends('line_ids.amount_total', 'line_ids.supplier_best_amount_total')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped('amount_total'))
            rec.supplier_best_amount_total = sum(rec.line_ids.mapped('supplier_best_amount_total'))
            rec.saving_amount_total = rec.amount_total - rec.supplier_best_amount_total


class BidItem(models.Model):
    _name = 'bid.item'
    _description = 'Đầu mục nhỏ dự thầu'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Thứ tự', default=10)
    project_id = fields.Many2one('bid.project', string='Dự án', required=True, ondelete='cascade')
    section_id = fields.Many2one('bid.section', string='Hạng mục', required=True, ondelete='cascade')
    parent_id = fields.Many2one('bid.item', string='Đầu mục cha', ondelete='cascade')
    child_ids = fields.One2many('bid.item', 'parent_id', string='Đầu mục con')
    name = fields.Char(string='Tên đầu mục', required=True)
    code = fields.Char(string='Mã')
    # Dùng cho trường hợp Excel có dòng vật tư cha như 32, sau đó 32.1/32.2 là vật tư con.
    # Dòng 32 thường chỉ có ĐVT/Số lượng, không có đơn giá, nên lưu ở bid.item để giữ đúng cây.
    is_material_parent = fields.Boolean(string='Là vật tư cha')
    uom_name = fields.Char(string='Đơn vị')
    quantity = fields.Float(string='Khối lượng')
    price_unit = fields.Float(string='Đơn giá dự thầu')
    line_ids = fields.One2many('bid.line', 'item_id', string='Vật tư')
    amount_total = fields.Float(string='Tổng tiền dự thầu', compute='_compute_amount_total', store=True)
    supplier_best_amount_total = fields.Float(string='Tổng giá NCC tốt nhất', compute='_compute_amount_total', store=True)
    saving_amount_total = fields.Float(string='Chênh lệch so với dự thầu', compute='_compute_amount_total', store=True)

    @api.depends('line_ids.amount_total', 'child_ids.amount_total', 'line_ids.supplier_best_amount_total', 'child_ids.supplier_best_amount_total')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped('amount_total')) + sum(rec.child_ids.mapped('amount_total'))
            rec.supplier_best_amount_total = sum(rec.line_ids.mapped('supplier_best_amount_total')) + sum(rec.child_ids.mapped('supplier_best_amount_total'))
            rec.saving_amount_total = rec.amount_total - rec.supplier_best_amount_total


class BidLine(models.Model):
    _name = 'bid.line'
    _description = 'Dòng vật tư dự thầu'
    _order = 'section_id, sequence, id'

    sequence = fields.Integer(string='STT', default=10)
    project_id = fields.Many2one('bid.project', string='Dự án', required=True, ondelete='cascade')
    section_id = fields.Many2one('bid.section', string='Hạng mục', required=True, ondelete='cascade')
    item_id = fields.Many2one('bid.item', string='Đầu mục', ondelete='set null')
    stt = fields.Char(string='STT Excel')
    name = fields.Char(string='Tên vật tư', required=True)
    uom_name = fields.Char(string='Đơn vị')
    quantity = fields.Float(string='Khối lượng')
    price_unit = fields.Float(string='Đơn giá dự thầu')
    amount_total = fields.Float(string='Thành tiền dự thầu', compute='_compute_amount_total', store=True)
    technical_note = fields.Text(string='Thông số kỹ thuật/Ghi chú')
    parent_id = fields.Many2one('bid.line', string='Vật tư cha', ondelete='cascade')
    child_ids = fields.One2many('bid.line', 'parent_id', string='Vật tư con')

    supplier_quote_ids = fields.One2many('bid.supplier.quote', 'line_id', string='Báo giá NCC')
    supplier_quote_count = fields.Integer(string='Số NCC', compute='_compute_supplier_compare', store=True)
    supplier_best_price_unit = fields.Float(string='Đơn giá NCC thấp nhất', compute='_compute_supplier_compare', store=True)
    supplier_best_amount_total = fields.Float(string='Thành tiền NCC thấp nhất', compute='_compute_supplier_compare', store=True)
    supplier_best_partner_id = fields.Many2one('res.partner', string='NCC thấp nhất', compute='_compute_supplier_compare', store=True)
    selected_quote_id = fields.Many2one('bid.supplier.quote', string='Báo giá đã chọn', compute='_compute_supplier_compare', store=True)
    selected_partner_id = fields.Many2one('res.partner', string='NCC đã chọn', compute='_compute_supplier_compare', store=True)
    selected_price_unit = fields.Float(string='Đơn giá NCC đã chọn', compute='_compute_supplier_compare', store=True)
    selected_amount_total = fields.Float(string='Thành tiền NCC đã chọn', compute='_compute_supplier_compare', store=True)
    saving_amount = fields.Float(string='Chênh lệch tốt nhất', compute='_compute_supplier_compare', store=True)
    saving_percent = fields.Float(string='% chênh lệch tốt nhất', compute='_compute_supplier_compare', store=True)

    @api.depends('quantity', 'price_unit')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = (rec.quantity or 0.0) * (rec.price_unit or 0.0)

    @api.depends(
        'quantity', 'amount_total',
        'supplier_quote_ids.price_unit', 'supplier_quote_ids.amount_total',
        'supplier_quote_ids.partner_id', 'supplier_quote_ids.is_selected'
    )
    def _compute_supplier_compare(self):
        for rec in self:
            quotes = rec.supplier_quote_ids.filtered(lambda q: q.price_unit > 0)
            rec.supplier_quote_count = len(rec.supplier_quote_ids)
            best = quotes.sorted(lambda q: (q.price_unit, q.id))[:1]
            best = best[0] if best else False
            selected = rec.supplier_quote_ids.filtered('is_selected')[:1]
            selected = selected[0] if selected else False

            rec.supplier_best_price_unit = best.price_unit if best else 0.0
            rec.supplier_best_amount_total = best.amount_total if best else 0.0
            rec.supplier_best_partner_id = best.partner_id if best else False

            rec.selected_quote_id = selected if selected else False
            rec.selected_partner_id = selected.partner_id if selected else False
            rec.selected_price_unit = selected.price_unit if selected else 0.0
            rec.selected_amount_total = selected.amount_total if selected else 0.0

            compare_amount = best.amount_total if best else 0.0
            rec.saving_amount = (rec.amount_total or 0.0) - compare_amount if best else 0.0
            rec.saving_percent = ((rec.saving_amount / rec.amount_total) * 100.0) if rec.amount_total and best else 0.0


class BidSupplierQuote(models.Model):
    _name = 'bid.supplier.quote'
    _description = 'Báo giá nhà cung cấp cho vật tư dự thầu'
    _order = 'line_id, price_unit, id'

    line_id = fields.Many2one('bid.line', string='Vật tư', required=True, ondelete='cascade')
    project_id = fields.Many2one('bid.project', string='Dự án', related='line_id.project_id', store=True, readonly=True)
    section_id = fields.Many2one('bid.section', string='Hạng mục', related='line_id.section_id', store=True, readonly=True)
    item_id = fields.Many2one('bid.item', string='Đầu mục', related='line_id.item_id', store=True, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Nhà cung cấp', required=True)
    uom_name = fields.Char(string='Đơn vị', related='line_id.uom_name', store=True, readonly=True)
    quantity = fields.Float(string='Khối lượng', related='line_id.quantity', store=True, readonly=True)
    bid_price_unit = fields.Float(string='Đơn giá dự thầu', related='line_id.price_unit', store=True, readonly=True)
    price_unit = fields.Float(string='Đơn giá NCC', required=True)
    amount_total = fields.Float(string='Thành tiền NCC', compute='_compute_amount_total', store=True)
    diff_price_unit = fields.Float(string='Chênh đơn giá', compute='_compute_amount_total', store=True)
    diff_amount_total = fields.Float(string='Chênh thành tiền', compute='_compute_amount_total', store=True)
    diff_percent = fields.Float(string='% chênh lệch', compute='_compute_amount_total', store=True)
    is_selected = fields.Boolean(string='Chọn NCC này')
    warranty = fields.Char(string='Bảo hành')
    delivery_time = fields.Char(string='Thời gian giao hàng')
    payment_term = fields.Char(string='Điều khoản thanh toán')
    note = fields.Text(string='Ghi chú')

    @api.depends('quantity', 'price_unit', 'bid_price_unit')
    def _compute_amount_total(self):
        for rec in self:
            qty = rec.quantity or 0.0
            rec.amount_total = qty * (rec.price_unit or 0.0)
            rec.diff_price_unit = (rec.bid_price_unit or 0.0) - (rec.price_unit or 0.0)
            rec.diff_amount_total = qty * rec.diff_price_unit
            rec.diff_percent = (rec.diff_price_unit / rec.bid_price_unit * 100.0) if rec.bid_price_unit else 0.0

    @api.onchange('is_selected')
    def _onchange_is_selected(self):
        if self.is_selected and self.line_id:
            for quote in self.line_id.supplier_quote_ids:
                if quote != self:
                    quote.is_selected = False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records.filtered('is_selected'):
            rec.line_id.supplier_quote_ids.filtered(lambda q: q.id != rec.id and q.is_selected).write({'is_selected': False})
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get('is_selected'):
            for rec in self.filtered('is_selected'):
                others = rec.line_id.supplier_quote_ids.filtered(lambda q: q.id != rec.id and q.is_selected)
                others.write({'is_selected': False})
        return res

    def action_select_quote(self):
        for rec in self:
            rec.line_id.supplier_quote_ids.write({'is_selected': False})
            rec.is_selected = True
        return True
