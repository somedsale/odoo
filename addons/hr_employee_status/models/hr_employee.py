# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    employee_status = fields.Selection(
        [
            ("probation", "Thử việc"),
            ("official", "Chính thức"),
            ("maternity", "Nghỉ thai sản"),
            ("suspended", "Tạm nghỉ"),
            ("resigned", "Đã nghỉ việc"),
        ],
        string="Trạng thái nhân sự",
        default="official",
        tracking=True,
    )

    resignation_date = fields.Date(string="Ngày nghỉ việc", tracking=True)
    resignation_reason = fields.Text(string="Lý do nghỉ việc")
    status_note = fields.Text(string="Ghi chú trạng thái")

    @api.onchange("employee_status")
    def _onchange_employee_status(self):
        for rec in self:
            # Gợi ý tự set ngày nghỉ khi chọn đã nghỉ việc
            if rec.employee_status == "resigned" and not rec.resignation_date:
                rec.resignation_date = fields.Date.context_today(rec)

    def write(self, vals):
        res = super().write(vals)

        # (Tuỳ chọn) Tự archive khi đã nghỉ việc
        if "employee_status" in vals:
            resigned_recs = self.filtered(lambda r: r.employee_status == "resigned")
            if resigned_recs:
                # Nếu bạn KHÔNG muốn tự ẩn record thì comment dòng này
                resigned_recs.filtered(lambda r: r.active).write({"active": False})

        return res