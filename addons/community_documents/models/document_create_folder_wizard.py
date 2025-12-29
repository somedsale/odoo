# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class DocumentCreateFolderWizard(models.TransientModel):
    _name = "document.create.folder.wizard"
    _description = "Create Folder"

    name = fields.Char(required=True)
    parent_id = fields.Many2one("document.folder")
    access_level = fields.Selection(
        [("internal", "Internal"), ("shared", "Shared")],
        default="internal",
        required=True,
    )

    # --- 3 model trung gian ---
    readable_line_ids = fields.One2many("doc.create.folder.wiz.readable", "wizard_id")
    writable_line_ids = fields.One2many("doc.create.folder.wiz.writable", "wizard_id")
    ownonly_line_ids = fields.One2many("doc.create.folder.wiz.ownonly", "wizard_id")

    # --- 3 field tags (computed + inverse, store=False => không tạo bảng relation) ---
    readable_user_ids = fields.Many2many(
        "res.users",
        string="Readable Users",
        compute="_compute_user_sets",
        inverse="_inverse_readable_user_ids",
        store=False,
    )
    writable_user_ids = fields.Many2many(
        "res.users",
        string="Writable Users",
        compute="_compute_user_sets",
        inverse="_inverse_writable_user_ids",
        store=False,
    )
    own_document_only_user_ids = fields.Many2many(
        "res.users",
        string="Users Own Document Only",
        compute="_compute_user_sets",
        inverse="_inverse_ownonly_user_ids",
        store=False,
    )

    @api.depends("readable_line_ids.user_id", "writable_line_ids.user_id", "ownonly_line_ids.user_id")
    def _compute_user_sets(self):
        for w in self:
            w.readable_user_ids = w.readable_line_ids.mapped("user_id")
            w.writable_user_ids = w.writable_line_ids.mapped("user_id")
            w.own_document_only_user_ids = w.ownonly_line_ids.mapped("user_id")

    # ---------- helpers sync line models ----------
    def _sync_lines(self, line_model, line_field_name, new_user_ids):
        """
        line_model: env['doc.create.folder.wiz.readable'] ...
        line_field_name: 'readable_line_ids' ...
        new_user_ids: recordset res.users
        """
        self.ensure_one()
        existing_lines = getattr(self, line_field_name)
        existing_ids = set(existing_lines.mapped("user_id").ids)
        desired_ids = set(new_user_ids.ids)

        # add
        to_add = desired_ids - existing_ids
        if to_add:
            line_model.create([{"wizard_id": self.id, "user_id": uid} for uid in to_add])

        # remove
        to_remove = existing_ids - desired_ids
        if to_remove:
            existing_lines.filtered(lambda l: l.user_id.id in to_remove).unlink()

    def _inverse_readable_user_ids(self):
        for w in self:
            w._sync_lines(self.env["doc.create.folder.wiz.readable"], "readable_line_ids", w.readable_user_ids)

    def _inverse_writable_user_ids(self):
        for w in self:
            w._sync_lines(self.env["doc.create.folder.wiz.writable"], "writable_line_ids", w.writable_user_ids)

    def _inverse_ownonly_user_ids(self):
        for w in self:
            w._sync_lines(self.env["doc.create.folder.wiz.ownonly"], "ownonly_line_ids", w.own_document_only_user_ids)

    def action_create_folder(self):
        self.ensure_one()
        folder = self.env["document.folder"].create({
            "name": (self.name or "").strip(),
            "parent_id": self.parent_id.id if self.parent_id else False,
            "access_level": self.access_level,
            "owner_id": self.env.user.id,
        })

        if self.access_level == "shared":
            read_set = set(self.readable_user_ids.ids)
            write_set = set(self.writable_user_ids.ids)
            own_set = set(self.own_document_only_user_ids.ids)

            # writable => luôn readable
            read_set |= write_set
            all_users = read_set | write_set | own_set

            vals_list = []
            for uid in all_users:
                vals_list.append({
                    "folder_id": folder.id,
                    "user_id": uid,
                    "role": "editor" if uid in write_set else "viewer",
                    "own_only": uid in own_set,
                })
            if vals_list:
                self.env["document.folder.member"].create(vals_list)

        return {"type": "ir.actions.act_window_close"}

class DocCreateFolderWizReadable(models.TransientModel):
    _name = "doc.create.folder.wiz.readable"
    _description = "Create Folder Wizard - Readable Users"

    wizard_id = fields.Many2one("document.create.folder.wizard", required=True, ondelete="cascade")
    user_id = fields.Many2one("res.users", required=True)


class DocCreateFolderWizWritable(models.TransientModel):
    _name = "doc.create.folder.wiz.writable"
    _description = "Create Folder Wizard - Writable Users"

    wizard_id = fields.Many2one("document.create.folder.wizard", required=True, ondelete="cascade")
    user_id = fields.Many2one("res.users", required=True)


class DocCreateFolderWizOwnOnly(models.TransientModel):
    _name = "doc.create.folder.wiz.ownonly"
    _description = "Create Folder Wizard - Own Documents Only Users"

    wizard_id = fields.Many2one("document.create.folder.wizard", required=True, ondelete="cascade")
    user_id = fields.Many2one("res.users", required=True)