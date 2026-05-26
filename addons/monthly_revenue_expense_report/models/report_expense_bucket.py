# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AccountPaymentRequestExpenseBucket(models.Model):
    _name = "account.payment.request.expense.bucket"
    _description = "Khoản mục báo cáo chi phí"
    _order = "section, sequence, id"

    name = fields.Char(
        string="Tên khoản mục",
        required=True,
    )

    code = fields.Char(
        string="Mã khoản mục",
        required=True,
        copy=False,
    )

    section = fields.Selection(
        [
            ("fixed", "A. Tổng định phí"),
            ("company", "B/a. Chi phí công ty"),
        ],
        string="Nhóm báo cáo",
        required=True,
        default="company",
        index=True,
    )

    sequence = fields.Integer(
        string="Thứ tự",
        default=10,
    )

    active = fields.Boolean(
        string="Đang sử dụng",
        default=True,
    )

    note = fields.Text(
        string="Ghi chú",
    )

    _sql_constraints = [
        (
            "code_unique",
            "unique(code)",
            "Mã khoản mục báo cáo đã tồn tại.",
        )
    ]

    @api.depends("name", "section")
    def _compute_display_name(self):
        section_map = dict(self._fields["section"].selection)

        for rec in self:
            section_label = section_map.get(rec.section, "")
            rec.display_name = f"{section_label} / {rec.name}" if section_label else rec.name