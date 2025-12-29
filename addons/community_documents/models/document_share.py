# -*- coding: utf-8 -*-
import secrets
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DocumentShare(models.Model):
    _name = "document.share"
    _description = "Document Share Link"
    _order = "id desc"

    name = fields.Char(default="Share Link")
    token = fields.Char(required=True, index=True, readonly=True)
    owner_id = fields.Many2one(
        "res.users",
        string="Owner",
        default=lambda self: self.env.user,
        required=True,
        index=True,
    )

    share_type = fields.Selection(
        [("folder", "Folder"), ("document", "Document")],
        required=True,
        index=True,
    )

    folder_id = fields.Many2one("document.folder", ondelete="cascade")
    document_id = fields.Many2one("document.document", ondelete="cascade")

    allow_download = fields.Boolean(default=True)
    expiration_date = fields.Datetime()
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("uniq_token", "unique(token)", "Share token must be unique."),
    ]

    @api.model
    def _generate_token(self):
        return secrets.token_urlsafe(24)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("token", self._generate_token())
        return super().create(vals_list)

    def _check_valid(self):
        self.ensure_one()
        if not self.active:
            raise UserError(_("This share link is disabled."))
        if self.expiration_date and fields.Datetime.now() > self.expiration_date:
            raise UserError(_("This share link has expired."))

    def get_share_url(self):
        self.ensure_one()
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        return f"{base_url}/docs/s/{self.token}"
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("token", self._generate_token())
            vals.setdefault("owner_id", self.env.user.id)
        return super().create(vals_list)
