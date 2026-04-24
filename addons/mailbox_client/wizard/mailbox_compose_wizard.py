# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MailboxComposeWizard(models.TransientModel):
    _name = "mailbox.compose.wizard"
    _description = "Mailbox Compose Wizard"

    mode = fields.Selection([
        ("new", "New"),
        ("reply", "Reply"),
        ("forward", "Forward"),
    ], default="new", required=True)

    account_id = fields.Many2one(
        "mailbox.account",
        string="Mailbox Account",
        required=True,
        default=lambda self: self.env["mailbox.account"].search(
            [("user_id", "=", self.env.user.id), ("active", "=", True)],
            limit=1
        ),
    )

    parent_message_id = fields.Many2one("mailbox.message", string="Parent Message")

    name = fields.Char(string="Subject", required=True)
    to_recipients = fields.Text(string="To", required=True)
    cc_recipients = fields.Text(string="Cc")
    bcc_recipients = fields.Text(string="Bcc")
    reply_to = fields.Char(string="Reply-To")

    body_html = fields.Html(
        string="Body",
        sanitize=False,
        sanitize_overridable=True,
    )
    body_text = fields.Text(string="Plain Text")

    attachment_ids = fields.Many2many(
        "ir.attachment",
        "mailbox_compose_ir_attachment_rel",
        "wizard_id",
        "attachment_id",
        string="Attachments",
    )
    @api.onchange("parent_message_id", "mode")
    def _onchange_parent_message_id(self):
        for rec in self:
            if not rec.parent_message_id:
                continue

            parent = rec.parent_message_id

            if rec.mode == "reply":
                rec.to_recipients = parent.reply_to or parent.sender or ""
                rec.cc_recipients = False
                if not rec.name:
                    rec.name = "Re: %s" % (parent.name or "")
                if not rec.body_html:
                    original_html = parent.body_html or ("<pre>%s</pre>" % (parent.body_text or ""))
                    rec.body_html = """
                        <p></p>
                        <p></p>
                        <hr/>
                        <p><strong>From:</strong> %s</p>
                        <p><strong>Date:</strong> %s</p>
                        <p><strong>Subject:</strong> %s</p>
                        %s
                    """ % (
                        parent.sender or "",
                        parent.message_date or "",
                        parent.name or "",
                        original_html,
                    )

            elif rec.mode == "forward":
                if not rec.name:
                    rec.name = "Fwd: %s" % (parent.name or "")
                if not rec.body_html:
                    original_html = parent.body_html or ("<pre>%s</pre>" % (parent.body_text or ""))
                    rec.body_html = """
                        <p></p>
                        <p></p>
                        <hr/>
                        <p><strong>From:</strong> %s</p>
                        <p><strong>Date:</strong> %s</p>
                        <p><strong>To:</strong> %s</p>
                        <p><strong>Cc:</strong> %s</p>
                        <p><strong>Subject:</strong> %s</p>
                        %s
                    """ % (
                        parent.sender or "",
                        parent.message_date or "",
                        parent.to_recipients or "",
                        parent.cc_recipients or "",
                        parent.name or "",
                        original_html,
                    )

    def action_send(self):
        self.ensure_one()

        if not self.account_id:
            raise UserError(_("Không tìm thấy mailbox account để gửi mail."))

        if not self.to_recipients:
            raise UserError(_("Bạn phải nhập người nhận."))

        sent_message = self.account_id._send_email_via_smtp(
            subject=self.name,
            body_html=self.body_html,
            body_text=self.body_text,
            to_recipients=self.to_recipients,
            cc_recipients=self.cc_recipients,
            bcc_recipients=self.bcc_recipients,
            reply_to=self.reply_to,
            attachments=self.attachment_ids,
            parent_message=self.parent_message_id,
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Sent Email"),
            "res_model": "mailbox.message",
            "res_id": sent_message.id,
            "view_mode": "form",
            "target": "current",
        }