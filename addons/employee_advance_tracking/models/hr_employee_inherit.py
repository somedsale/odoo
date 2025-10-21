# -*- coding: utf-8 -*-
from odoo import models, api


class HREmployee(models.Model):
    _inherit = "hr.employee"

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        self.env["account.employee.advance"].sudo().create({
            "employee_id": rec.id
        })
        return rec
