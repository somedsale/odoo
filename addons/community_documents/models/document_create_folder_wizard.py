# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DocumentCreateFolderWizard(models.TransientModel):
    _name = "document.create.folder.wizard"
    _description = "Create Folder Wizard"

    name = fields.Char(required=True)
    parent_id = fields.Many2one("document.folder")

    access_mode = fields.Selection(
        [("private", "Chỉ mình tôi"),
         ("restricted", "Chỉ định người truy cập (Nội bộ)")],
        required=True,
        default="private",
    )

    allowed_user_ids = fields.Many2many(
        "res.users",
        "doc_create_folder_wiz_allowed_rel",
        "wiz_id",
        "user_id",
        string="Người được truy cập",
        domain=[("share", "=", False)],
    )

    def action_create(self):
        self.ensure_one()
        vals = {
            "name": self.name,
            "parent_id": self.parent_id.id if self.parent_id else False,
            "owner_id": self.env.user.id,
            "access_mode": self.access_mode,
            "allowed_user_ids": [(6, 0, self.allowed_user_ids.ids)] if self.access_mode == "restricted" else [(6, 0, [])],
        }
        return self.env["document.folder"].create(vals)
