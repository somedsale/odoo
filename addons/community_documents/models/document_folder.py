# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class DocumentFolder(models.Model):
    _name = "document.folder"
    _description = "Document Folder"
    _order = "name"

    name = fields.Char(required=True)
    parent_id = fields.Many2one("document.folder", string="Parent Folder", ondelete="restrict", index=True)
    child_ids = fields.One2many("document.folder", "parent_id", string="Subfolders")

    complete_name = fields.Char(compute="_compute_complete_name", store=True, index=True)

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for f in self:
            if f.parent_id:
                f.complete_name = f"{f.parent_id.complete_name} / {f.name}"
            else:
                f.complete_name = f.name
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

    def action_get_share_link(self):
        self.ensure_one()
        Share = self.env["document.share"].sudo()
        share = Share.search([
            ("share_type", "=", "folder"),
            ("folder_id", "=", self.id),
            ("active", "=", True),
        ], limit=1)
        if not share:
            share = Share.create({
                "share_type": "folder",
                "folder_id": self.id,
                "name": f"Share Folder: {self.name}",
            })
        return share.get_share_url()
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
    def _get_descendants(self):
        """self + all subfolders (recursive)."""
        self.ensure_one()
        Folder = self.env["document.folder"].with_context(active_test=False).sudo()
        all_folders = self
        stack = self
        while stack:
            children = Folder.search([("parent_id", "in", stack.ids)])
            children = children - all_folders
            if not children:
                break
            all_folders |= children
            stack = children
        return all_folders

    def _folder_depth(self, folder):
        d = 0
        cur = folder
        while cur.parent_id:
            d += 1
            cur = cur.parent_id
        return d

    def _find_blockers(self, folder_ids):
        """
        Tìm model/field nào đang Many2one -> document.folder và còn record trỏ tới.
        Trả về list tuple (model, field, count).
        """
        res = []
        IrFields = self.env["ir.model.fields"].sudo()
        m2o_fields = IrFields.search([
            ("ttype", "=", "many2one"),
            ("relation", "=", "document.folder"),
        ])
        for f in m2o_fields:
            model_name = f.model
            field_name = f.name
            if model_name not in self.env.registry.models:
                continue
            M = self.env[model_name].with_context(active_test=False).sudo()
            if field_name not in M._fields:
                continue
            try:
                cnt = M.search_count([(field_name, "in", folder_ids)])
            except Exception:
                continue
            if cnt:
                res.append((model_name, field_name, cnt))
        return res

    def action_delete_recursive(self):
        """
        1) Xóa tất cả document.document trong folder + subfolders (kể cả archived)
        2) Đảm bảo không còn document nào trỏ folder
        3) Xóa folder con trước, rồi xóa folder cha
        Nếu vẫn không xóa được -> raise UserError chỉ ra model/field đang chặn.
        """
        Folder = self.env["document.folder"].with_context(active_test=False).sudo()
        Doc = self.env["document.document"].with_context(active_test=False).sudo()

        for folder in Folder.browse(self.ids).exists():
            folders = folder._get_descendants()

            # ===== 1) PURGE FILES FIRST =====
            docs = Doc.search([("folder_id", "in", folders.ids)])
            if docs:
                docs.unlink()

            # ===== 2) VERIFY NO DOC LEFT =====
            remaining = Doc.search_count([("folder_id", "in", folders.ids)])
            if remaining:
                raise UserError(_("Không thể xóa folder vì vẫn còn %s file trong folder/subfolder (kể cả archived).") % remaining)

            # ===== 3) DELETE FOLDERS (children first) =====
            ordered = folders.sorted(key=lambda f: self._folder_depth(f), reverse=True)
            try:
                ordered.unlink()
            except Exception:
                blockers = self._find_blockers(folders.ids)
                if blockers:
                    msg = "Folder bị chặn bởi các quan hệ sau (model/field/count):\n"
                    msg += "\n".join([f"- {m}.{fld}: {cnt}" for (m, fld, cnt) in blockers])
                    raise UserError(msg)
                raise

        return True