from odoo import fields, models # type: ignore
from datetime import datetime

class SaleOrder(models.Model):
    _inherit = 'sale.order'  # Kế thừa model sale.order

    custom_reference = fields.Char(string='Custom Reference', help='A custom reference for this quotation')
    formatted_date = fields.Char(
        string='Formatted Date',
        compute='_compute_formatted_date',
        store=False,  # Không lưu vào DB, chỉ tính toán khi cần
        help='Formatted date in the format: Tp. Hồ Chí Minh, ngày DD tháng MM năm YYYY'
    )

    def _compute_formatted_date(self):
        for record in self:
            # Lấy ngày từ date_order, nếu không có thì dùng ngày hiện tại
            date = record.date_order or datetime.now()
            record.formatted_date = f"Tp. Hồ Chí Minh, ngày {date.day:02d} tháng {date.month:02d} năm {date.year}"
    # x_hr_address = fields.Char(string="Địa chỉ nhân viên")
    # x_hr_phone = fields.Char(string="SĐT nhân viên")

    # @api.model
    # def create(self, vals):
    #     res = super().create(vals)
    #     if res.user_id:
    #         emp = self.env['hr.employee'].search([('user_id', '=', res.user_id.id)], limit=1)
    #         if emp:
    #             res.x_hr_address = emp.work_location
    #             res.x_hr_phone = emp.work_phone
    #     return res