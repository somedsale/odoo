# -*- coding: utf-8 -*-
import mimetypes

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class DocumentDocument(models.Model):
    _name = "document.document"
    _description = "Document"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "write_date desc, id desc"

    # -----------------------------
    # Fields
    # -----------------------------
    active = fields.Boolean(default=True)

    name = fields.Char(required=True, tracking=True)

    folder_id = fields.Many2one(
        "document.folder",
        string="Folder",
        required=True,
        index=True,
        tracking=True,
        default=lambda self: self._default_folder_id(),
    )

    owner_id = fields.Many2one(
        "res.users",
        string="Owner",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )

    partner_id = fields.Many2one("res.partner", string="Related Contact", tracking=True)

    tag_ids = fields.Many2many(
        "document.tag",
        "document_document_tag_rel",
        "document_id",
        "tag_id",
        string="Tags",
        tracking=True,
    )

    # Link to ir.attachment (binary or url)
    attachment_id = fields.Many2one(
        "ir.attachment",
        string="Attachment",
        ondelete="set null",
        index=True,
    )

    # Upload helper fields (JS/UI sends these)
    datas = fields.Binary(string="File")
    datas_filename = fields.Char(string="Filename")

    # Link mode
    is_link = fields.Boolean(string="Is a Link", default=False)
    url = fields.Char(string="URL")

    # Info
    mimetype = fields.Char(string="Mime Type", compute="_compute_attachment_info", store=True, readonly=True)
    file_size = fields.Integer(string="File Size", compute="_compute_attachment_info", store=True, readonly=True)
    download_url = fields.Char(string="Download Url", compute="_compute_download_url", readonly=True)

    note = fields.Text(string="Note")

    # -----------------------------
    # Defaults / helpers
    # -----------------------------
    @api.model
    def _default_folder_id(self):
        """Default folder = community_documents.folder_general, else first folder, else False."""
        folder = self.env.ref("community_documents.folder_general", raise_if_not_found=False)
        if folder:
            return folder.id
        folder = self.env["document.folder"].search([], limit=1)
        return folder.id if folder else False

    def _is_manager(self):
        return self.env.user.has_group("community_documents.group_documents_manager")

    def _check_folder_access(self, folder):
        """Hard permission check for folder (backend)."""
        folder.ensure_one()
        if self._is_manager():
            return True

        # Expect document.folder has: access_level, owner_id, allowed_user_ids
        access = folder.access_level or "internal"
        if access == "internal":
            return True
        if access == "shared":
            return folder.owner_id.id == self.env.user.id or self.env.user in folder.allowed_user_ids
        if access == "private":
            return folder.owner_id.id == self.env.user.id
        return False

    def _guess_mimetype(self, filename):
        return mimetypes.guess_type(filename or "")[0] or "application/octet-stream"

    # -----------------------------
    # Computes
    # -----------------------------
    @api.depends("attachment_id", "attachment_id.mimetype", "attachment_id.file_size")
    def _compute_attachment_info(self):
        for rec in self:
            att = rec.attachment_id
            rec.mimetype = att.mimetype if att else False
            rec.file_size = att.file_size if att else 0

    def _compute_download_url(self):
        for rec in self:
            if rec.attachment_id:
                rec.download_url = f"/web/content/{rec.attachment_id.id}?download=true"
            else:
                rec.download_url = False

    # -----------------------------
    # Core: create / write / unlink
    # -----------------------------
    @api.model_create_multi
    def create(self, vals_list):
        Folder = self.env["document.folder"]
        Attachment = self.env["ir.attachment"]

        # Resolve default folder once
        default_folder = self.env.ref("community_documents.folder_general", raise_if_not_found=False)
        if not default_folder:
            default_folder = Folder.search([], limit=1)

        prepared_vals = []
        created_attachments = []  # parallel list: attachment created for each item (or None)

        for vals in vals_list:
            vals = dict(vals or {})

            # ---- Ensure folder_id (required) ----
            if not vals.get("folder_id"):
                if default_folder:
                    vals["folder_id"] = default_folder.id
                else:
                    raise UserError(_("No default folder found. Please create a folder first."))

            folder = Folder.browse(vals["folder_id"])
            if folder.exists() and not self._check_folder_access(folder):
                raise AccessError(_("You don't have access to this folder."))

            # ---- Ensure owner ----
            if not vals.get("owner_id"):
                vals["owner_id"] = self.env.user.id

            # ---- Ensure name (required) BEFORE super ----
            # Priority: datas_filename > provided name > url > "Document"
            if vals.get("datas_filename"):
                vals["name"] = vals.get("datas_filename")
            elif not vals.get("name"):
                vals["name"] = vals.get("url") or _("Document")

            # ---- Create attachment if needed ----
            attachment = None

            # Case A: upload file via datas (base64)
            if vals.get("datas") and not vals.get("attachment_id"):
                filename = vals.get("datas_filename") or vals.get("name") or _("Document")
                attachment = Attachment.create({
                    "name": filename,
                    "type": "binary",
                    "datas": vals["datas"],
                    "mimetype": self._guess_mimetype(filename),
                    "res_model": self._name,  # res_id set after doc created
                })
                vals["attachment_id"] = attachment.id
                vals["is_link"] = False
                vals.pop("datas", None)
                vals.pop("datas_filename", None)

            # Case B: add link via url (create url attachment)
            elif vals.get("url") and not vals.get("attachment_id"):
                name = vals.get("name") or vals["url"]
                attachment = Attachment.create({
                    "name": name,
                    "type": "url",
                    "url": vals["url"],
                    "res_model": self._name,
                })
                vals["attachment_id"] = attachment.id
                vals["is_link"] = True

            prepared_vals.append(vals)
            created_attachments.append(attachment)

        records = super().create(prepared_vals)

        # Link attachments to created records
        for rec, att in zip(records, created_attachments):
            if att:
                att.write({"res_id": rec.id, "res_model": rec._name})
            else:
                # If attachment_id provided externally, ensure linkage
                if rec.attachment_id and (rec.attachment_id.res_id != rec.id or rec.attachment_id.res_model != rec._name):
                    rec.attachment_id.write({"res_id": rec.id, "res_model": rec._name})

        return records

    def write(self, vals):
        Folder = self.env["document.folder"]
        Attachment = self.env["ir.attachment"]

        vals = dict(vals or {})

        # Folder change permission
        if vals.get("folder_id"):
            folder = Folder.browse(vals["folder_id"])
            if folder.exists() and not self._check_folder_access(folder):
                raise AccessError(_("You don't have access to this folder."))

        # If replacing file via datas
        if vals.get("datas"):
            filename = vals.get("datas_filename") or vals.get("name") or self.name or _("Document")
            att = Attachment.create({
                "name": filename,
                "type": "binary",
                "datas": vals["datas"],
                "mimetype": self._guess_mimetype(filename),
                "res_model": self._name,
                "res_id": self.id if len(self) == 1 else 0,  # if multi, we relink below
            })
            vals["attachment_id"] = att.id
            vals["is_link"] = False

            # Auto-name from filename
            if vals.get("datas_filename"):
                vals["name"] = vals["datas_filename"]

            vals.pop("datas", None)
            vals.pop("datas_filename", None)

        # If replacing link via url
        if vals.get("url"):
            # If they set url, we consider link mode
            name = vals.get("name") or self.name or vals["url"]
            att = Attachment.create({
                "name": name,
                "type": "url",
                "url": vals["url"],
                "res_model": self._name,
                "res_id": self.id if len(self) == 1 else 0,
            })
            vals["attachment_id"] = att.id
            vals["is_link"] = True

            # If no explicit name provided, keep current or url
            if not vals.get("name"):
                vals["name"] = name

        res = super().write(vals)

        # If multi-record write created attachments with res_id=0, relink them properly
        # (best effort: when multi, create one attachment per record is ambiguous; so we avoid multi file replace)
        # We'll just ensure existing attachment points to the record for each record.
        for rec in self:
            if rec.attachment_id and (rec.attachment_id.res_id != rec.id or rec.attachment_id.res_model != rec._name):
                rec.attachment_id.write({"res_id": rec.id, "res_model": rec._name})

        return res

    def unlink(self):
        # Optionally delete attachments that belong only to this record
        attachments = self.mapped("attachment_id").filtered(lambda a: a.res_model == self._name)
        res = super().unlink()

        # Delete orphan attachments linked to deleted docs
        # Only delete those that pointed to this model and have no res_id anymore or were pointing to deleted record.
        if attachments:
            # safest: delete only those still pointing to deleted ids (res_id in old ids)
            # We don't have old ids after super, so use sudo search by res_model and res_id not existing.
            # Keep it simple: only delete attachments with res_id=0 (rare) - or keep attachments.
            # -> For safety, we won't force delete here unless you want.
            pass

        return res
