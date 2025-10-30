from odoo import models, fields, api

class AccountPaymentRequest(models.Model):
    _inherit = "account.payment.request"

    employee_advance_id = fields.Many2one("account.employee.advance", string="Theo dõi tạm ứng")

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        """Khi chọn nhân viên -> tự gán bản ghi Theo dõi tạm ứng"""
        for rec in self:
            if rec.employee_id:
                advance = self.env["account.employee.advance"].search(
                    [("employee_id", "=", rec.employee_id.id)], limit=1
                )
                rec.employee_advance_id = advance.id if advance else False

    @api.model
    def create(self, vals):
        """Khi tạo mới, nếu có employee_id -> tự link vào employee_advance_id"""
        if vals.get("employee_id") and not vals.get("employee_advance_id"):
            advance = self.env["account.employee.advance"].search(
                [("employee_id", "=", vals["employee_id"])], limit=1
            )
            if advance:
                vals["employee_advance_id"] = advance.id
        return super().create(vals)
    def write(self, vals):
        """Khi cập nhật, nếu tick Tạm ứng hoặc đổi nhân viên -> tự gán bản ghi Theo dõi"""
        res = super().write(vals)
        for rec in self:
            # ✅ Nếu tick "Tạm ứng" và có nhân viên mà chưa có liên kết theo dõi
            if rec.is_advance and rec.employee_id and not rec.employee_advance_id:
                advance = rec.env["account.employee.advance"].search(
                    [("employee_id", "=", rec.employee_id.id)], limit=1
                )
                if not advance:
                    advance = rec.env["account.employee.advance"].create({
                        "employee_id": rec.employee_id.id
                    })
                rec.sudo().write({"employee_advance_id": advance.id})  # ✅ tránh loop

            # ✅ Nếu bỏ tick "Tạm ứng" thì gỡ liên kết, nhưng không gây lặp
            elif not rec.is_advance and rec.employee_advance_id:
                rec.sudo().write({"employee_advance_id": False})  # ✅ an toàn
        return res