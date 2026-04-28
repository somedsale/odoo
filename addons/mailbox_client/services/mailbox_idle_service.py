# -*- coding: utf-8 -*-

import threading
import time
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

MAILBOX_IDLE_THREADS = {}
MAILBOX_IDLE_STOP_FLAGS = {}


def _idle_loop(db_name, account_id):
    from odoo import registry as registry_get

    _logger.info("[mailbox_idle] starting loop for account %s", account_id)

    while True:
        stop_flag = MAILBOX_IDLE_STOP_FLAGS.get(account_id)
        if stop_flag and stop_flag.is_set():
            _logger.info("[mailbox_idle] stop requested for account %s", account_id)
            break

        imap_conn = None
        try:
            with registry_get(db_name).cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                account = env["mailbox.account"].browse(account_id)

                if not account.exists() or not account.active or not account.idle_enabled:
                    break

                account.write({
                    "idle_status": "running",
                    "idle_error_message": False,
                })

                imap_conn = account._connect_imap()
                account._sync_imap_folders(imap_conn)

                inbox = account.folder_ids.filtered(lambda f: f.code == "inbox" and f.active)[:1]
                if not inbox:
                    inbox = account.folder_ids.filtered(lambda f: f.active)[:1]

                if not inbox:
                    time.sleep(10)
                    continue

                ok = account._idle_wait_inbox(imap_conn, inbox)
                if ok:
                    account.write({
                        "idle_last_event": account._now_dt(),
                    })

                cr.commit()

        except Exception as e:
            _logger.exception("[mailbox_idle] loop error for account %s: %s", account_id, e)
            try:
                with registry_get(db_name).cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    account = env["mailbox.account"].browse(account_id)
                    if account.exists():
                        account.write({
                            "idle_status": "error",
                            "idle_error_message": str(e),
                        })
                    cr.commit()
            except Exception:
                _logger.exception("[mailbox_idle] failed to persist idle error")
            time.sleep(8)

        finally:
            try:
                if imap_conn:
                    imap_conn.logout()
            except Exception:
                pass

    try:
        with registry_get(db_name).cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            account = env["mailbox.account"].browse(account_id)
            if account.exists():
                account.write({"idle_status": "stopped"})
            cr.commit()
    except Exception:
        _logger.exception("[mailbox_idle] failed to mark stopped")

    MAILBOX_IDLE_THREADS.pop(account_id, None)
    MAILBOX_IDLE_STOP_FLAGS.pop(account_id, None)
    _logger.info("[mailbox_idle] loop ended for account %s", account_id)


def start_idle_thread(db_name, account_id):
    existing = MAILBOX_IDLE_THREADS.get(account_id)
    if existing and existing.is_alive():
        return False

    stop_flag = threading.Event()
    MAILBOX_IDLE_STOP_FLAGS[account_id] = stop_flag

    thread = threading.Thread(
        target=_idle_loop,
        args=(db_name, account_id),
        name=f"mailbox_idle_{account_id}",
        daemon=True,
    )
    MAILBOX_IDLE_THREADS[account_id] = thread
    thread.start()
    return True


def stop_idle_thread(account_id):
    stop_flag = MAILBOX_IDLE_STOP_FLAGS.get(account_id)
    if stop_flag:
        stop_flag.set()
        return True
    return False