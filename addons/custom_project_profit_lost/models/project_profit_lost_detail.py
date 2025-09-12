from odoo import fields,models,api
class ProjectProfitLostDetail(models.Model):
    _name = "project.profit.lost.detail"
    _description = "Chi tiết lời lỗ công trình"
    _order="date desc"

    profit_lost_id = fields.Many2one("project.profit.lost", string="Tổng hợp", ondelete="cascade")
    date = fields.Date("Ngày")
    description = fields.Char("Diễn giải")
    # amount = fields.Monetary("Số tiền", currency_field="currency_id")
    # type = fields.Selection([
    #     ("material", "Chi phí vật tư"),
    #     ("labor", "Chi phí nhân công"),
    #     ("manufacturing", "Chi phí khác"),
    # ], string="Loại")
    material_amount = fields.Monetary(
        "Chi phí nguyên vật liệu (VT)", currency_field="currency_id"
    )
    labor_amount = fields.Monetary(
        "Chi phí nhân công", currency_field="currency_id"
    )
    other_amount = fields.Monetary(
        "Chi phí khác (SXC)", currency_field="currency_id"
    )

    total_amount = fields.Monetary(
        "Tổng chi phí", compute="_compute_total", store=True, currency_field="currency_id"
    )
    @api.depends("material_amount", "labor_amount", "other_amount")
    def _compute_total(self):
        for rec in self:
            rec.total_amount = (rec.material_amount or 0) + (rec.labor_amount or 0) + (rec.other_amount or 0)
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)
