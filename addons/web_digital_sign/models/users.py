# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class Users(models.Model):
    _inherit = "res.users"

    digital_signature = fields.Binary(string="Chữ kí điện tử", help="Chữ kí điện tử")
    def write(self, vals):
        # Nếu chỉ cập nhật mỗi digital_signature và là tự sửa chính mình -> cho phép bằng sudo
        only_sig = set(vals.keys()).issubset({'digital_signature'})
        if only_sig:
            # kiểm tra tất cả record đang ghi đều là chính user hiện tại
            ids_are_self = all(rec.id == self.env.user.id for rec in self)
            if ids_are_self:
                return super(Users, self.sudo()).write(vals)
        # mặc định: dùng cơ chế ACL/Rule bình thường
        return super().write(vals)
