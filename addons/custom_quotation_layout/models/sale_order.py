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
            date = datetime.now()
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
    def number_to_text(self, number):
        """
        Chuyển đổi số thành chữ tiếng Việt.
        :param number: Số cần chuyển đổi (integer hoặc float)
        :return: Chuỗi chữ tiếng Việt
        """
        def convert_less_than_one_thousand(number):
            units = ["", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
            teens = ["mười", "mười một", "mười hai", "mười ba", "mười bốn", "mười lăm", 
                     "mười sáu", "mười bảy", "mười tám", "mười chín"]
            tens = ["", "", "hai mươi", "ba mươi", "bốn mươi", "năm mươi", 
                    "sáu mươi", "bảy mươi", "tám mươi", "chín mươi"]

            result = ""
            if number >= 100:
                result += units[number // 100] + " trăm"
                number %= 100
                if number > 0:
                    result += " "
            if number >= 20:
                result += tens[number // 10]
                number %= 10
                if number > 0:
                    result += " " + units[number]
            elif number >= 10:
                result += teens[number - 10]
            else:
                result += units[number]
            return result.strip()

        if not number:
            return "Không đồng"

        units = ["", "nghìn", "triệu", "tỷ"]
        result = []
        i = 0
        number = int(number)

        while number > 0:
            part = number % 1000
            if part > 0:
                text = convert_less_than_one_thousand(part)
                if i > 0:
                    text += " " + units[i]
                result.insert(0, text)
            number //= 1000
            i += 1

        final_result = " ".join(result).strip()
        final_result = final_result[0].upper() + final_result[1:] + " đồng"
        return final_result