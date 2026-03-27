# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectWorkAssignment(models.Model):
    _inherit = "project.work.assignment"

    acceptance_line_ids = fields.One2many(
        "project.work.acceptance",
        "assignment_id",
        string="Lịch sử nghiệm thu",
    )