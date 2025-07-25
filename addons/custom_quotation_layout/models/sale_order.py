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
    def amount_to_text_vi(self,number):
        number = int(round(number))

        units = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ"]
        num_text = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]

        def read_three_digits(number, show_zero_hundred):
            hundred = number // 100
            ten = (number % 100) // 10
            unit = number % 10
            words = ""

            if hundred != 0:
                words += num_text[hundred] + " trăm"
            elif show_zero_hundred:
                words += "không trăm"

            if ten == 0:
                if unit != 0:
                    if hundred != 0:
                        words += " linh " + num_text[unit]
                    else:
                        words += num_text[unit]
            elif ten == 1:
                words += " mười"
                if unit == 1:
                    words += " một"
                elif unit == 5:
                    words += " lăm"
                elif unit != 0:
                    words += " " + num_text[unit]
            else:
                words += " " + num_text[ten] + " mươi"
                if unit == 1:
                    words += " mốt"
                elif unit == 5:
                    words += " lăm"
                elif unit != 0:
                    words += " " + num_text[unit]

            return words.strip()

        def split_number(number):
            parts = []
            while number > 0:
                parts.insert(0, number % 1000)
                number //= 1000
            return parts

        if number == 0:
            return "Không đồng"

        parts = split_number(number)
        word_parts = []
        for i in range(len(parts)):
            n = parts[i]
            if n != 0:
                show_zero_hundred = (i != 0 and parts[i] < 100)
                words = read_three_digits(n, show_zero_hundred)
                unit = units[len(parts) - i - 1]
                word_parts.append(words + (" " + unit if unit else ""))

        final = " ".join(word_parts).strip().capitalize() + " đồng"
        return final

    def int_to_roman(seft,num):
        if not isinstance(num, int) or num < 1:
            return ""
        val = [
            (1000, "M"),
            (900, "CM"),
            (500, "D"),
            (400, "CD"),
            (100, "C"),
            (90, "XC"),
            (50, "L"),
            (40, "XL"),
            (10, "X"),
            (9, "IX"),
            (5, "V"),
            (4, "IV"),
            (1, "I")
        ]
        result = ""
        for (arabic, roman) in val:
            while num >= arabic:
                result += roman
                num -= arabic
        return result