from odoo import models, fields, api


class ProjectExpenseCustom(models.Model):
    _name = 'project.expense.custom'
    _description = 'Chi phí dự án'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "create_date desc"

    name = fields.Char(string="Tên dự án", related="project_id.name", store=True, readonly=True)
    project_id = fields.Many2one('project.project', string="Dự án", required=True, index=True)
    partner_id = fields.Many2one('res.partner', string="Khách hàng", related="project_id.partner_id", store=True, readonly=True,index=True)
    contract_number = fields.Char(string="Số hợp đồng", related="project_id.num_contract", store=True, readonly=True,index=True)
    signature_date = fields.Date(string="Ngày ký hợp đồng", related="project_id.signature_date", store=True, readonly=True,index=True)
    date_start = fields.Date(string="Ngày bắt đầu", related="project_id.date_start", store=True, readonly=True,index=True)
    date_end = fields.Date(string="Ngày kết thúc", related="project_id.date", store=True, readonly=True,index=True)
    currency_id = fields.Many2one('res.currency', string="Tiền tệ", default=lambda self: self.env.company.currency_id)
    payment_request_ids = fields.One2many(
        'account.payment.request',
        'project_expense_id',
        string="Yêu cầu chi tiền"
    )

    # ===== Tổng toàn dự án =====
    # done
    total_spent = fields.Float(string="Tổng đã chi", compute='_compute_costs', store=True)
    # confirmed
    total_not_spent = fields.Float(string="Tổng chưa chi", compute='_compute_costs', store=True)
    # confirmed + done
    total_cost = fields.Float(string="Tổng chi phí theo dõi", compute='_compute_costs', store=True)

    # ===== Đã chi theo phân loại (done) =====
    total_spent_material = fields.Float(string="Đã chi NVL", compute='_compute_costs', store=True)
    total_spent_labor = fields.Float(string="Đã chi Nhân công", compute='_compute_costs', store=True)
    total_spent_manufacturing = fields.Float(string="Đã chi Sản xuất chung", compute='_compute_costs', store=True)

    # ===== Tổng theo phân loại (confirmed + done) =====
    total_material = fields.Float(string="Tổng NVL", compute='_compute_costs', store=True)
    total_labor = fields.Float(string="Tổng Nhân công", compute='_compute_costs', store=True)
    total_manufacturing = fields.Float(string="Tổng Sản xuất chung", compute='_compute_costs', store=True)

    # ===== Chưa chi theo phân loại (confirmed) =====
    total_not_spent_material = fields.Float(string="Chưa chi NVL", compute='_compute_costs', store=True)
    total_not_spent_labor = fields.Float(string="Chưa chi Nhân công", compute='_compute_costs', store=True)
    total_not_spent_manufacturing = fields.Float(string="Chưa chi Sản xuất chung", compute='_compute_costs', store=True)

    @api.depends(
        'payment_request_ids.total',
        'payment_request_ids.state',        # <-- dùng state
        'payment_request_ids.expense_type', # material / labor / manufacturing
    )
    def _compute_costs(self):
        for record in self:
            # ===== Tổng toàn dự án =====
            total_confirmed = 0.0   # chưa chi
            total_done = 0.0        # đã chi

            # ===== Tổng theo phân loại (confirmed + done) =====
            total_material = 0.0
            total_labor = 0.0
            total_manufacturing = 0.0

            # ===== Đã chi theo phân loại (done) =====
            spent_material = 0.0
            spent_labor = 0.0
            spent_manufacturing = 0.0

            # ===== Chưa chi theo phân loại (confirmed) =====
            not_spent_material = 0.0
            not_spent_labor = 0.0
            not_spent_manufacturing = 0.0

            for pr in record.payment_request_ids:
                amount = pr.total or 0.0
                state = pr.state or ''
                category = pr.expense_type or ''

                # Chỉ lấy confirmed + done (bỏ draft / post / cancelled)
                if state not in ('confirmed', 'done'):
                    continue

                # Tổng theo phân loại (confirmed + done)
                if category == 'material':
                    total_material += amount
                elif category == 'labor':
                    total_labor += amount
                elif category == 'manufacturing':
                    total_manufacturing += amount

                # Đã chi / Chưa chi
                if state == 'done':
                    total_done += amount

                    if category == 'material':
                        spent_material += amount
                    elif category == 'labor':
                        spent_labor += amount
                    elif category == 'manufacturing':
                        spent_manufacturing += amount

                elif state == 'confirmed':
                    total_confirmed += amount

                    if category == 'material':
                        not_spent_material += amount
                    elif category == 'labor':
                        not_spent_labor += amount
                    elif category == 'manufacturing':
                        not_spent_manufacturing += amount

            # ===== Gán tổng toàn dự án =====
            record.total_spent = total_done
            record.total_not_spent = total_confirmed
            record.total_cost = total_done + total_confirmed

            # ===== Gán đã chi theo phân loại =====
            record.total_spent_material = spent_material
            record.total_spent_labor = spent_labor
            record.total_spent_manufacturing = spent_manufacturing

            # ===== Gán tổng theo phân loại =====
            record.total_material = total_material
            record.total_labor = total_labor
            record.total_manufacturing = total_manufacturing

            # ===== Gán chưa chi theo phân loại =====
            record.total_not_spent_material = not_spent_material
            record.total_not_spent_labor = not_spent_labor
            record.total_not_spent_manufacturing = not_spent_manufacturing

    @api.model
    def create_or_update_expense(self, project_id):
        expense = self.search([('project_id', '=', project_id)], limit=1)
        if not expense:
            self.create({'project_id': project_id})

    @api.model
    def _load_all_projects(self):
        for project in self.env['project.project'].search([]):
            self.create_or_update_expense(project.id)