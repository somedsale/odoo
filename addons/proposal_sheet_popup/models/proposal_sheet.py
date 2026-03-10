# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.tools.misc import format_amount
import logging

_logger = logging.getLogger(__name__)


class ProposalSheet(models.Model):
    _inherit = "proposal.sheet"

    @api.model
    def get_proposal_info_for_popup(self, proposal_id):
        proposal = self.sudo().browse(int(proposal_id)).exists()
        if not proposal:
            return {
                "name": "Not found",
                "state": "",
                "state_label": "",
                "requested_by": "",
                "project": "",
                "type": "",
                "type_label": "",
                "currency_symbol": "",
                "amount_total_fmt": "",
                "amount_total_taxes_fmt": "",
                "payment_total": 0.0,
                "payment_total_fmt": "",
                "lines": [],
            }

        # Labels
        try:
            type_label = dict(self._fields["type"].selection).get(proposal.type, proposal.type or "")
        except Exception:
            type_label = proposal.type or ""

        try:
            state_label = dict(self._fields["state"].selection).get(proposal.state, proposal.state or "")
        except Exception:
            state_label = proposal.state or ""

        currency = proposal.currency_id or proposal.company_id.currency_id
        currency_symbol = currency.symbol or ""

        def money_fmt(amount):
            try:
                return format_amount(self.env, float(amount or 0.0), currency)
            except Exception:
                try:
                    return f"{float(amount or 0.0):,.0f} {currency_symbol}".strip()
                except Exception:
                    return ""

        def _get(obj, field, default=None):
            return getattr(obj, field, default) if hasattr(obj, field) else default

        lines_out = []

        # ===== Lines by type =====
        if proposal.type == "material" and hasattr(proposal, "material_line_ids"):
            for ln in proposal.material_line_ids.sudo():
                name = ""
                prod = _get(ln, "product_id")
                if prod:
                    name = prod.display_name

                if not name:
                    mat = _get(ln, "material_id")
                    if mat:
                        name = getattr(mat, "display_name", "") or getattr(mat, "name", "")

                if not name:
                    name = _get(ln, "name") or _get(ln, "description") or ""

                qty = _get(ln, "quantity", 0.0) or 0.0
                uom = _get(ln, "unit")
                uom_name = (
                    uom.display_name if uom
                    else (_get(ln, "product_uom") and _get(ln, "product_uom").display_name) or ""
                )

                price_unit = _get(ln, "price_unit", 0.0) or 0.0
                total = _get(ln, "price_total", None)
                if total is None:
                    total = _get(ln, "price_total_taxed", None)
                if total is None:
                    try:
                        total = float(qty) * float(price_unit)
                    except Exception:
                        total = 0.0

                lines_out.append({
                    "name": name,
                    "qty": qty,
                    "uom": uom_name,
                    "price_unit_fmt": money_fmt(price_unit),
                    "total_fmt": money_fmt(total),
                })

        elif proposal.type == "expense" and hasattr(proposal, "expense_line_ids"):
            for ln in proposal.expense_line_ids.sudo():
                name = ""
                exp = _get(ln, "expense_id")
                if exp:
                    name = exp.display_name
                if not name:
                    name = _get(ln, "name") or _get(ln, "description") or ""

                qty = _get(ln, "quantity", 0.0) or 0.0
                uom = _get(ln, "unit")
                uom_name = uom.display_name if uom else ""

                price_unit = _get(ln, "price_unit", 0.0) or 0.0
                total = _get(ln, "price_total", None)
                if total is None:
                    try:
                        total = float(qty) * float(price_unit)
                    except Exception:
                        total = 0.0

                lines_out.append({
                    "name": name,
                    "qty": qty,
                    "uom": uom_name,
                    "price_unit_fmt": money_fmt(price_unit),
                    "total_fmt": money_fmt(total),
                })

        elif proposal.type == "other" and hasattr(proposal, "expense_noproject_line_ids"):
            for ln in proposal.expense_noproject_line_ids.sudo():
                name = _get(ln, "content") or _get(ln, "name") or ""
                qty = _get(ln, "quantity", 0.0) or 0.0

                uom = _get(ln, "unit")
                uom_name = uom.display_name if uom else ""

                price_unit = _get(ln, "price_unit", 0.0) or 0.0
                total = _get(ln, "amount_total", None)
                if total is None:
                    total = _get(ln, "amount", None)
                if total is None:
                    try:
                        total = float(qty) * float(price_unit)
                    except Exception:
                        total = 0.0

                lines_out.append({
                    "name": name,
                    "qty": qty,
                    "uom": uom_name,
                    "price_unit_fmt": money_fmt(price_unit),
                    "total_fmt": money_fmt(total),
                })

        # ===== payment_total (new) =====
        payment_total = getattr(proposal, "payment_total", None)

        if payment_total is None:
            # fallback: sum payment requests by proposal_sheet_id
            payment_total = 0.0
            try:
                prs = self.env["account.payment.request"].sudo().search([("proposal_sheet_id", "=", proposal.id)])
                if prs:
                    # prefer 'total' if exists, else fallback fields
                    if "total" in prs._fields:
                        payment_total = sum(prs.mapped("total"))
                    elif "amount_total" in prs._fields:
                        payment_total = sum(prs.mapped("amount_total"))
                    elif "amount" in prs._fields:
                        payment_total = sum(prs.mapped("amount"))
            except Exception:
                payment_total = 0.0

        payment_total = float(payment_total or 0.0)

        # sort lines for stable UI
        try:
            lines_out.sort(key=lambda x: (x.get("name") or "").lower())
        except Exception:
            pass

        return {
            "id": proposal.id,
            "name": proposal.name or "",
            "state": proposal.state or "",
            "state_label": state_label,
            "requested_by": proposal.requested_by.name if proposal.requested_by else "",
            "project": proposal.project_id.display_name if proposal.project_id else "",
            "type": proposal.type or "",
            "type_label": type_label,
            "currency_symbol": currency_symbol,
            "amount_total_fmt": money_fmt(getattr(proposal, "amount_total", 0.0)),
            "amount_total_taxes_fmt": money_fmt(getattr(proposal, "amount_total_taxes", getattr(proposal, "amount_total", 0.0))),
            "payment_total": payment_total,
            "payment_total_fmt": money_fmt(payment_total),
            "lines": lines_out,
        }
