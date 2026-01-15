# -*- coding: utf-8 -*-
import base64
from odoo import http
from odoo.http import request, content_disposition


class DocumentShareController(http.Controller):

    def _get_share(self, token):
        share = request.env["document.share"].sudo().search([("token", "=", token)], limit=1)
        if not share:
            return None
        # validate
        try:
            share._check_valid()
        except Exception:
            return None
        return share

    @http.route("/docs/s/<string:token>", type="http", auth="public", website=False)
    def share_page(self, token, **kw):
        share = self._get_share(token)
        if not share:
            return request.not_found()

        values = {"share": share}

        if share.share_type == "document":
            doc = share.document_id.sudo()
            values["doc"] = doc
            return request.render("community_documents.share_document_page", values)

        folder = share.folder_id.sudo()
        docs = request.env["document.document"].sudo().search([("folder_id", "=", folder.id)], order="write_date desc", limit=200)
        values.update({"folder": folder, "docs": docs})
        return request.render("community_documents.share_folder_page", values)

    @http.route("/docs/s/<string:token>/content", type="http", auth="public", website=False)
    def share_content(self, token, doc_id=None, download="0", **kw):
        share = self._get_share(token)
        if not share:
            return request.not_found()

        allow_download = bool(share.allow_download) or str(download) == "0"
        if str(download) == "1" and not allow_download:
            return request.not_found()

        if share.share_type == "document":
            doc = share.document_id.sudo()
        else:
            # folder share -> doc_id must belong to folder
            if not doc_id:
                return request.not_found()
            doc = request.env["document.document"].sudo().browse(int(doc_id))
            if not doc.exists() or doc.folder_id.id != share.folder_id.id:
                return request.not_found()

        att = doc.attachment_id.sudo()
        if not att:
            return request.not_found()

        if att.type == "url":
            # redirect to url
            return request.redirect(att.url)

        data = base64.b64decode(att.datas or b"")
        mimetype = doc.mimetype or 'application/octet-stream'
        filename = doc.name or 'file'

        dispo = content_disposition(filename)  # trả về attachment; filename*=UTF-8''...
        if not int(download or 0):
            dispo = dispo.replace('attachment', 'inline', 1)

        headers = [
            ('Content-Type', mimetype),
            ('Content-Disposition', dispo),
        ]
        return request.make_response(data, headers=headers)
