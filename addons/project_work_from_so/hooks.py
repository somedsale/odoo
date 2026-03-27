# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Chạy sau khi cài module lần đầu."""
    try:
        env["project.project"].sudo()._sync_work_items_from_so_batch()
        _logger.info("Post init hook: synced work items from SO for all projects having sale_order_id.")
    except Exception:
        _logger.exception("Post init hook failed while syncing work items from SO.")