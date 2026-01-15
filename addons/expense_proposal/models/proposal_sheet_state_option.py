# -*- coding: utf-8 -*-
from odoo import fields, models

class ProposalSheetStateOption(models.Model):
    _name = "proposal.sheet.state.option"
    _description = "Proposal Sheet State Option"
    _order = "sequence, id"

    key = fields.Char(required=True, index=True)   # ví dụ: reviewed_manager
    name = fields.Char(required=True)              # label hiển thị
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("key_uniq", "unique(key)", "State key phải là duy nhất!"),
    ]
