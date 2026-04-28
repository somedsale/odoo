# -*- coding: utf-8 -*-

from odoo import api, fields, models


class MailboxMessage(models.Model):
    _name = "mailbox.message"
    _description = "Mailbox Message"
    _order = "message_date desc, id desc"

    name = fields.Char(required=True)
    account_id = fields.Many2one(
        "mailbox.account",
        required=True,
        ondelete="cascade",
    )
    folder_id = fields.Many2one(
        "mailbox.folder",
        required=True,
        ondelete="restrict",
    )

    direction = fields.Selection([
        ("incoming", "Incoming"),
        ("outgoing", "Outgoing"),
    ], default="incoming", required=True)

    state = fields.Selection([
        ("received", "Received"),
        ("sent", "Sent"),
        ("draft", "Draft"),
        ("trash", "Trash"),
    ], default="received", required=True)

    sender = fields.Char()
    sender_name = fields.Char()
    to_recipients = fields.Text()
    cc_recipients = fields.Text()
    bcc_recipients = fields.Text()
    reply_to = fields.Char()

    body_html = fields.Html(sanitize=False)
    body_text = fields.Text()
    snippet = fields.Char(compute="_compute_snippet", store=True)

    message_date = fields.Datetime(index=True)
    is_read = fields.Boolean(default=False)
    is_starred = fields.Boolean(default=False)

    message_id_header = fields.Char(index=True)
    in_reply_to = fields.Char()
    references_header = fields.Text()

    attachment_ids = fields.Many2many(
        "ir.attachment",
        "mailbox_message_ir_attachment_rel",
        "message_id",
        "attachment_id",
        string="Attachments",
    )
    attachment_count = fields.Integer(compute="_compute_attachment_count")

    _sql_constraints = [
        (
            "mailbox_message_account_message_id_uniq",
            "unique(account_id, message_id_header)",
            "Message-ID already exists for this account.",
        ),
    ]

    @api.depends("body_text", "body_html")
    def _compute_snippet(self):
        for rec in self:
            source = rec.body_text or rec.body_html or ""
            text = source
            if isinstance(text, str):
                text = (
                    text.replace("<br>", " ")
                    .replace("<br/>", " ")
                    .replace("<br />", " ")
                )
            rec.snippet = (text or "").strip()[:180]

    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = len(rec.attachment_ids)

    def action_mark_read(self):
        self.write({"is_read": True})
        return True

    def action_mark_unread(self):
        self.write({"is_read": False})
        return True

    def action_toggle_star(self):
        for rec in self:
            rec.is_starred = not rec.is_starred
        return True

    def action_move_trash(self):
        for rec in self:
            trash_folder = self.env["mailbox.folder"].search([
                ("account_id", "=", rec.account_id.id),
                ("code", "=", "trash"),
            ], limit=1)
            if trash_folder:
                rec.write({
                    "folder_id": trash_folder.id,
                    "state": "trash",
                })
        return True

    def action_restore_inbox(self):
        for rec in self:
            inbox_folder = self.env["mailbox.folder"].search([
                ("account_id", "=", rec.account_id.id),
                ("code", "=", "inbox"),
            ], limit=1)
            if inbox_folder:
                rec.write({
                    "folder_id": inbox_folder.id,
                    "state": "received",
                })
        return True

    def get_message_full_data(self):
        self.ensure_one()

        attachments = []
        for att in self.attachment_ids:
            attachments.append({
                "id": att.id,
                "name": att.name,
                "mimetype": att.mimetype,
                "file_size": att.file_size,
            })

        return {
            "id": self.id,
            "name": self.name,
            "sender": self.sender,
            "sender_name": self.sender_name,
            "to_recipients": self.to_recipients,
            "cc_recipients": self.cc_recipients,
            "bcc_recipients": self.bcc_recipients,
            "reply_to": self.reply_to,
            "body_html": self.body_html,
            "body_text": self.body_text,
            "message_date": self.message_date,
            "is_read": self.is_read,
            "is_starred": self.is_starred,
            "attachment_count": self.attachment_count,
            "folder_id": self.folder_id.id if self.folder_id else False,
            "account_id": self.account_id.id if self.account_id else False,
            "direction": self.direction,
            "state": self.state,
            "attachments": attachments,
        }