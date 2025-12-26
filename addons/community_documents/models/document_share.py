# -*- coding: utf-8 -*-
import secrets
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DocumentShare(models.Model):
    _name = "document.share"
    _description = "Document Share Link"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    name = fields.Char(default=lambda self: self.env["ir.sequence"].next_by_code("document.share") or _("Share"), required=True)
    active = fields.Boolean(default=True)

    token = fields.Char(index=True, readonly=True, copy=False)
    expiration_date = fields.Datetime()
    state = fields.Selection([("active", "Active"), ("expired", "Expired")], compute="_compute_state", store=False)

    document_ids = fields.Many2many("document.document", string="Documents", required=True)
    owner_id = fields.Many2one("res.users", default=lambda self: self.env.user, required=True)

    share_url = fields.Char(compute="_compute_share_url", store=False)

    @api.depends("expiration_date", "active")
    def _compute_state(self):
        now = fields.Datetime.now()
        for rec in self:
            if not rec.active:
                rec.state = "expired"
            elif rec.expiration_date and rec.expiration_date < now:
                rec.state = "expired"
            else:
                rec.state = "active"

    def _compute_share_url(self):
        for rec in self:
            rec.share_url = f"/documents/share/{rec.token}" if rec.token else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["token"] = secrets.token_urlsafe(24)
        return super().create(vals_list)

    def action_open_share(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.share_url,
            "target": "new",
        }
