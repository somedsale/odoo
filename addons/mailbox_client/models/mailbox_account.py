# -*- coding: utf-8 -*-

import base64
import email
import imaplib
import smtplib
import socket
import ssl
import time

from email.header import decode_header, make_header, Header
from email.message import EmailMessage
from email.utils import (
    parsedate_to_datetime,
    make_msgid,
    getaddresses,
    formataddr,
)

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..services.mailbox_idle_service import start_idle_thread, stop_idle_thread


class MailboxAccount(models.Model):
    _name = "mailbox.account"
    _description = "Mailbox Account"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)

    user_id = fields.Many2one(
        "res.users",
        string="User",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )

    email_address = fields.Char(string="Email Address", required=True, tracking=True)
    login = fields.Char(string="Login", required=True)
    password = fields.Char(string="Password", required=True)

    imap_host = fields.Char(string="IMAP Host", required=True, default="pro63.emailserver.vn")
    imap_port = fields.Integer(string="IMAP Port", default=993)
    imap_ssl = fields.Boolean(string="IMAP SSL", default=True)

    smtp_host = fields.Char(string="SMTP Host", required=True, default="pro63.emailserver.vn")
    smtp_port = fields.Integer(string="SMTP Port", default=465)
    smtp_ssl = fields.Boolean(string="SMTP SSL", default=True)
    smtp_starttls = fields.Boolean(string="SMTP STARTTLS", default=True)

    idle_enabled = fields.Boolean(default=True, string="Enable IMAP IDLE")
    idle_status = fields.Selection([
        ("stopped", "Stopped"),
        ("running", "Running"),
        ("error", "Error"),
    ], default="stopped", readonly=True)
    idle_last_event = fields.Datetime(readonly=True)
    idle_error_message = fields.Text(readonly=True)

    folder_ids = fields.One2many(
        "mailbox.folder",
        "account_id",
        string="Folders",
    )
    mailbox_message_ids = fields.One2many(
        "mailbox.message",
        "account_id",
        string="Messages",
    )

    last_fetch_date = fields.Datetime(readonly=True)
    last_fetch_status = fields.Selection([
        ("never", "Never"),
        ("success", "Success"),
        ("failed", "Failed"),
    ], default="never", readonly=True)
    last_fetch_message = fields.Text(readonly=True)

    _sql_constraints = [
        (
            "mailbox_account_email_user_uniq",
            "unique(email_address, user_id)",
            "Email account already exists for this user.",
        ),
    ]

    @api.model
    def _now_dt(self):
        return fields.Datetime.now()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._create_default_folders()
            if rec.active and rec.idle_enabled:
                try:
                    rec.action_start_idle()
                except Exception:
                    pass
        return records

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if "active" in vals or "idle_enabled" in vals:
                if rec.active and rec.idle_enabled:
                    try:
                        rec.action_start_idle()
                    except Exception:
                        pass
                else:
                    rec.action_stop_idle()
        return res

    def unlink(self):
        for rec in self:
            rec.action_stop_idle()
        return super().unlink()

    # ---------------------------------------------------------
    # Default folders
    # ---------------------------------------------------------

    def _create_default_folders(self):
        folder_model = self.env["mailbox.folder"]
        for rec in self:
            default_folders = [
                ("Inbox", "INBOX", "inbox", 10),
                ("Sent", "Sent", "sent", 20),
                ("Drafts", "Drafts", "draft", 30),
                ("Trash", "Trash", "trash", 40),
                ("Spam", "Spam", "spam", 50),
                ("Archive", "Archive", "archive", 60),
            ]
            existing_codes = set(rec.folder_ids.mapped("code"))
            for name, imap_name, code, sequence in default_folders:
                if code not in existing_codes:
                    folder_model.create({
                        "account_id": rec.id,
                        "name": name,
                        "imap_name": imap_name,
                        "code": code,
                        "sequence": sequence,
                        "active": True,
                    })

    # ---------------------------------------------------------
    # Buttons
    # ---------------------------------------------------------

    def action_test_imap(self):
        for rec in self:
            conn = None
            try:
                conn = rec._connect_imap()
                rec.message_post(body=_("IMAP connection successful."))
            except Exception as e:
                raise UserError(_("IMAP connection failed:\n%s") % str(e))
            finally:
                try:
                    if conn:
                        conn.logout()
                except Exception:
                    pass
        return True

    def action_test_smtp(self):
        for rec in self:
            conn = None
            try:
                conn = rec._connect_smtp()
                conn.quit()
                rec.message_post(body=_("SMTP connection successful."))
            except Exception as e:
                raise UserError(_("SMTP connection failed:\n%s") % str(e))
        return True

    def action_fetch_mail(self):
        for rec in self:
            rec._fetch_mail()
        return True

    def action_start_idle(self):
        for rec in self:
            rec.write({
                "idle_status": "running",
                "idle_error_message": False,
            })
            start_idle_thread(self.env.cr.dbname, rec.id)
        return True

    def action_stop_idle(self):
        for rec in self:
            stop_idle_thread(rec.id)
            rec.write({"idle_status": "stopped"})
        return True

    @api.model
    def cron_fetch_mailboxes(self):
        accounts = self.search([("active", "=", True)])
        for account in accounts:
            try:
                account._fetch_mail()
            except Exception:
                pass
        return True

    # ---------------------------------------------------------
    # Connections
    # ---------------------------------------------------------

    def _connect_imap(self):
        self.ensure_one()
        if self.imap_ssl:
            conn = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
        else:
            conn = imaplib.IMAP4(self.imap_host, self.imap_port)
        conn.login(self.login, self.password)
        return conn

    def _connect_smtp(self):
        self.ensure_one()
        if self.smtp_ssl:
            context = ssl.create_default_context()
            conn = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context)
        else:
            conn = smtplib.SMTP(self.smtp_host, self.smtp_port)
            if self.smtp_starttls:
                context = ssl.create_default_context()
                conn.starttls(context=context)
        conn.login(self.login, self.password)
        return conn

    # ---------------------------------------------------------
    # Folder sync / parsing
    # ---------------------------------------------------------

    def _guess_folder_code(self, folder_name):
        name = (folder_name or "").strip().lower()

        if name in ("inbox",):
            return "inbox"
        if "sent" in name or "sent items" in name or "đã gửi" in name:
            return "sent"
        if "draft" in name or "nháp" in name:
            return "draft"
        if "trash" in name or "bin" in name or "deleted" in name or "thùng rác" in name:
            return "trash"
        if "spam" in name or "junk" in name or "bulk" in name or "thư rác" in name:
            return "spam"
        if "archive" in name or "all mail" in name or "lưu trữ" in name:
            return "archive"
        return "custom"

    def _guess_folder_sequence(self, code):
        mapping = {
            "inbox": 10,
            "sent": 20,
            "draft": 30,
            "trash": 40,
            "spam": 50,
            "archive": 60,
            "custom": 100,
        }
        return mapping.get(code, 100)

    def _parse_imap_list_line(self, raw_line):
        if isinstance(raw_line, bytes):
            raw_line = raw_line.decode(errors="ignore")

        raw_line = (raw_line or "").strip()
        if not raw_line:
            return ""

        parts = raw_line.split(' "/" ')
        if len(parts) >= 2:
            mailbox_name = parts[-1].strip().strip('"').strip()
            return mailbox_name

        last_quote = raw_line.rfind('"')
        if last_quote == -1:
            return ""

        prev_quote = raw_line.rfind('"', 0, last_quote)
        if prev_quote == -1:
            return ""

        mailbox_name = raw_line[prev_quote + 1:last_quote].strip()
        return mailbox_name

    def _sync_imap_folders(self, imap_conn):
        self.ensure_one()
        folder_model = self.env["mailbox.folder"]

        typ, mailboxes = imap_conn.list()
        if typ != "OK":
            return

        existing_by_imap = {
            (f.imap_name or "").lower(): f
            for f in self.folder_ids
        }

        for raw in mailboxes or []:
            imap_name = self._parse_imap_list_line(raw)
            if not imap_name:
                continue

            imap_name = imap_name.strip()

            # bỏ folder rác
            if (
                not imap_name
                or imap_name in (".", '""', "INBOX.")
                or imap_name.startswith(".")
                or imap_name.endswith(".")
                or imap_name.startswith("(")
                or imap_name in ("[Gmail]",)
            ):
                continue

            code = self._guess_folder_code(imap_name)
            sequence = self._guess_folder_sequence(code)

            vals = {
                "account_id": self.id,
                "name": imap_name,
                "imap_name": imap_name,
                "code": code,
                "sequence": sequence,
                "active": True,
            }

            existing = existing_by_imap.get(imap_name.lower())
            if existing:
                existing.write(vals)
            else:
                folder_model.create(vals)

    def _select_imap_folder(self, imap_conn, folder_name, readonly=True):
        folder_name = (folder_name or "").strip() or "INBOX"
        escaped = folder_name.replace("\\", "\\\\").replace('"', r"\"")
        candidates = [f'"{escaped}"', folder_name]

        for candidate in candidates:
            try:
                typ, data = imap_conn.select(candidate, readonly=readonly)
                if typ == "OK":
                    return typ, data
            except Exception:
                continue
        return "BAD", [b"Cannot select folder"]

    # ---------------------------------------------------------
    # Fetch all folders
    # ---------------------------------------------------------

    def _fetch_mail(self):
        self.ensure_one()
        imap_conn = None
        try:
            imap_conn = self._connect_imap()
            self._sync_imap_folders(imap_conn)

            folders = self.folder_ids.filtered(lambda f: f.active and f.imap_name)
            total_fetched = 0
            inbox_new_count = 0

            for folder in folders.sorted(key=lambda f: (f.sequence, f.id)):
                fetched = self._fetch_folder_messages(imap_conn, folder)
                total_fetched += fetched
                if folder.code == "inbox":
                    inbox_new_count += fetched

            self.write({
                "last_fetch_date": fields.Datetime.now(),
                "last_fetch_status": "success",
                "last_fetch_message": _("Fetched successfully. Total processed: %s") % total_fetched,
            })

            if inbox_new_count:
                self._notify_new_mail_bus(new_count=inbox_new_count)

        except Exception as e:
            self.write({
                "last_fetch_date": fields.Datetime.now(),
                "last_fetch_status": "failed",
                "last_fetch_message": str(e),
            })
            raise UserError(_("Fetch mail failed:\n%s") % str(e))
        finally:
            try:
                if imap_conn:
                    imap_conn.logout()
            except Exception:
                pass
    def _fetch_folder_messages(self, imap_conn, folder, limit=100):
        self.ensure_one()
        fetched_count = 0

        typ, _data = self._select_imap_folder(imap_conn, folder.imap_name, readonly=True)
        if typ != "OK":
            return fetched_count

        typ, data = imap_conn.search(None, "ALL")
        if typ != "OK":
            return fetched_count

        msg_nums = data[0].split() if data and data[0] else []
        if not msg_nums:
            return fetched_count

        msg_nums = msg_nums[-limit:]

        for msg_num in msg_nums:
            try:
                ok = self._fetch_one_message(imap_conn, folder, msg_num)
                if ok:
                    fetched_count += 1
            except Exception:
                continue

        return fetched_count

    def _fetch_one_message(self, imap_conn, folder, msg_num):
        self.ensure_one()

        typ, msg_data = imap_conn.fetch(msg_num, "(RFC822)")
        if typ != "OK" or not msg_data:
            return False

        raw_email = None
        for part in msg_data:
            if isinstance(part, tuple) and len(part) >= 2:
                raw_email = part[1]
                break

        if not raw_email:
            return False

        parsed = email.message_from_bytes(raw_email)
        message_id_header = self._sanitize_mail_header_value(parsed.get("Message-ID"))

        message_model = self.env["mailbox.message"]
        existing = False
        if message_id_header:
            existing = message_model.search([
                ("account_id", "=", self.id),
                ("message_id_header", "=", message_id_header),
            ], limit=1)

        if existing:
            if existing.folder_id != folder:
                existing.folder_id = folder.id
            return False

        subject = self._decode_mime_header(parsed.get("Subject"))
        sender = self._decode_mime_header(parsed.get("From"))
        to_recipients = self._decode_mime_header(parsed.get("To"))
        cc_recipients = self._decode_mime_header(parsed.get("Cc"))
        bcc_recipients = self._decode_mime_header(parsed.get("Bcc"))
        reply_to = self._decode_mime_header(parsed.get("Reply-To"))

        sender_name = ""
        sender_email = ""
        sender_pairs = getaddresses([sender or ""])
        if sender_pairs:
            sender_name = sender_pairs[0][0] or ""
            sender_email = sender_pairs[0][1] or ""

        references_header = self._sanitize_mail_header_value(parsed.get("References"))
        in_reply_to = self._sanitize_mail_header_value(parsed.get("In-Reply-To"))
        message_date = self._parse_message_date(parsed.get("Date"))

        vals = {
            "name": subject or "(No Subject)",
            "account_id": self.id,
            "folder_id": folder.id,
            "direction": "incoming",
            "state": "received",
            "sender": sender_email or sender or "",
            "sender_name": sender_name or "",
            "to_recipients": to_recipients or "",
            "cc_recipients": cc_recipients or "",
            "bcc_recipients": bcc_recipients or "",
            "reply_to": reply_to or "",
            "message_date": message_date,
            "message_id_header": message_id_header or False,
            "references_header": references_header or False,
            "in_reply_to": in_reply_to or False,
            "is_read": False if folder.code == "inbox" else True,
        }

        mailbox_message = message_model.create(vals)
        self._extract_body_and_attachments(parsed, mailbox_message)
        return True

    # ---------------------------------------------------------
    # Near realtime: IDLE wait inbox
    # ---------------------------------------------------------

    def _idle_wait_inbox(self, imap_conn, folder):
        self.ensure_one()

        typ, _data = self._select_imap_folder(imap_conn, folder.imap_name, readonly=True)
        if typ != "OK":
            return False

        tag = imap_conn._new_tag()
        imap_conn.send(b"%s IDLE\r\n" % tag)

        ready = imap_conn.readline()
        if not ready or b"+" not in ready:
            return False

        socket_obj = getattr(imap_conn, "sock", None)
        if socket_obj:
            socket_obj.settimeout(60.0)

        got_new_mail = False
        try:
            started = time.time()
            while time.time() - started < 55:
                response = imap_conn.readline()
                if not response:
                    continue
                response_up = response.upper()
                if b"EXISTS" in response_up or b"RECENT" in response_up:
                    got_new_mail = True
                    break
        except socket.timeout:
            pass
        finally:
            imap_conn.send(b"DONE\r\n")
            try:
                imap_conn.readline()
            except Exception:
                pass

        if got_new_mail:
            fetched = self._fetch_folder_messages(imap_conn, folder, limit=20)
            if fetched:
                self._notify_new_mail_bus(new_count=fetched)
                self.write({
                    "last_fetch_date": fields.Datetime.now(),
                    "last_fetch_status": "success",
                    "last_fetch_message": _("Fetched immediately by IMAP IDLE."),
                })
            return True

        return False
    def _notify_new_mail_bus(self, new_count=1):
        self.ensure_one()
        self.env["bus.bus"]._sendone(
            f"mailbox_user_{self.user_id.id}",
            "mailbox_new_mail",
            {
                "account_id": self.id,
                "email_address": self.email_address,
                "new_count": new_count,
                "timestamp": fields.Datetime.now().isoformat(),
                "title": "Mail mới",
                "message": "Bạn vừa nhận được email mới.",
            },
        )

    # ---------------------------------------------------------
    # Parsing helpers
    # ---------------------------------------------------------

    def _decode_mime_header(self, value):
        if not value:
            return ""
        try:
            return str(make_header(decode_header(value)))
        except Exception:
            return value

    def _parse_message_date(self, value):
        if not value:
            return fields.Datetime.now()
        try:
            dt = parsedate_to_datetime(value)
            if not dt:
                return fields.Datetime.now()
            if dt.tzinfo:
                dt = dt.astimezone(tz=None).replace(tzinfo=None)
            return dt
        except Exception:
            return fields.Datetime.now()

    def _extract_body_and_attachments(self, parsed_message, mailbox_message):
        self.ensure_one()

        body_text = ""
        body_html = ""
        attachment_model = self.env["ir.attachment"]

        if parsed_message.is_multipart():
            for part in parsed_message.walk():
                content_disposition = (part.get("Content-Disposition") or "").lower()
                content_type = (part.get_content_type() or "").lower()

                if part.get_content_maintype() == "multipart":
                    continue

                filename = part.get_filename()
                if filename:
                    filename = self._decode_mime_header(filename)

                if "attachment" in content_disposition or filename:
                    payload = part.get_payload(decode=True)
                    if payload:
                        att = attachment_model.create({
                            "name": filename or _("attachment"),
                            "datas": base64.b64encode(payload),
                            "mimetype": content_type or "application/octet-stream",
                            "res_model": "mailbox.message",
                            "res_id": mailbox_message.id,
                            "type": "binary",
                        })
                        mailbox_message.attachment_ids = [(4, att.id)]
                    continue

                if content_type == "text/html" and not body_html:
                    payload = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body_html = payload.decode(charset, errors="replace")
                    except Exception:
                        body_html = payload.decode("utf-8", errors="replace")
                    continue

                if content_type == "text/plain" and not body_text:
                    payload = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body_text = payload.decode(charset, errors="replace")
                    except Exception:
                        body_text = payload.decode("utf-8", errors="replace")
                    continue
        else:
            content_type = (parsed_message.get_content_type() or "").lower()
            payload = parsed_message.get_payload(decode=True) or b""
            charset = parsed_message.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="replace")
            except Exception:
                decoded = payload.decode("utf-8", errors="replace")

            if content_type == "text/html":
                body_html = decoded
            else:
                body_text = decoded

        final_body_text = body_text or ""
        final_body_html = body_html or ""

        text_stripped = (final_body_text or "").strip().lower()
        if not final_body_html and text_stripped.startswith("<") and (
            "<table" in text_stripped
            or "<div" in text_stripped
            or "<html" in text_stripped
            or "<body" in text_stripped
            or "<p" in text_stripped
            or "<span" in text_stripped
            or "<meta" in text_stripped
            or "<style" in text_stripped
        ):
            final_body_html = final_body_text

        if not final_body_html and final_body_text:
            final_body_html = "<pre>%s</pre>" % (final_body_text or "")

        mailbox_message.write({
            "body_text": final_body_text,
            "body_html": final_body_html or False,
        })

    # ---------------------------------------------------------
    # SMTP send
    # ---------------------------------------------------------

    def _sanitize_mail_header_value(self, value):
        value = (value or "").strip()
        value = value.replace("\r", " ").replace("\n", " ")
        value = " ".join(value.split())
        return value

    def _format_header_addresses(self, value):
        if not value:
            return ""

        pairs = getaddresses([value])
        results = []
        for name, addr in pairs:
            name = (name or "").strip()
            addr = (addr or "").strip()
            if not addr:
                continue

            if name:
                encoded_name = str(Header(name, "utf-8"))
                results.append(formataddr((encoded_name, addr)))
            else:
                results.append(addr)

        return ", ".join(results)

    def _extract_ascii_recipients(self, *blocks):
        recipients = []
        for block in blocks:
            if not block:
                continue

            pairs = getaddresses([block])
            for _name, addr in pairs:
                addr = (addr or "").strip()
                if not addr:
                    continue

                try:
                    addr.encode("ascii")
                except UnicodeEncodeError:
                    raise UserError(_(
                        "Địa chỉ email '%s' chứa ký tự Unicode. "
                        "SMTP server hiện tại không hỗ trợ SMTPUTF8."
                    ) % addr)

                recipients.append(addr)

        return recipients

    def _validate_ascii_email(self, addr, field_label):
        if not addr:
            return
        try:
            addr.encode("ascii")
        except UnicodeEncodeError:
            raise UserError(_(
                "%s '%s' chứa ký tự Unicode. "
                "SMTP server hiện tại không hỗ trợ SMTPUTF8."
            ) % (field_label, addr))

    def _send_email_via_smtp(
        self,
        subject,
        body_html,
        body_text,
        to_recipients,
        cc_recipients=None,
        bcc_recipients=None,
        reply_to=None,
        attachments=None,
        parent_message=None,
    ):
        self.ensure_one()

        self._validate_ascii_email(self.email_address, _("Email gửi đi"))

        msg = EmailMessage()
        msg["Subject"] = subject or ""
        msg["From"] = self._format_header_addresses(self.email_address)
        msg["To"] = self._format_header_addresses(to_recipients or "")

        if cc_recipients:
            msg["Cc"] = self._format_header_addresses(cc_recipients)

        if reply_to:
            msg["Reply-To"] = self._format_header_addresses(reply_to)

        msg_id = make_msgid()
        msg["Message-ID"] = self._sanitize_mail_header_value(msg_id)

        if parent_message and parent_message.message_id_header:
            in_reply_to = self._sanitize_mail_header_value(parent_message.message_id_header)
            references = self._sanitize_mail_header_value(parent_message.references_header)

            if in_reply_to:
                msg["In-Reply-To"] = in_reply_to

            refs = f"{references} {in_reply_to}".strip() if references else in_reply_to
            refs = self._sanitize_mail_header_value(refs)
            if refs:
                msg["References"] = refs

        if body_html:
            msg.set_content(body_text or "HTML email")
            msg.add_alternative(body_html, subtype="html")
        else:
            msg.set_content(body_text or "")

        for attachment in attachments or []:
            raw = attachment.raw or b""
            maintype, subtype = ("application", "octet-stream")
            if attachment.mimetype and "/" in attachment.mimetype:
                maintype, subtype = attachment.mimetype.split("/", 1)
            msg.add_attachment(
                raw,
                maintype=maintype,
                subtype=subtype,
                filename=attachment.name,
            )

        recipients = self._extract_ascii_recipients(
            to_recipients,
            cc_recipients,
            bcc_recipients,
        )

        if not recipients:
            raise UserError(_("Không có người nhận hợp lệ."))

        try:
            smtp_client = self._connect_smtp()
            smtp_client.send_message(
                msg,
                from_addr=self.email_address,
                to_addrs=recipients,
            )
            smtp_client.quit()
        except Exception as e:
            raise UserError(_("Gửi mail thất bại:\n%s") % str(e))

        sent_folder = self.env["mailbox.folder"].search([
            ("account_id", "=", self.id),
            ("code", "=", "sent"),
        ], limit=1)

        if not sent_folder:
            self._create_default_folders()
            sent_folder = self.env["mailbox.folder"].search([
                ("account_id", "=", self.id),
                ("code", "=", "sent"),
            ], limit=1)

        sent_message = self.env["mailbox.message"].create({
            "name": subject or "(No Subject)",
            "account_id": self.id,
            "folder_id": sent_folder.id,
            "direction": "outgoing",
            "state": "sent",
            "sender": self.email_address,
            "to_recipients": to_recipients,
            "cc_recipients": cc_recipients,
            "bcc_recipients": bcc_recipients,
            "reply_to": reply_to,
            "body_html": body_html or False,
            "body_text": body_text or False,
            "message_date": fields.Datetime.now(),
            "message_id_header": self._sanitize_mail_header_value(msg_id),
            "in_reply_to": self._sanitize_mail_header_value(parent_message.message_id_header) if parent_message else False,
            "references_header": self._sanitize_mail_header_value(parent_message.references_header) if parent_message else False,
            "is_read": True,
        })

        for attachment in attachments or []:
            sent_message.attachment_ids = [(4, attachment.id)]

        return sent_message