# -*- coding: utf-8 -*-

from odoo import fields, models


class MailboxFolder(models.Model):
    _name = "mailbox.folder"
    _description = "Mailbox Folder"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=100)
    active = fields.Boolean(default=True)

    account_id = fields.Many2one(
        "mailbox.account",
        required=True,
        ondelete="cascade",
    )
    imap_name = fields.Char(required=True)
    code = fields.Selection([
        ("inbox", "Inbox"),
        ("sent", "Sent"),
        ("draft", "Draft"),
        ("trash", "Trash"),
        ("spam", "Spam"),
        ("archive", "Archive"),
        ("custom", "Custom"),
    ], default="custom", required=True)

    mailbox_message_ids = fields.One2many(
        "mailbox.message",
        "folder_id",
        string="Messages",
    )
    mailbox_message_count = fields.Integer(compute="_compute_mailbox_message_count")

    _sql_constraints = [
        (
            "mailbox_folder_account_imap_name_uniq",
            "unique(account_id, imap_name)",
            "Folder already exists for this account.",
        ),
    ]

    def _compute_mailbox_message_count(self):
        for rec in self:
            rec.mailbox_message_count = len(rec.mailbox_message_ids)