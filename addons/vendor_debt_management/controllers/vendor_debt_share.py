# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
from werkzeug.exceptions import NotFound, Forbidden


class VendorDebtShareController(http.Controller):

    @http.route(
        ["/vendor-debt/share/<string:token>"],
        type="http",
        auth="public",
        website=True,
        csrf=False,
    )
    def vendor_debt_share(self, token, **kwargs):
        Note = request.env["supplier.invoice.payment.summary.note"].sudo()
        Summary = request.env["supplier.invoice.payment.summary"].sudo()

        note = Note.search([
            ("share_token", "=", token),
            ("share_enabled", "=", True),
        ], limit=1)

        if not note:
            raise NotFound()

        if note.share_expired_at and fields.Datetime.now() > note.share_expired_at:
            raise Forbidden("Liên kết đã hết hạn.")

        summary = Summary.search([
            ("partner_id", "=", note.partner_id.id),
            ("currency_id", "=", note.currency_id.id),
        ], limit=1)

        if not summary:
            raise NotFound()

        report_data = summary.get_owl_report_data()

        values = {
            "summary": summary,
            "share_note": note,
            "report_data": report_data,
        }
        return request.render("vendor_debt_management.vendor_debt_share_page", values)