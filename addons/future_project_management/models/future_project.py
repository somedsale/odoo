from odoo import models, fields, api

class FutureProject(models.Model):
    _name = "future.project"
    _description = "Future Project"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "expected_bid_date asc, id desc"

    name = fields.Char("Tên dự án", required=True, tracking=True)
    code = fields.Char("Mã nội bộ")

    stage_id = fields.Many2one(
        "future.project.stage",
        string="Trạng thái",
        default=lambda self: self.env["future.project.stage"].search([], limit=1),
        tracking=True,
        group_expand="_group_expand_stages",
    )

    customer_id = fields.Many2one(
        "res.partner",
        string="Chủ đầu tư",
        tracking=True,
    )
    address = fields.Char("Địa chỉ")
    location = fields.Many2one(
        "future.project.location",
        string="Khu vực",
    )
    hospital_type = fields.Selection(
        [
            ("public", "Public Hospital"),
            ("private", "Private Hospital"),
            ("clinic", "Clinic"),
            ("other", "Other"),
        ],
        string="Project Type",
    )

    contact_person = fields.Char("Người tiếp cận")
    contact_phone = fields.Char("Số điện thoại")
    contact_email = fields.Char("Email")

    assigned_user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        default=lambda self: self.env.user,
        tracking=True,
    )

    expected_start_date = fields.Date("Thời gian dự kiến bắt đầu")
    expected_bid_date = fields.Date("Ngày dự kiến ​​đấu thầu")
    expected_end_date = fields.Date("Thời gian dự kiến kết thúc")

    expected_value = fields.Monetary("Giá trị dự kiến")
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )

    probability = fields.Float(
        "Xác suất (%)",
        compute="_compute_probability",
        store=True,
    )

    priority = fields.Selection(
        [("0", "Thấp"), ("1", "Trung bình"), ("2", "Cao")],
        default="1",
        string="Mức độ ưu tiên",
    )

    description = fields.Text("Ghi chú")
    active = fields.Boolean(default=True)

    @api.depends("stage_id")
    def _compute_probability(self):
        for rec in self:
            rec.probability = rec.stage_id.probability if rec.stage_id else 0.0

    def _group_expand_stages(self, stages, domain, order):
        return self.env["future.project.stage"].search([], order="sequence")
