from odoo import models, fields, api
from odoo.exceptions import UserError

class AccountPaymentRequest(models.Model):
    _inherit = 'account.payment.request'  # kế thừa model đã có

    def action_post(self):
        # Gọi hàm gốc trước (nếu có)
        res = super(AccountPaymentRequest, self).action_post()

        expense_detail_obj = self.env['project.expense.detail']

        for rec in self:
            if rec.state != 'post':
                # Đảm bảo phiếu ở trạng thái post mới tạo chi phí
                continue

            # Tạo chi phí thực tế từ các dòng chi tiết phiếu chi
            for line in rec.line_ids:
                # Tránh tạo trùng (nếu cần)
                existing = expense_detail_obj.search([
                    ('project_id', '=', rec.project_id.id),
                    ('estimate_line_id', '=', line.estimate_line_id.id if line.estimate_line_id else False),
                    ('category', '=', line.category),
                    ('quantity', '=', line.quantity),
                    ('price_unit', '=', line.price_unit),
                    ('uom_id', '=', line.uom_id.id if line.uom_id else False),
                    ('note', '=', line.note or ''),
                ], limit=1)
                if not existing:
                    expense_detail_obj.create({
                        'project_id': rec.project_id.id,
                        'estimate_line_id': line.estimate_line_id.id if line.estimate_line_id else False,
                        'category': line.category,
                        'quantity': line.quantity,
                        'uom_id': line.uom_id.id if line.uom_id else False,
                        'price_unit': line.price_unit,
                        'note': line.note or '',
                    })

        return res
