# -*- coding: utf-8 -*-
from odoo import models, api
from datetime import date


class SupplierDebtRealReport(models.AbstractModel):
    _name = "report.vendor_debt_management.report_supplier_debt_real_view"
    _description = "Báo cáo Tổng hợp Công nợ NCC thực tế (theo summary NCC)"

    @api.model
    def _get_report_values(self, docids, data=None):
        Summary = self.env["supplier.invoice.payment.summary"]
        Note = self.env["supplier.invoice.payment.summary.note"]

        today = date.today()

        docs = Summary.browse(docids).exists() if docids and docids != [0] else Summary.search([])

        done_domestic_labor = []
        done_domestic_material = []
        done_foreign = []

        pending_domestic_labor = []
        pending_domestic_material = []
        pending_foreign = []

        def _keep_line(rec):
            # giữ cả dòng có công nợ cũ
            return any([
                (rec.residual_amount or 0.0) != 0.0,
                (rec.advance_amount or 0.0) != 0.0,
                (rec.old_debt or 0.0) != 0.0,
            ])

        def _due_days_text(rec):
            if not rec.due_date or (rec.residual_amount or 0.0) <= 0.0:
                return ""
            delta = (rec.due_date - today).days
            if delta > 0:
                return f"Còn {delta} ngày từ {rec.due_date.strftime('%d/%m/%Y')}"
            elif delta == 0:
                return f"Đến hạn hôm nay - {rec.due_date.strftime('%d/%m/%Y')}"
            return f"Quá hạn {abs(delta)} ngày từ {rec.due_date.strftime('%d/%m/%Y')}"

        for rec in docs:
            if not _keep_line(rec):
                continue

            partner = rec.partner_id
            currency = rec.currency_id or self.env.company.currency_id

            note = Note.search([
                ("partner_id", "=", rec.partner_id.id),
                ("currency_id", "=", rec.currency_id.id),
            ], limit=1)

            supplier_category = (
                (note.supplier_category if note else False)
                or rec.supplier_category
                or "domestic"
            )

            supplier_domestic_type = (
                (note.supplier_domestic_type if note else False)
                or rec.supplier_domestic_type
                or False
            )

            reconciled = bool(
                (note.reconciled if note else False)
                if note else rec.reconciled
            )

            supply_category_name = ""
            if note and note.supply_category:
                supply_category_name = note.supply_category.name or ""
            elif rec.supply_category:
                supply_category_name = rec.supply_category.name or ""

            row = {
                "partner_id": partner.id if partner else False,
                "partner_name": partner.display_name if partner else "",
                "supply_category_name": supply_category_name,
                "contract_amount": rec.total_contract_amount or 0.0,
                "invoice_amount": rec.total_invoice_amount or 0.0,
                "paid_hd": rec.total_payment_amount or 0.0,
                "advance_amount": rec.advance_amount or 0.0,
                "old_debt": rec.old_debt or 0.0,
                "residual_amount": rec.residual_amount or 0.0,
                "due_days": _due_days_text(rec),
                "currency": currency,
                "supplier_category": supplier_category,
                "supplier_domestic_type": supplier_domestic_type,
                "reconciled": reconciled,
            }

            if supplier_category == "foreign":
                if reconciled:
                    done_foreign.append(row)
                else:
                    pending_foreign.append(row)
            else:
                if supplier_domestic_type == "labor":
                    if reconciled:
                        done_domestic_labor.append(row)
                    else:
                        pending_domestic_labor.append(row)
                else:
                    if reconciled:
                        done_domestic_material.append(row)
                    else:
                        pending_domestic_material.append(row)

        key_name = lambda l: (l.get("partner_name") or "").lower()

        done_domestic_labor = sorted(done_domestic_labor, key=key_name)
        done_domestic_material = sorted(done_domestic_material, key=key_name)
        done_foreign = sorted(done_foreign, key=key_name)

        pending_domestic_labor = sorted(pending_domestic_labor, key=key_name)
        pending_domestic_material = sorted(pending_domestic_material, key=key_name)
        pending_foreign = sorted(pending_foreign, key=key_name)

        return {
            "doc_ids": docs.ids,
            "doc_model": "supplier.invoice.payment.summary",
            "docs": docs,
            "done_domestic_labor": done_domestic_labor,
            "done_domestic_material": done_domestic_material,
            "done_foreign": done_foreign,
            "pending_domestic_labor": pending_domestic_labor,
            "pending_domestic_material": pending_domestic_material,
            "pending_foreign": pending_foreign,
        }