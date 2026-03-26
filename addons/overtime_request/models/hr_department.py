# -*- coding: utf-8 -*-
from odoo import fields, models


class HrDepartment(models.Model):
    _inherit = "hr.department"

    overtime_manager_user_id = fields.Many2one(
        "res.users",
        string="Trưởng phòng duyệt tăng ca",
        help="User chịu trách nhiệm duyệt phiếu tăng ca của phòng ban này.",
    )