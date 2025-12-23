from odoo import models, fields, api

class ProjectProfitLost(models.Model):
    _name = 'project.profit.lost'
    _description = 'Phân tích lời lỗ công trình'
    _rec_name = "project_id"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    active = fields.Boolean(default=True)
    project_id = fields.Many2one('project.project', string='Dự án', required=True, index=True)
    name = fields.Char(
        string='Tên phân tích', 
        compute="_compute_name", 
        store=True
    )

    num_contract = fields.Char(string='Số hợp đồng')
    contract_value = fields.Monetary(string='Giá trị hợp đồng', currency_field='currency_id')
    settlement_value = fields.Monetary(string='Giá trị quyết toán', currency_field='currency_id', compute='_compute_settlement_value', store=True)  
    invoice_amount = fields.Monetary(string='Số tiền hóa đơn', currency_field='currency_id', store=True, compute="_compute_fill_invoice_amount")  
    revenue = fields.Monetary(string='Số tiền đã thanh toán', currency_field='currency_id',  store=True)
    material_cost = fields.Monetary(string='Chi phí nguyên vật liệu (VT)', currency_field='currency_id', store=True)
    labor_cost = fields.Monetary(string='Chi phí nhân công', currency_field='currency_id', store=True)
    other_cost = fields.Monetary(string='Chi phí khác (SXC)', currency_field='currency_id', store=True)
    expense = fields.Monetary(string='Tổng chi phí', currency_field='currency_id',  store=True)
    profit = fields.Monetary(string='Lãi/Lỗ', currency_field='currency_id',  store=True, compute="_compute_profit")
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    detail_ids = fields.One2many("project.profit.lost.detail", "profit_lost_id", string="Chi tiết")
    is_highlighted = fields.Boolean(string="Highlighted", default=False)
    settlement_ids = fields.One2many(
    'customer.settlement',
    compute="_compute_settlement_ids",
    string="Hồ sơ quyết toán",
)
    invoice_ids = fields.One2many(
    'customer.invoice',
    compute='_compute_invoice_ids',
    string='Hóa đơn khách hàng',
)
    receivable_amount = fields.Monetary(
    string="Số tiền nợ phải thu",
    currency_field='currency_id',
    compute='_compute_receivable_amount',
    store=True
)
    @api.depends('settlement_value', 'revenue')
    def _compute_receivable_amount(self):
        for rec in self:
            rec.receivable_amount = (rec.settlement_value or 0.0) - (rec.revenue or 0.0)
    def _compute_invoice_ids(self):
        Invoice = self.env['customer.invoice']
        for rec in self:
            rec.invoice_ids = Invoice.search([
                ('project_id', '=', rec.project_id.id)
            ])
    @api.depends('settlement_ids.amount_settlement','settlement_ids')
    def _compute_settlement_value(self):
        for rec in self:
            rec.settlement_value = sum(
                rec.settlement_ids.mapped('amount_settlement')
            )
    def _compute_settlement_ids(self):
        Settlement = self.env['customer.settlement']
        for rec in self:
            rec.settlement_ids = Settlement.search([
                ('project_id', '=', rec.project_id.id)
            ])
    @api.depends("project_id")
    def _compute_name(self):
        for rec in self:
            if rec.project_id:
                rec.name = f"Chi tiết lời lỗ công trình - {rec.project_id.name}"
            else:
                rec.name = "Chi tiết lời lỗ công trình"
    @api.depends("settlement_value")
    def _compute_profit(self):
        for rec in self:
            if rec.settlement_value:
                rec.profit = rec.settlement_value - rec.expense
            else:
                rec.profit = 0
    @api.depends(
        'settlement_value',
        'invoice_ids.amount_total'
    )
    def _compute_fill_invoice_amount(self):
        for rec in self:
            if rec.invoice_ids:
                rec.invoice_amount = sum(
                    rec.invoice_ids.mapped('amount_total')
                )
            else:
                rec.invoice_amount = rec.settlement_value or 0.0

    def _recompute_values(self):
        for rec in self:
            rec.detail_ids.unlink()  # clear cũ để cập nhật lại

            # Doanh thu
            receipts = self.env['account.receipt'].search([
                ('project_id', '=', rec.project_id.id),
                ('state', '=', 'posted')
            ])
            rec.revenue = sum(receipts.mapped('amount'))

            # Hợp đồng
            contract = self.env['contract.management'].search([('project_id','=',rec.project_id.id)], limit=1)
            rec.num_contract = contract.num_contract if contract else ''
            rec.contract_value = contract.contract_value if contract else 0.0

            # Chi phí
            payments = self.env['account.payment.request'].search([
                ('project_id', '=', rec.project_id.id),
                ('status_expense', '=', 'paid')
            ])
            rec.expense = sum(payments.mapped('total'))
            rec.material_cost = sum(payments.filtered(lambda x: x.expense_type == 'material').mapped('total'))
            rec.labor_cost = sum(payments.filtered(lambda x: x.expense_type == 'labor').mapped('total'))
            rec.other_cost = sum(payments.filtered(lambda x: x.expense_type == 'manufacturing').mapped('total'))

            for p in payments:
                vals = {
                    'profit_lost_id': rec.id,
                    'date': p.date_payment,
                    'description': p.note,
                    'material_amount': 0.0,
                    'labor_amount': 0.0,
                    'other_amount': 0.0,
                }
                if p.expense_type == 'material':
                    vals['material_amount'] = p.total
                elif p.expense_type == 'labor':
                    vals['labor_amount'] = p.total
                elif p.expense_type == 'manufacturing':
                    vals['other_amount'] = p.total

                rec.detail_ids.create(vals)
            # Lợi nhuận
            if rec.settlement_value:
                rec.profit = rec.settlement_value - rec.expense
            else:
                rec.profit = 0
    @api.model
    def create_or_update(self, project_id):
        rec = self.search([('project_id', '=', project_id)], limit=1)
        if not rec:
            rec = self.create({'project_id': project_id})
        rec._recompute_values()
        return rec

    def load_all_projects(self):
        Project = self.env['project.project']

        # 1) Lấy các dự án hợp lệ
        allowed_projects = Project.search([
            ('is_internal_project2', '=', False),
            ('id', '!=', 4),
        ])
        allowed_ids = set(allowed_projects.ids)

        # 2) Lấy danh sách project_id đã có trong bảng profit.lost
        existing = self.search([])
        existing_ids = set(existing.mapped('project_id').ids)

        # 3) Xóa các record thuộc project không hợp lệ
        invalid_ids = existing_ids - allowed_ids
        if invalid_ids:
            self.search([('project_id', 'in', list(invalid_ids))]).write({'active': False})

        # 4) Tạo record cho project còn thiếu (chưa có trong profit.lost)
        missing_ids = allowed_ids - existing_ids
        for mid in missing_ids:
            self.create({'project_id': mid})

        # 5) Chỉ recompute cho các project hợp lệ
        self.search([('project_id', 'in', list(allowed_ids))])._recompute_values()

    @api.model
    def action_open_profit_lost(self):
        # Đồng bộ trước khi mở
        # self._load_all_projects()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Phân tích lời lỗ công trình',
            'res_model': 'project.profit.lost',
            'view_mode': 'tree,form,pivot',
        }
    def action_highlight(self):
        for rec in self:
            rec.is_highlighted = not rec.is_highlighted