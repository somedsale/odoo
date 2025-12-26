# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DocumentAddLinkWizard(models.TransientModel):
    _name = "document.add.link.wizard"
    _description = "Add a Link to Documents"

    name = fields.Char(string="Name")
    url = fields.Char(string="URL", required=True)
    folder_id = fields.Many2one("document.folder", string="Folder")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # default folder from context
        if self.env.context.get("default_folder_id"):
            res["folder_id"] = self.env.context["default_folder_id"]
        return res

    def action_add_link(self):
        self.ensure_one()
        if not self.url:
            raise UserError(_("Please enter a URL."))

        # name fallback = url
        name = self.name or self.url

        vals = {
            "name": name,
            "url": self.url,
        }
        if self.folder_id:
            vals["folder_id"] = self.folder_id.id

        self.env["document.document"].create(vals)

        # close dialog
        return {"type": "ir.actions.act_window_close"}
