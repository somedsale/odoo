# -*- coding: utf-8 -*-
from odoo import fields, models


class DocumentFolderMember(models.Model):
    _name = "document.folder.member"
    _description = "Folder Member"
    _order = "id desc"

    folder_id = fields.Many2one("document.folder", required=True, ondelete="cascade", index=True)
    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)

    role = fields.Selection(
        [("viewer", "Viewer"), ("editor", "Editor")],
        default="viewer",
        required=True,
    )

    own_only = fields.Boolean(string="Own Documents Only", default=False)

    _sql_constraints = [
        ("uniq_folder_user", "unique(folder_id, user_id)", "This user is already shared in this folder."),
    ]
