from odoo import models, fields

class AccountPaymentRequest(models.Model):
    _inherit = "account.payment.request"

    expense_bucket = fields.Selection([
        # A
        ("rent_office_factory", "Chi phí thuê văn phòng + xưởng"),

        # B/a (17 mục)
        ("loan_principal", "Trả gốc vay (Ngân hàng + cá nhân)"),
        ("loan_interest", "Lãi vay (Ngân hàng, Cá nhân)"),
        ("bank_fee", "Phí ngân hàng (CK, Phí số dư, mua SEC,...)"),
        ("salary_board", "Chi phí lương ban Giám Đốc"),
        ("salary_sales", "Chi phí lương Kinh Doanh"),
        ("salary_accounting", "Chi phí lương Kế Toán"),
        ("salary_planning_tech_production", "Chi phí lương bộ phận kế hoạch kỹ thuật và sản xuất"),
        ("insurance_215", "Chi phí BHXH, BHYT, BHTN 21,5%"),
        ("electric_water", "Chi phí điện, Nước sinh hoạt"),
        ("phone_fee", "Chi phí Cước điện thoại (di động, cố định, số hotline...)"),
        ("internet_fee", "Cước Internet văn phòng"),
        ("stationery_hygiene_shipping", "Văn phòng phẩm + vật dụng vệ sinh + cước vận chuyển"),
        ("garbage_fee", "Chi phí đổ rác"),
        ("reception", "Chi phí Tiếp khách"),
        ("drinking_water", "Chi phí nước uống bình nhân viên"),
        ("badminton", "Chi phí cầu lông (đặt sân, mua cầu..)"),
        ("worship", "Chi phí cúng (mùng 1,15, ....)"),
    ], string="Khoản mục báo cáo", index=True)
