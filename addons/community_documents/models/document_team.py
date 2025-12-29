# -*- coding: utf-8 -*-
from odoo import fields, models


class DocumentTeam(models.Model):
    _name = "document.team"
    _description = "Document Team"
    _order = "name"

    name = fields.Char(required=True)
    leader_id = fields.Many2one("res.users", string="Leader", required=True, default=lambda self: self.env.user)
    member_ids = fields.Many2many("res.users", "document_team_user_rel", "team_id", "user_id", string="Members")
    description = fields.Text()
