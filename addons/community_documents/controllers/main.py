# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class DocumentShareController(http.Controller):

    @http.route("/documents/share/<string:token>", type="http", auth="public", website=True)
    def documents_share(self, token, **kw):
        Share = request.env["document.share"].sudo()
        share = Share.search([("token", "=", token)], limit=1)
        if not share or share.state != "active":
            return request.not_found()

        # Render a very simple public page listing docs + download links
        return request.render("community_documents.document_share_page", {
            "share": share,
            "docs": share.document_ids.sudo(),
        })
