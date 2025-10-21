# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountEmployeeAdvance(models.Model):
    _name = "account.employee.advance"
    _description = "Theo dõi tạm ứng nhân viên"
    _rec_name = "employee_id"
    _order = "department_id, employee_id"

    # ====== THÔNG TIN CHÍNH ======
    employee_id = fields.Many2one(
        "hr.employee",
        string="Nhân viên",
        required=True,
        ondelete="cascade",
    )
    department_id = fields.Many2one(
        "hr.department",
        string="Phòng ban",
        related="employee_id.department_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Tiền tệ",
        default=lambda self: self.env.company.currency_id,
    )

    # ====== LIÊN KẾT PHIẾU CHI / PHIẾU THU ======
    payment_ids = fields.One2many(
        "account.payment.request",
        "employee_advance_id",
        string="Phiếu chi tạm ứng",
        domain=[("is_advance", "=", True)],
    )
    receipt_ids = fields.One2many(
        "account.receipt",
        "employee_advance_id",
        string="Phiếu thu hoàn tạm ứng",
        domain=[("is_advance_refund", "=", True)],
    )

    # ====== SỐ LIỆU THEO DÕI ======
    advance_total = fields.Monetary(
        string="Tổng tiền tạm ứng",
        currency_field="currency_id",
        compute="_compute_advance_total",
        store=True,
        help="Tổng số tiền nhân viên đã được tạm ứng.",
    )
    refund_total = fields.Monetary(
        string="Tổng tiền hoàn ứng",
        currency_field="currency_id",
        compute="_compute_refund_total",
        store=True,
        help="Tổng số tiền nhân viên đã hoàn lại.",
    )
    remain_total = fields.Monetary(
        string="Còn lại",
        currency_field="currency_id",
        compute="_compute_remain_total",
        store=True,
        help="Số tiền nhân viên còn phải hoàn lại.",
    )

    # ====== TÍNH TOÁN ======
    @api.depends("advance_total", "refund_total")
    def _compute_remain_total(self):
        for rec in self:
            rec.remain_total = rec.advance_total - rec.refund_total

    @api.depends("payment_ids.total", "payment_ids.state", "payment_ids.is_advance")
    def _compute_advance_total(self):
        for rec in self:
            valid_payments = rec.payment_ids.filtered(
                lambda p: p.is_advance and p.state in ["approved", "paid", "done", "posted"]
            )
            rec.advance_total = sum(valid_payments.mapped("total"))

    @api.depends("receipt_ids.amount", "receipt_ids.state", "receipt_ids.is_advance_refund")
    def _compute_refund_total(self):
        for rec in self:
            valid_receipts = rec.receipt_ids.filtered(
                lambda r: r.is_advance_refund and r.state in ["posted", "done", "paid", "confirmed"]
            )
            rec.refund_total = sum(valid_receipts.mapped("amount"))

    # ====== RÀNG BUỘC ======
    _sql_constraints = [
        ("employee_unique", "unique(employee_id)", "Mỗi nhân viên chỉ có một dòng theo dõi tạm ứng."),
    ]

    # ====== KHỞI TẠO DỮ LIỆU ======
    @api.model
    def init(self):
        """Tự động tạo dòng theo dõi cho tất cả nhân viên chưa có"""
        employees = self.env["hr.employee"].search([("id", "!=", 1)])
        for emp in employees:
            if not self.search([("employee_id", "=", emp.id)], limit=1):
                self.create({"employee_id": emp.id})