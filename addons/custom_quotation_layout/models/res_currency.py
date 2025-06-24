from odoo import models

VIETNAMESE_NUMBERS = {
    0: 'không', 1: 'một', 2: 'hai', 3: 'ba', 4: 'bốn',
    5: 'năm', 6: 'sáu', 7: 'bảy', 8: 'tám', 9: 'chín'
}

def convert_number_to_text_vi(n):
    # Bạn có thể dùng thư viện ngoài hoặc viết thủ công
    # Ở đây chỉ demo đơn giản cho bạn cách tích hợp
    return "Một trăm năm mươi chín triệu bảy trăm hai mươi nghìn đồng" 

class ResCurrency(models.Model):
    _inherit = 'res.currency'

    def amount_to_text_vi(self, amount):
        # Convert float to int for simplification (optional)
        amount = int(amount)
        text = convert_number_to_text_vi(amount)
        return text.capitalize()