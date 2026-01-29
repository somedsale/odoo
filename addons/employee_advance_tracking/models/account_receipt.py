from odoo import models, fields, api

class AccountReceipt(models.Model):
    _inherit = "account.receipt"
    _order = "name desc"

    employee_advance_id = fields.Many2one("account.employee.advance", string="Theo dõi tạm ứng")
    payment_id = fields.Many2one(
        "account.payment.request",
        string="Phiếu chi tạm ứng (CT)",
        domain="[('is_advance','=',True),('employee_id','=',employee_id)]",
    )
    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        for rec in self:
            if rec.employee_id:
                advance = self.env["account.employee.advance"].search(
                    [("employee_id", "=", rec.employee_id.id)], limit=1
                )
                rec.employee_advance_id = advance.id if advance else False
    @api.onchange("payment_id")
    def _onchange_payment_id(self):
        for rec in self:
            if rec.payment_id and rec.payment_id.total:
                rec.amount = rec.payment_id.total
    @api.model
    def create(self, vals):
        rec = super().create(vals)

        # Nếu tạo phiếu thu mà có chọn phiếu chi tạm ứng -> link ngay
        if rec.payment_id:
            rec.payment_id.sudo().write({
                "refund_receipt_id": rec.id
            })

        # Logic gốc (giữ nguyên): gán employee_advance_id nếu thiếu
        if vals.get("employee_id") and not vals.get("employee_advance_id"):
            advance = self.env["account.employee.advance"].search(
                [("employee_id", "=", vals["employee_id"])], limit=1
            )
            if advance:
                rec.sudo().write({"employee_advance_id": advance.id})

        return rec
    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if "payment_id" in vals and rec.payment_id:
            # Gắn phiếu thu hoàn ứng vào phiếu chi
                rec.payment_id.sudo().write({
                    "refund_receipt_id": rec.id
                })
            # Nếu tick "Hoàn ứng" và có nhân viên mà chưa có liên kết theo dõi
            if rec.is_advance_refund and rec.employee_id and not rec.employee_advance_id:
                advance = rec.env["account.employee.advance"].search(
                    [("employee_id", "=", rec.employee_id.id)], limit=1
                )
                if not advance:
                    advance = rec.env["account.employee.advance"].create({
                        "employee_id": rec.employee_id.id
                    })
                rec.sudo().write({"employee_advance_id": advance.id})  # ✅ an toàn, không lặp

            # Nếu bỏ tick "Hoàn ứng" thì gỡ liên kết (tránh vòng lặp)
            elif not rec.is_advance_refund and rec.employee_advance_id:
                rec.sudo().write({"employee_advance_id": False})  # ✅ dùng write() chính nó, không trigger lại write()
        return res
