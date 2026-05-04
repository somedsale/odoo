from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MailboxSignature(models.Model):
    _name = "mailbox.signature"
    _description = "Mailbox Signature"
    _order = "is_default desc, sequence asc, id desc"

    name = fields.Char(string="Signature Name", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    user_id = fields.Many2one(
        "res.users",
        string="User",
        required=True,
        default=lambda self: self.env.user,
        ondelete="cascade",
        index=True,
    )

    is_default = fields.Boolean(string="Default")
    signature_html = fields.Html(
        string="Signature Content",
        sanitize=False,
        translate=False,
        required=True,
    )

    @api.model
    def _my_domain(self):
        return [("user_id", "=", self.env.user.id)]

    @api.constrains("is_default", "user_id", "active")
    def _check_single_default_per_user(self):
        for rec in self:
            if rec.is_default and rec.active:
                other = self.search_count([
                    ("id", "!=", rec.id),
                    ("user_id", "=", rec.user_id.id),
                    ("is_default", "=", True),
                    ("active", "=", True),
                ])
                if other:
                    raise ValidationError(_("Mỗi người dùng chỉ được có một chữ ký mặc định."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["user_id"] = self.env.user.id
        records = super().create(vals_list)
        for rec in records:
            if rec.is_default:
                rec._unset_other_defaults()
        return records

    def write(self, vals):
        if "user_id" in vals:
            vals.pop("user_id")

        self._check_owner_access()

        res = super().write(vals)
        if "is_default" in vals:
            for rec in self.filtered(lambda r: r.is_default):
                rec._unset_other_defaults()
        return res

    def unlink(self):
        self._check_owner_access()
        return super().unlink()

    def _unset_other_defaults(self):
        self.ensure_one()
        others = self.search([
            ("id", "!=", self.id),
            ("user_id", "=", self.user_id.id),
            ("is_default", "=", True),
        ])
        if others:
            others.write({"is_default": False})

    def _check_owner_access(self):
        for rec in self:
            if rec.user_id != self.env.user:
                raise ValidationError(_("Bạn chỉ được phép thao tác chữ ký của chính mình."))