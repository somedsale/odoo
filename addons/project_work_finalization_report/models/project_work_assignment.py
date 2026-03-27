# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectWorkAssignment(models.Model):
    _inherit = "project.work.assignment"

    finalization_line_ids = fields.One2many(
        "project.work.finalization",
        "assignment_id",
        string="Lịch sử thanh/quyết toán",
    )