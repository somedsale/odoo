# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from werkzeug.utils import redirect
import logging

_logger = logging.getLogger(__name__)


class S3RedirectController(http.Controller):
    """
    Controller redirect tất cả route đọc/tải attachment của Odoo sang S3
    """

    # ==========================================================
    # /web/image/<id> (ảnh form/report)
    # ==========================================================
    @http.route(['/web/image/<int:attachment_id>'], type='http', auth='public')
    def web_image_redirect(self, attachment_id=None, **kw):
        return self._redirect_s3_if_needed(attachment_id, label="🖼️ /web/image", **kw)

    # ==========================================================
    # /web/content/<id> (file binary)
    # ==========================================================
    @http.route(['/web/content/<int:attachment_id>'], type='http', auth='user')
    def web_content_redirect(self, attachment_id=None, **kw):
        return self._redirect_s3_if_needed(attachment_id, label="📄 /web/content", **kw)

    # ==========================================================
    # /web/content/ir.attachment/<id>/datas (nút tải file form/view)
    # ==========================================================
    @http.route(['/web/content/ir.attachment/<int:attachment_id>/datas'], type='http', auth='user')
    def web_content_datas_redirect(self, attachment_id=None, **kw):
        return self._redirect_s3_if_needed(attachment_id, label="📎 /web/content/ir.attachment/datas", **kw)

    # ==========================================================
    # /mail/attachment/<id>/download (nút tải chatter)
    # ==========================================================
    @http.route(['/mail/attachment/<int:attachment_id>/download'], type='http', auth='user')
    def mail_attachment_download(self, attachment_id=None, **kw):
        return self._redirect_s3_if_needed(attachment_id, label="💬 /mail/attachment/download", **kw)

    # ==========================================================
    # /discuss/channel/<id>/image/<id> (ảnh trong chatter)
    # ==========================================================
    @http.route(
        ['/discuss/channel/<int:channel_id>/image/<int:attachment_id>'],
        type='http', auth='user'
    )
    def discuss_image_redirect(self, channel_id=None, attachment_id=None, **kw):
        return self._redirect_s3_if_needed(attachment_id, label=f"💬 /discuss/image/{channel_id}", **kw)

    # ==========================================================
    # /discuss/channel/<id>/attachment/<id> (PDF, DOC, XLSX, ...)
    # ==========================================================
    @http.route(
        ['/discuss/channel/<int:channel_id>/attachment/<int:attachment_id>'],
        type='http', auth='user'
    )
    def discuss_attachment_redirect(self, channel_id=None, attachment_id=None, **kw):
        return self._redirect_s3_if_needed(attachment_id, label=f"💬 /discuss/attachment/{channel_id}", **kw)

    # ==========================================================
    # HELPER CHUNG
    # ==========================================================
    def _redirect_s3_if_needed(self, attachment_id, label="", **kw):
        """Redirect nếu attachment nằm trên S3"""
        attach = request.env['ir.attachment'].sudo().browse(attachment_id)
        if not attach.exists():
            return request.not_found()

        try:
            if attach._is_s3_key(attach.store_fname):
                key = attach._normalize_store_key(attach.store_fname)
                url = attach._get_s3_url(key)
                if url:
                    _logger.info("%s → Redirect to S3: %s", label, url)
                    return redirect(url)
        except Exception as e:
            _logger.warning("⚠️ %s redirect error: %s", label, e)

        _logger.debug("%s fallback local serve %s", label, attach.store_fname)
        return request.env['ir.http'].sudo()._serve_attachment(attach, **kw)
