from odoo import models
import math

VIETNAMESE_NUMBERS = {
    0: 'không', 1: 'một', 2: 'hai', 3: 'ba', 4: 'bốn',
    5: 'năm', 6: 'sáu', 7: 'bảy', 8: 'tám', 9: 'chín'
}

UNITS = ['', 'nghìn', 'triệu', 'tỷ']

def _read_three_digits(n):
    hundred = n // 100
    ten = (n % 100) // 10
    unit = n % 10
    words = []

    if hundred > 0:
        words.append(VIETNAMESE_NUMBERS[hundred] + ' trăm')
    elif ten > 0 or unit > 0:
        words.append('không trăm')

    if ten > 1:
        words.append(VIETNAMESE_NUMBERS[ten] + ' mươi')
        if unit == 1:
            words.append('mốt')
        elif unit == 5:
            words.append('lăm')
        elif unit > 0:
            words.append(VIETNAMESE_NUMBERS[unit])
    elif ten == 1:
        words.append('mười')
        if unit == 5:
            words.append('lăm')
        elif unit > 0:
            words.append(VIETNAMESE_NUMBERS[unit])
    elif unit > 0:
        words.append('lẻ ' + VIETNAMESE_NUMBERS[unit])

    return ' '.join(words)

def convert_number_to_text_vi(number):
    if number == 0:
        return 'Không đồng'

    if number < 0:
        return 'Âm ' + convert_number_to_text_vi(-number)

    words = []
    unit_idx = 0

    while number > 0:
        n = number % 1000
        if n != 0:
            prefix = _read_three_digits(n)
            suffix = UNITS[unit_idx]
            if suffix:
                words.insert(0, prefix + ' ' + suffix)
            else:
                words.insert(0, prefix)
        else:
            if unit_idx == 3 and any(words):  # Có "tỷ" dù hàng này là 000
                words.insert(0, UNITS[unit_idx])
        number //= 1000
        unit_idx += 1

    final_text = ' '.join(words).strip()
    final_text = final_text[0].upper() + final_text[1:] + ' đồng'
    return final_text

class ResCurrency(models.Model):
    _inherit = 'res.currency'

    def amount_to_text_vi(self, amount):
        # Convert float to int for simplification (optional)
        amount = int(amount)
        text = convert_number_to_text_vi(amount)
        return text.capitalize()