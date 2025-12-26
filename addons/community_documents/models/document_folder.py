# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class DocumentFolder(models.Model):
    _name = "document.folder"
    _description = "Document Folder"
    _order = "name"

    name = fields.Char(required=True)
    parent_id = fields.Many2one("document.folder", ondelete="set null")
    owner_id = fields.Many2one("res.users", default=lambda self: self.env.user, required=True)

    access_level = fields.Selection(
        [
            ("internal", "Internal"),
            ("shared", "Shared"),
            ("private", "Private"),
        ],
        default="internal",
        required=True,
    )
    member_ids = fields.One2many(
        "document.folder.member", "folder_id", string="Shared With"
    )

    allowed_user_ids = fields.Many2many(
        "res.users",
        "document_folder_allowed_user_rel",
        "folder_id",
        "user_id",
        string="Allowed Users",
    )
    readable_user_ids = fields.Many2many(
        "res.users",
        string="Readable Users",
        compute="_compute_share_users",
        inverse="_inverse_share_users",
    )
    writable_user_ids = fields.Many2many(
        "res.users",
        string="Writable Users",
        compute="_compute_share_users",
        inverse="_inverse_share_users",
    )
    own_document_only_user_ids = fields.Many2many(
        "res.users",
        string="Users Own Document Only",
        compute="_compute_share_users",
        inverse="_inverse_share_users",
    )
    document_ids = fields.One2many("document.document", "folder_id")
    document_count = fields.Integer(compute="_compute_document_count")

    def _compute_document_count(self):
        for rec in self:
            rec.document_count = len(rec.document_ids)

    def _is_manager(self):
        return self.env.user.has_group("community_documents.group_documents_manager")

    def _check_access_folder(self):
        """Hard check (backend)"""
        self.ensure_one()
        if self._is_manager():
            return True
        if self.access_level == "internal":
            return True
        if self.access_level == "shared":
            return self.owner_id.id == self.env.user.id or self.env.user in self.allowed_user_ids
        if self.access_level == "private":
            return self.owner_id.id == self.env.user.id
        return False

    def write(self, vals):
        # only manager can change owner/access settings (optional)
        if any(k in vals for k in ("owner_id", "access_level", "allowed_user_ids")) and not self._is_manager():
            # owner can still change allowed_user_ids if shared? tùy bạn, mình khóa cho chắc
            raise AccessError(_("You are not allowed to change folder permissions."))
        return super().write(vals)
    @api.depends("member_ids.user_id", "member_ids.role", "member_ids.own_only")
    def _compute_share_users(self):
        for folder in self:
            members = folder.member_ids
            folder.readable_user_ids = members.filtered(lambda m: m.role in ("viewer", "editor")).mapped("user_id")
            folder.writable_user_ids = members.filtered(lambda m: m.role == "editor").mapped("user_id")
            folder.own_document_only_user_ids = members.filtered(lambda m: m.own_only).mapped("user_id")

    def _inverse_share_users(self):
        Member = self.env["document.folder.member"]
        for folder in self:
            read_set = set(folder.readable_user_ids.ids)
            write_set = set(folder.writable_user_ids.ids)
            own_set = set(folder.own_document_only_user_ids.ids)

            # Writable => luôn phải readable
            read_set |= write_set

            all_users = read_set | write_set | own_set

            existing = {m.user_id.id: m for m in folder.member_ids}

            # update / create
            for uid in all_users:
                role = "editor" if uid in write_set else "viewer"
                own_only = uid in own_set

                if uid in existing:
                    existing[uid].write({"role": role, "own_only": own_only})
                else:
                    Member.create({
                        "folder_id": folder.id,
                        "user_id": uid,
                        "role": role,
                        "own_only": own_only,
                    })

            # remove members not in any set
            to_remove = [m.id for u, m in existing.items() if u not in all_users]
            if to_remove:
                Member.browse(to_remove).unlink()