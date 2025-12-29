# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class DocumentShareWizard(models.TransientModel):
    _name = "document.share.wizard"
    _description = "Share Wizard"

    share_type = fields.Selection([("folder","Folder"),("document","Document")], required=True)
    folder_id = fields.Many2one("document.folder")
    document_id = fields.Many2one("document.document")

    allow_download = fields.Boolean(default=True)
    expiration_date = fields.Datetime()

    share_url = fields.Char(readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        st = self.env.context.get("default_share_type")
        if st:
            res["share_type"] = st
        if self.env.context.get("default_folder_id"):
            res["folder_id"] = self.env.context["default_folder_id"]
        if self.env.context.get("default_document_id"):
            res["document_id"] = self.env.context["default_document_id"]
        return res

    def action_generate(self):
        self.ensure_one()
        Share = self.env["document.share"].sudo()

        domain = [("active","=",True), ("share_type","=",self.share_type)]
        if self.share_type == "folder":
            domain.append(("folder_id","=", self.folder_id.id))
        else:
            domain.append(("document_id","=", self.document_id.id))

        share = Share.search(domain, limit=1)
        vals = {
            "allow_download": self.allow_download,
            "expiration_date": self.expiration_date,
        }
        if not share:
            vals.update({
                "share_type": self.share_type,
                "folder_id": self.folder_id.id if self.share_type == "folder" else False,
                "document_id": self.document_id.id if self.share_type == "document" else False,
                "name": "Share Link",
            })
            share = Share.create(vals)
        else:
            share.write(vals)

        self.share_url = share.get_share_url()

        return {
            "type": "ir.actions.act_window",
            "res_model": "document.share.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
