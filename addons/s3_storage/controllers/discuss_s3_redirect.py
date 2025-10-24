# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from werkzeug.utils import redirect
import logging

_logger = logging.getLogger(__name__)

class DiscussS3Redirect(http.Controller):
    @http.route(
        ['/discuss/channel/<int:channel_id>/image/<int:attachment_id>'],
        type='http',
        auth='user',
    )
    def discuss_image_redirect(self, channel_id=None, attachment_id=None, **kwargs):
        """Redirect Discuss chat image to S3 if stored remotely."""
        attach = request.env['ir.attachment'].sudo().browse(attachment_id)
        if not attach.exists():
            return request.not_found()

        if attach._is_s3_key(attach.store_fname):
            key = attach._normalize_store_key(attach.store_fname)
            url = attach._get_s3_url(key)
            if url:
                _logger.info("💬 [Discuss → S3 redirect] %s", url)
                return redirect(url)

        # fallback: use default internal route (Odoo local)
        _logger.debug("💬 [Discuss → local serve] %s", attach.store_fname)
        return request.env['ir.http'].sudo()._serve_attachment(attach, **kwargs)
