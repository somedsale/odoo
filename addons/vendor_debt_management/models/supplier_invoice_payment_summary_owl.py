# -*- coding: utf-8 -*-
from odoo import models
from collections import defaultdict


class SupplierInvoicePaymentSummaryOwl(models.Model):
    _inherit = "supplier.invoice.payment.summary"

    def action_open_owl_report(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "vendor_debt_management.supplier_debt_owl_report",
            "name": "Báo cáo công nợ NCC (OWL)",
            "context": {
                "active_id": self.id,
                "active_model": self._name,
            },
            "params": {
                "summary_id": self.id,
            },
        }

    def action_print_pdf_report(self):
        self.ensure_one()
        return self.env.ref(
            "vendor_debt_management.action_report_supplier_summary_pdf"
        ).report_action(self)

    def get_pdf_report_url(self):
        self.ensure_one()
        return "/report/pdf/vendor_debt_management.report_sup_summary_html/%s" % self.id
    # =========================
    # Helpers
    # =========================
    def _owl_get_payment_amount_field(self):
        Payment = self.env["account.payment.request"]
        if "total" in Payment._fields:
            return "total"
        for candidate in ["amount", "requested_amount", "amount_total", "paid_amount"]:
            if candidate in Payment._fields:
                return candidate
        return False

    def _owl_get_payment_amount(self, payment):
        amount_field = self._owl_get_payment_amount_field()
        if not amount_field:
            return 0.0
        return float(getattr(payment, amount_field, 0.0) or 0.0)

    def _owl_get_payment_date(self, payment):
        for field_name in ["date_payment", "payment_date", "date", "create_date"]:
            if field_name in payment._fields and getattr(payment, field_name, False):
                value = getattr(payment, field_name)
                return value.strftime("%Y-%m-%d")
        return False

    def _owl_get_invoice_date(self, invoice):
        for field_name in ["date", "invoice_date", "create_date"]:
            if field_name in invoice._fields and getattr(invoice, field_name, False):
                value = getattr(invoice, field_name)
                return value.strftime("%Y-%m-%d")
        return False

    def _owl_get_invoice_due_date(self, invoice):
        for field_name in ["due_date", "invoice_date_due"]:
            if field_name in invoice._fields and getattr(invoice, field_name, False):
                value = getattr(invoice, field_name)
                return value.strftime("%Y-%m-%d")
        return False

    def _owl_get_currency(self, record, fallback_currency):
        if "currency_id" in record._fields and record.currency_id:
            return record.currency_id
        return fallback_currency

    def _owl_invoice_display_name(self, invoice):
        return (
            getattr(invoice, "invoice_number", False)
            or getattr(invoice, "name", False)
            or getattr(invoice, "display_name", False)
            or "Không rõ số hóa đơn"
        )

    def _owl_contract_display_name(self, contract):
        return (
            getattr(contract, "name", False)
            or getattr(contract, "display_name", False)
            or "Không rõ hợp đồng"
        )

    def _owl_project_name(self, record):
        if "project_id" in record._fields and record.project_id:
            return record.project_id.name or ""
        return ""

    def _owl_status_from_residual(self, amount, residual):
        amount = float(amount or 0.0)
        residual = float(residual or 0.0)
        paid = amount - residual

        if amount <= 0:
            return "unknown"
        if residual <= 0:
            return "paid"
        if paid > 0:
            return "partial"
        return "unpaid"

    def _owl_build_invoice_payload(self, invoice, payments, summary_currency):
        currency = self._owl_get_currency(invoice, summary_currency)
        amount = float(getattr(invoice, "amount", 0.0) or 0.0)
        payment_total = sum(self._owl_get_payment_amount(p) for p in payments)
        residual = amount - payment_total
        due_date = self._owl_get_invoice_due_date(invoice)

        payment_items = []
        for payment in payments.sorted(
            key=lambda p: (
                self._owl_get_payment_date(p) or "",
                p.id,
            )
        ):
            payment_items.append({
                "id": payment.id,
                "name": getattr(payment, "name", False) or getattr(payment, "display_name", False) or "",
                "date": self._owl_get_payment_date(payment),
                "amount": self._owl_get_payment_amount(payment),
                "currency_id": currency.id if currency else False,
                "currency_symbol": currency.symbol if currency else "",
                "invoice_id": invoice.id,
                "has_invoice": True,
                "note": "",
            })

        return {
            "id": invoice.id,
            "name": self._owl_invoice_display_name(invoice),
            "date": self._owl_get_invoice_date(invoice),
            "due_date": due_date,
            "amount": amount,
            "payment_total": payment_total,
            "residual": residual,
            "status": self._owl_status_from_residual(amount, residual),
            "project_name": self._owl_project_name(invoice),
            "currency_id": currency.id if currency else False,
            "currency_symbol": currency.symbol if currency else "",
            "payments": payment_items,
        }

    def _owl_build_orphan_payment_payload(self, payment, summary_currency):
        currency = self._owl_get_currency(payment, summary_currency)
        return {
            "id": payment.id,
            "name": getattr(payment, "name", False) or getattr(payment, "display_name", False) or "",
            "date": self._owl_get_payment_date(payment),
            "amount": self._owl_get_payment_amount(payment),
            "currency_id": currency.id if currency else False,
            "currency_symbol": currency.symbol if currency else "",
            "invoice_id": False,
            "has_invoice": False,
            "note": "Không có hóa đơn",
        }

    def _owl_empty_section(self, key, title, section_type="contract"):
        return {
            "key": key,
            "type": section_type,
            "title": title,
            "project_name": "",
            "interpretation": "",
            "contract_name": "",
            "contract_date": False,
            "contract_amount": 0.0,
            "settlements_total": 0.0,
            "settlements": [],
            "invoice_total": 0.0,
            "payment_total": 0.0,
            "residual_total": 0.0,
            "currency_id": False,
            "currency_symbol": "",
            "invoices": [],
            "orphan_payments": [],
        }

    def get_owl_report_data(self):
        self.ensure_one()

        doc = self
        currency = doc.currency_id
        currency_symbol = currency.symbol if currency else ""

        all_invoices = doc.invoice_ids.sorted(
            key=lambda i: (
                (i.project_id.id if "project_id" in i._fields and i.project_id else 0),
                (i.contract_id.id if "contract_id" in i._fields and i.contract_id else 0),
                self._owl_get_invoice_date(i) or "",
                i.id,
            )
        )

        all_payments = doc.payment_request_ids.sorted(
            key=lambda p: (
                self._owl_get_payment_date(p) or "",
                p.id,
            )
        )

        payments_by_invoice = defaultdict(lambda: self.env["account.payment.request"])
        orphan_payments = self.env["account.payment.request"]

        for payment in all_payments:
            invoice = payment.invoice_id if "invoice_id" in payment._fields else False
            if invoice:
                payments_by_invoice[invoice.id] |= payment
            else:
                orphan_payments |= payment

        grouped_projects = {}

        def _get_project_bucket(project_id, project_name):
            key = str(project_id or 0)
            if key not in grouped_projects:
                grouped_projects[key] = {
                    "id": key,
                    "project_id": project_id or False,
                    "project_name": project_name or "Không có dự án",
                    "contracts": {},
                }
            return grouped_projects[key]

        def _get_contract_bucket(project_bucket, contract_id, contract_name, contract_date=False, interpretation="", contract_amount=0.0):
            key = str(contract_id or 0)
            if key not in project_bucket["contracts"]:
                project_bucket["contracts"][key] = {
                    "id": key,
                    "contract_id": contract_id or False,
                    "contract_name": contract_name or "Không có hợp đồng",
                    "contract_date": contract_date or False,
                    "interpretation": interpretation or "",
                    "contract_amount": float(contract_amount or 0.0),
                    "rows": [],
                    "invoice_total": 0.0,
                    "payment_total": 0.0,
                    "residual_total": 0.0,
                }
            return project_bucket["contracts"][key]

        def _append_row_to_bucket(bucket, row):
            bucket["rows"].append(row)
            if row.get("show_invoice"):
                bucket["invoice_total"] += float(row.get("invoice_amount") or 0.0)
            bucket["payment_total"] += float(row.get("payment_amount") or 0.0)
            if row.get("residual_display") not in (False, None) and row.get("show_invoice"):
                bucket["residual_total"] += float(row.get("residual_display") or 0.0)

        handled_invoice_ids = set()
        stt = 0

        def _append_invoice_rows(inv, contract=False, forced_project_name=""):
            nonlocal stt

            inv_currency = self._owl_get_currency(inv, currency)
            inv_currency_symbol = inv_currency.symbol if inv_currency else currency_symbol
            project = inv.project_id if "project_id" in inv._fields else False

            project_name = (
                contract.project_id.name
                if contract and "project_id" in contract._fields and contract.project_id
                else (project.name if project else forced_project_name or "Không có dự án")
            )
            project_id = (
                contract.project_id.id
                if contract and "project_id" in contract._fields and contract.project_id
                else (project.id if project else False)
            )

            contract_name = self._owl_contract_display_name(contract) if contract else "Không có hợp đồng"
            contract_id = contract.id if contract else False
            contract_date = (
                contract.contract_date.strftime("%Y-%m-%d")
                if contract and getattr(contract, "contract_date", False)
                else False
            )
            interpretation = getattr(contract, "interpretation", False) or "" if contract else ""
            contract_amount = float(getattr(contract, "amount", 0.0) or 0.0) if contract else 0.0

            project_bucket = _get_project_bucket(project_id, project_name)
            contract_bucket = _get_contract_bucket(
                project_bucket,
                contract_id,
                contract_name,
                contract_date,
                interpretation,
                contract_amount,
            )

            pay_lines = payments_by_invoice.get(inv.id, self.env["account.payment.request"]).sorted(
                key=lambda p: (self._owl_get_payment_date(p) or "", p.id)
            )

            inv_amount = float(getattr(inv, "amount", 0.0) or 0.0)

            if pay_lines:
                running_paid = 0.0
                for idx, pay in enumerate(pay_lines):
                    stt += 1
                    pay_amount = self._owl_get_payment_amount(pay)
                    running_paid += pay_amount
                    running_balance = inv_amount - running_paid

                    row = {
                        "id": f"row_{stt}",
                        "stt": stt,
                        "show_invoice": idx == 0,
                        "invoice_name": self._owl_invoice_display_name(inv),
                        "invoice_date": self._owl_get_invoice_date(inv),
                        "invoice_due_date": self._owl_get_invoice_due_date(inv),
                        "invoice_amount": inv_amount,
                        "payment_name": getattr(pay, "name", False) or getattr(pay, "display_name", False) or "",
                        "payment_date": self._owl_get_payment_date(pay),
                        "payment_amount": pay_amount,
                        "residual_display": running_balance,
                        "note": "",
                        "currency_symbol": inv_currency_symbol,
                    }
                    _append_row_to_bucket(contract_bucket, row)
            else:
                stt += 1
                row = {
                    "id": f"row_{stt}",
                    "stt": stt,
                    "show_invoice": True,
                    "invoice_name": self._owl_invoice_display_name(inv),
                    "invoice_date": self._owl_get_invoice_date(inv),
                    "invoice_due_date": self._owl_get_invoice_due_date(inv),
                    "invoice_amount": inv_amount,
                    "payment_name": "",
                    "payment_date": False,
                    "payment_amount": 0.0,
                    "residual_display": inv_amount,
                    "note": "",
                    "currency_symbol": inv_currency_symbol,
                }
                _append_row_to_bucket(contract_bucket, row)

        # 1) Invoice theo hợp đồng
        contract_ids = doc.contract_ids.sorted(key=lambda c: ((c.project_id.id or 0), c.id))
        for contract in contract_ids:
            contract_invoices = all_invoices.filtered(
                lambda i: (
                    "contract_id" in i._fields
                    and i.contract_id
                    and i.contract_id.id == contract.id
                )
            )
            for inv in contract_invoices:
                handled_invoice_ids.add(inv.id)
                _append_invoice_rows(inv, contract=contract)

        # 2) Invoice có dự án nhưng không hợp đồng
        proj_invoices = all_invoices.filtered(
            lambda i: (
                i.id not in handled_invoice_ids
                and (not getattr(i, "contract_id", False))
                and getattr(i, "project_id", False)
            )
        )
        for inv in proj_invoices:
            handled_invoice_ids.add(inv.id)
            _append_invoice_rows(inv, contract=False)

        # 3) Invoice không dự án / không hợp đồng
        orphan_invoices = all_invoices.filtered(lambda i: i.id not in handled_invoice_ids)
        for inv in orphan_invoices:
            _append_invoice_rows(inv, contract=False, forced_project_name="Không có dự án")

        # 4) Phiếu chi không có hóa đơn => nhét vào Không có dự án / Không có hợp đồng
        # 4) Phiếu chi không có hóa đơn
        if orphan_payments:
            for pay in orphan_payments.sorted(key=lambda p: (self._owl_get_payment_date(p) or "", p.id)):
                stt += 1
                pay_amount = self._owl_get_payment_amount(pay)
                pay_currency = self._owl_get_currency(pay, currency)
                pay_currency_symbol = pay_currency.symbol if pay_currency else currency_symbol

                # Ưu tiên xác định project / contract từ payment
                pay_contract = pay.contract_id if "contract_id" in pay._fields and pay.contract_id else False
                pay_project = False

                if pay_contract and "project_id" in pay_contract._fields and pay_contract.project_id:
                    pay_project = pay_contract.project_id
                elif "project_id" in pay._fields and pay.project_id:
                    pay_project = pay.project_id

                project_id = pay_project.id if pay_project else False
                project_name = pay_project.name if pay_project else "Không có dự án"

                contract_id = pay_contract.id if pay_contract else False
                contract_name = self._owl_contract_display_name(pay_contract) if pay_contract else "Không có hợp đồng"
                contract_date = (
                    pay_contract.contract_date.strftime("%Y-%m-%d")
                    if pay_contract and getattr(pay_contract, "contract_date", False)
                    else False
                )
                interpretation = getattr(pay_contract, "interpretation", False) or "" if pay_contract else ""
                contract_amount = float(getattr(pay_contract, "amount", 0.0) or 0.0) if pay_contract else 0.0

                project_bucket = _get_project_bucket(project_id, project_name)
                contract_bucket = _get_contract_bucket(
                    project_bucket,
                    contract_id,
                    contract_name,
                    contract_date,
                    interpretation,
                    contract_amount,
                )

                row = {
                    "id": f"row_{stt}",
                    "stt": stt,
                    "show_invoice": False,
                    "invoice_name": "",
                    "invoice_date": False,
                    "invoice_due_date": False,
                    "invoice_amount": 0.0,
                    "payment_name": getattr(pay, "name", False) or getattr(pay, "display_name", False) or "",
                    "payment_date": self._owl_get_payment_date(pay),
                    "payment_amount": pay_amount,
                    "residual_display": False,
                    "note": "Không có hóa đơn",
                    "currency_symbol": pay_currency_symbol,
                }
                _append_row_to_bucket(contract_bucket, row)

        projects = []
        for project_key, project_data in grouped_projects.items():
            contracts = list(project_data["contracts"].values())
            contracts.sort(key=lambda c: ((0 if c["contract_id"] else 1), c["contract_name"] or ""))
            project_data["contracts"] = contracts
            project_data["invoice_total"] = sum(c["invoice_total"] for c in contracts)
            project_data["payment_total"] = sum(c["payment_total"] for c in contracts)
            project_data["residual_total"] = sum(c["residual_total"] for c in contracts)
            projects.append(project_data)

        projects.sort(key=lambda p: (0 if p["project_id"] else 1, p["project_name"] or ""))

        summary = {
            "summary_id": doc.id,
            "partner_id": doc.partner_id.id if doc.partner_id else False,
            "partner_name": doc.partner_id.name if doc.partner_id else "",
            "currency_id": currency.id if currency else False,
            "currency_symbol": currency_symbol,
            "old_debt": float(doc.old_debt or 0.0),
            "total_contract_amount": float(doc.total_contract_amount or 0.0),
            "total_settlements_amount": float(doc.total_settlements_amount or 0.0),
            "total_invoice_amount": float(doc.total_invoice_amount or 0.0),
            "total_payment_amount": float(doc.total_payment_amount or 0.0),
            "residual_amount": float(doc.residual_amount or 0.0),
            "advance_amount": float(doc.advance_amount or 0.0),
            "due_date": doc.due_date.strftime("%Y-%m-%d") if doc.due_date else False,
            "due_days": doc.due_days or "",
            "note": doc.note or "",
            "interpretation": doc.interpretation or "",
            "reconciled": bool(doc.reconciled),
            "pdf_url": doc.get_pdf_report_url(),
        }

        return {
            "summary": summary,
            "projects": projects,
        }