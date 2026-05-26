# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountPaymentRequest(models.Model):
    _inherit = "account.payment.request"

    expense_bucket_id = fields.Many2one(
        "account.payment.request.expense.bucket",
        string="Khoản mục báo cáo",
        index=True,
        tracking=True,
        domain="[('active', '=', True)]",
    )

    expense_bucket_section = fields.Selection(
        related="expense_bucket_id.section",
        string="Nhóm khoản mục báo cáo",
        store=True,
        readonly=True,
    )

    # Field cũ: giữ để tương thích dữ liệu/report cũ, nhưng ẩn trên giao diện
    expense_bucket = fields.Selection(
        [
            ("rent_office_factory", "Chi phí thuê văn phòng + xưởng"),

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
        ],
        string="Khoản mục báo cáo cũ",
        index=True,
        copy=False,
    )

    # =========================================================
    # HELPER
    # =========================================================
    def _get_bucket_by_code(self, code):
        if not code:
            return False

        return self.env["account.payment.request.expense.bucket"].search([
            ("code", "=", code),
        ], limit=1)

    def _sync_expense_bucket_id_from_old_code(self):
        """
        Đồng bộ từ field cũ expense_bucket sang field mới expense_bucket_id.
        Dùng cho dữ liệu cũ hoặc trường hợp import còn dùng code cũ.
        """
        Bucket = self.env["account.payment.request.expense.bucket"]

        for rec in self:
            if rec.expense_bucket and not rec.expense_bucket_id:
                bucket = Bucket.search([
                    ("code", "=", rec.expense_bucket),
                ], limit=1)

                if bucket:
                    rec.expense_bucket_id = bucket.id

    def _sync_old_code_from_expense_bucket_id(self):
        """
        Đồng bộ từ field mới expense_bucket_id sang field cũ expense_bucket.
        Dùng để report cũ hoặc domain fallback vẫn chạy được.
        """
        for rec in self:
            if rec.expense_bucket_id:
                rec.expense_bucket = rec.expense_bucket_id.code
            else:
                rec.expense_bucket = False

    # =========================================================
    # ONCHANGE
    # =========================================================
    @api.onchange("expense_bucket_id")
    def _onchange_expense_bucket_id(self):
        for rec in self:
            if rec.expense_bucket_id:
                rec.expense_bucket = rec.expense_bucket_id.code
            else:
                rec.expense_bucket = False

    @api.onchange("expense_bucket")
    def _onchange_expense_bucket(self):
        """
        Phòng trường hợp dữ liệu cũ/import chỉnh field cũ.
        Bình thường field cũ đã ẩn nên user không thấy.
        """
        for rec in self:
            if rec.expense_bucket and not rec.expense_bucket_id:
                bucket = rec._get_bucket_by_code(rec.expense_bucket)
                if bucket:
                    rec.expense_bucket_id = bucket.id

    # =========================================================
    # CREATE / WRITE
    # =========================================================
    @api.model_create_multi
    def create(self, vals_list):
        Bucket = self.env["account.payment.request.expense.bucket"]

        for vals in vals_list:
            # Nếu chọn field mới thì tự ghi code cũ
            if vals.get("expense_bucket_id"):
                bucket = Bucket.browse(vals["expense_bucket_id"])
                vals["expense_bucket"] = bucket.code or False

            # Nếu import/dữ liệu ngoài chỉ truyền field cũ thì tự map sang field mới
            elif vals.get("expense_bucket"):
                bucket = Bucket.search([
                    ("code", "=", vals["expense_bucket"]),
                ], limit=1)

                if bucket:
                    vals["expense_bucket_id"] = bucket.id

        return super().create(vals_list)

    def write(self, vals):
        Bucket = self.env["account.payment.request.expense.bucket"]

        # Nếu sửa field mới
        if "expense_bucket_id" in vals:
            if vals.get("expense_bucket_id"):
                bucket = Bucket.browse(vals["expense_bucket_id"])
                vals["expense_bucket"] = bucket.code or False
            else:
                vals["expense_bucket"] = False

        # Nếu import hoặc code khác sửa field cũ
        elif "expense_bucket" in vals:
            if vals.get("expense_bucket"):
                bucket = Bucket.search([
                    ("code", "=", vals["expense_bucket"]),
                ], limit=1)

                if bucket:
                    vals["expense_bucket_id"] = bucket.id
                else:
                    vals["expense_bucket_id"] = False
            else:
                vals["expense_bucket_id"] = False

        return super().write(vals)