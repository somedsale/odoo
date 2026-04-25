# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

from ..services.imap_idle_worker import imap_idle_manager


class MailboxIdleController(http.Controller):

    @http.route("/mailbox/idle/start_all", type="http", auth="user")
    def start_all_idle(self, **kwargs):
        if not request.env.user.has_group("mailbox_client.group_mailbox_manager"):
            return request.not_found()

        db_name = request.env.cr.dbname
        imap_idle_manager.restart_all(db_name)
        return "IMAP IDLE started"

    @http.route("/mailbox/idle/start/<int:account_id>", type="http", auth="user")
    def start_idle_account(self, account_id, **kwargs):
        if not request.env.user.has_group("mailbox_client.group_mailbox_manager"):
            return request.not_found()

        db_name = request.env.cr.dbname
        imap_idle_manager.start_account(db_name, account_id)
        return "IMAP IDLE started for account %s" % account_id      