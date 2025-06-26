from odoo import models, fields, api

class ResCurrency(models.Model):
    _inherit = 'res.currency'

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