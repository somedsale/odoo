# -*- coding: utf-8 -*-
import imaplib
import logging
import threading
import time

import odoo
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


class ImapIdleSession(threading.Thread):
    def __init__(self, db_name, account_id, stop_event=None):
        super().__init__(daemon=True)
        self.db_name = db_name
        self.account_id = account_id
        self.stop_event = stop_event or threading.Event()

    def run(self):
        while not self.stop_event.is_set():
            try:
                self._run_idle_loop()
            except Exception as e:
                _logger.exception("IMAP IDLE crashed for account %s: %s", self.account_id, e)
                time.sleep(10)

    def _run_idle_loop(self):
        registry = odoo.registry(self.db_name)
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            account = env["mailbox.account"].browse(self.account_id).exists()
            if not account or not account.active:
                _logger.info("Mailbox account %s not active or not found", self.account_id)
                return

            imap_client = account._connect_imap()
            folder_name = account.inbox_folder_name or "INBOX"

            status, _data = imap_client.select(folder_name)
            if status != "OK":
                raise Exception("Cannot select folder %s" % folder_name)

            _logger.info("IMAP IDLE started for %s", account.email_address)

            try:
                while not self.stop_event.is_set():
                    self._idle_once(imap_client, env, account)
            finally:
                try:
                    imap_client.close()
                except Exception:
                    pass
                try:
                    imap_client.logout()
                except Exception:
                    pass

    def _idle_once(self, imap_client, env, account):
        tag = imap_client._new_tag()
        imap_client.send(f"{tag} IDLE\r\n".encode())

        response = imap_client.readline()
        if b"+ " not in response:
            raise Exception("Server did not accept IDLE: %s" % response.decode(errors="ignore"))

        start = time.time()
        timeout_seconds = 60 * 25

        while not self.stop_event.is_set():
            imap_client.sock.settimeout(5)
            try:
                line = imap_client.readline()
            except Exception:
                line = b""

            if line:
                text = line.decode(errors="ignore").strip()
                _logger.info("IDLE event account=%s line=%s", account.email_address, text)

                if "EXISTS" in text or "RECENT" in text:
                    imap_client.send(b"DONE\r\n")
                    done_line = imap_client.readline()
                    _logger.info("IDLE DONE response: %s", done_line.decode(errors="ignore").strip())

                    self._fetch_and_notify(env, account)
                    return

            if time.time() - start > timeout_seconds:
                imap_client.send(b"DONE\r\n")
                imap_client.readline()
                return

    def _fetch_and_notify(self, env, account):
        env.cr.rollback()
        account = env["mailbox.account"].browse(account.id).exists()
        if not account:
            return

        before_ids = set(
            env["mailbox.message"].search([
                ("account_id", "=", account.id),
                ("folder_id.code", "=", "inbox"),
            ]).ids
        )

        account._fetch_mail()

        after_messages = env["mailbox.message"].search([
            ("account_id", "=", account.id),
            ("folder_id.code", "=", "inbox"),
        ], order="id desc", limit=20)

        new_messages = after_messages.filtered(lambda m: m.id not in before_ids)

        if new_messages:
            payload = {
                "type": "mailbox_new_message",
                "account_id": account.id,
                "message_ids": new_messages.ids,
                "user_id": account.user_id.id,
            }
            env["bus.bus"]._sendone(
                "mailbox_user_%s" % account.user_id.id,
                "mailbox_event",
                payload,
            )
            _logger.info("New message notified for user %s", account.user_id.login)

        env.cr.commit()


class ImapIdleManager:
    def __init__(self):
        self.sessions = {}

    def start_account(self, db_name, account_id):
        key = (db_name, account_id)
        if key in self.sessions and self.sessions[key].is_alive():
            return

        stop_event = threading.Event()
        session = ImapIdleSession(db_name, account_id, stop_event=stop_event)
        self.sessions[key] = session
        session.start()

    def stop_account(self, db_name, account_id):
        key = (db_name, account_id)
        session = self.sessions.get(key)
        if session:
            session.stop_event.set()
            self.sessions.pop(key, None)

    def restart_all(self, db_name):
        registry = odoo.registry(db_name)
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            accounts = env["mailbox.account"].search([("active", "=", True)])
            for account in accounts:
                self.start_account(db_name, account.id)


imap_idle_manager = ImapIdleManager()