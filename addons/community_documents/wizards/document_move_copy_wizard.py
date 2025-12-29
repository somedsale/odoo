# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DocumentMoveCopyWizard(models.TransientModel):
    _name = "document.move.copy.wizard"
    _description = "Move/Copy Documents Wizard"

    operation = fields.Selection(
        [("move", "Move"), ("copy", "Copy")],
        required=True,
        default="move",
    )
    folder_id = fields.Many2one("document.folder", string="Target Folder", required=True)
    document_ids = fields.Many2many("document.document", string="Documents", required=True)

    def action_apply(self):
        self.ensure_one()
        docs = self.document_ids
        if not docs:
            raise UserError(_("Bạn chưa chọn file nào."))

        if self.operation == "move":
            docs.write({"folder_id": self.folder_id.id})
            return {"type": "ir.actions.act_window_close"}

        # COPY
        Document = self.env["document.document"].sudo()
        Attachment = self.env["ir.attachment"].sudo()

        for d in docs:
            # tạo doc mới
            new_vals = {
                "name": d.name,
                "folder_id": self.folder_id.id,
                "mimetype": d.mimetype,
                "tag_ids": [(6, 0, d.tag_ids.ids)] if hasattr(d, "tag_ids") else False,
                "is_link": getattr(d, "is_link", False),
            }

            # nếu doc là link: copy link fields nếu có
            if getattr(d, "is_link", False):
                for k in ("url", "link_url", "url_link"):
                    if k in d._fields:
                        new_vals[k] = d[k]
                        break

            new_doc = Document.create(new_vals)

            # copy attachment nếu có
            att = getattr(d, "attachment_id", False)
            if att:
                att = att.exists()
            if att and att.id:
                # copy binary attachment -> gắn sang doc mới
                new_att = att.copy({
                    "res_model": "document.document",
                    "res_id": new_doc.id,
                    "name": att.name or new_doc.name,
                })
                new_doc.write({"attachment_id": new_att.id})

        return {"type": "ir.actions.act_window_close"}
