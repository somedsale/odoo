# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from werkzeug.utils import redirect
import logging

_logger = logging.getLogger(__name__)

class S3RedirectBinary(http.Controller):
    @http.route(['/web/image/<int:id>', '/web/content/<int:id>'], type='http', auth='public')
    def web_image_redirect(self, id=None, **kw):
        attach = request.env['ir.attachment'].sudo().browse(id)
        if attach and attach.exists() and attach._is_s3_key(attach.store_fname):
            key = attach._normalize_store_key(attach.store_fname)
            url = attach._get_s3_url(key)
            if url:
                _logger.info("🔁 Redirecting to S3: %s", url)
                return redirect(url)
        # fallback Odoo default
        return request.env['ir.http'].sudo()._serve_attachment(attach, **kw)
