# -*- coding: utf-8 -*-
from odoo import api, models, fields
from collections import OrderedDict
from datetime import datetime


class ReportPlannedPayment(models.AbstractModel):
    _name = "report.expense_proposal.report_planned_payment"
    _description = "QWeb Report: Planned Payment - Group by Project then Vendor (Expenses + PO lines)"

    # DỰ KIẾN THANH TOÁN: PO chưa đặt + đang giao
    PLANNED_PO_STATUSES = ("in_progress", "not_shipped")

    @api.model
    def _get_report_values(self, docids, data=None):
        today = fields.Date.context_today(self)
        company = self.env.company

        ProposalSheet = self.env["proposal.sheet"]
        PurchaseLine = self.env["purchase.order.line"]

        # 1) Chi phí từ phiếu đề xuất
        sheets = ProposalSheet.search([
            ("type", "in", ["expense"]),
            ("state", "=", "waiting_accounting_paid"),
        ], order="project_id, date_proposal, id")

        # 2) Vật tư từ PO line: chỉ cần PO có project_id
        po_domain = [
            ("display_type", "=", False),
            ("order_id.state", "!=", "cancel"),
            ("order_id.company_id", "=", company.id),
            ("order_id.shipping_status", "in", list(self.PLANNED_PO_STATUSES)),
        ]
        po_lines = PurchaseLine.search(po_domain, order="order_id, id")

        # Sort đẹp theo project/date ở Python (tránh order related field)
        epoch = datetime(1970, 1, 1)

        def _po_sort_key(l):
            proj = getattr(l.order_id, "project_id", False)
            proj_id = proj.id if proj else 0
            date = l.order_id.date_order or epoch
            return (proj_id, date, l.order_id.id, l.id)

        po_lines = po_lines.sorted(_po_sort_key)

        # ========= helpers =========
        def _get_amount(line):
            if hasattr(line, "amount"):
                return line.amount or 0.0
            if hasattr(line, "price_total"):
                return line.price_total or 0.0
            if hasattr(line, "price_subtotal"):
                return line.price_subtotal or 0.0
            qty = getattr(line, "product_qty", 0.0) or getattr(line, "quantity", 0.0) or 0.0
            pu = getattr(line, "price_unit", 0.0) or 0.0
            return qty * pu

        def _get_vendor_name(line):
            # proposal line
            if getattr(line, "object", False):
                return (line.object.name or "").strip() or "khác"
            if getattr(line, "vendor_id", False):
                return (line.vendor_id.display_name or "").strip() or "khác"
            if getattr(line, "partner_id", False):
                return (line.partner_id.display_name or "").strip() or "khác"
            # PO line
            if getattr(line, "order_id", False) and getattr(line.order_id, "partner_id", False):
                return (line.order_id.partner_id.display_name or "").strip() or "khác"
            return "khác"

        def _get_line_name(line):
            if getattr(line, "content", False):
                return line.content or ""
            if getattr(line, "expense_id", False):
                return line.expense_id.display_name or ""
            if getattr(line, "name", False):
                return line.name or ""
            return ""

        def _get_note(line):
            note = getattr(line, "note", "") or ""
            if getattr(line, "order_id", False) and getattr(line.order_id, "name", False):
                note = f"{note} | {line.order_id.name}" if note else line.order_id.name
            return note

        def _get_date(line):
            date = getattr(line, "date", False)
            if date:
                return date
            if getattr(line, "order_id", False) and getattr(line.order_id, "date_order", False):
                return line.order_id.date_order.date()
            return False

        # ========== GROUP: Project -> Vendor ==========
        project_map = OrderedDict()

        def _ensure_project(project_name):
            if project_name not in project_map:
                project_map[project_name] = {
                    "project": project_name,
                    "total": 0.0,
                    "idx": 0,                  # STT chạy liên tục trong dự án
                    "vendors": OrderedDict(),  # vendor_name -> {vendor,total,lines}
                }
            return project_map[project_name]

        def _ensure_vendor(sec, vendor_name):
            key = (vendor_name or "khác").strip() or "khác"
            if key not in sec["vendors"]:
                sec["vendors"][key] = {"vendor": key, "total": 0.0, "lines": []}
            return sec["vendors"][key]

        def _add(project_name, line):
            sec = _ensure_project(project_name)
            vendor_name = _get_vendor_name(line)
            vgrp = _ensure_vendor(sec, vendor_name)

            sec["idx"] += 1
            amount = _get_amount(line)

            row = {
                "stt": sec["idx"],
                "name": _get_line_name(line),
                "amount": amount,
                "note": _get_note(line),
                "date": _get_date(line),
            }

            vgrp["total"] += amount
            vgrp["lines"].append(row)
            sec["total"] += amount

        # A) Chi phí theo project từ proposal.sheet
        for s in sheets:
            project_name = s.project_id.display_name if s.project_id else "KHÔNG CÓ CÔNG TRÌNH"
            for l in s.expense_noproject_line_ids:
                _add(project_name, l)
            for l in s.expense_line_ids:
                _add(project_name, l)

        # B) Vật tư theo project từ PO line
        for pol in po_lines:
            po_project = getattr(pol.order_id, "project_id", False)
            project_name = po_project.display_name if po_project else "KHÔNG CÓ CÔNG TRÌNH"
            _add(project_name, pol)

        # build sections list cho template
        sections = []
        for sec in project_map.values():
            sec["vendor_groups"] = list(sec["vendors"].values())
            sections.append(sec)

        total = sum(sec["total"] for sec in sections)

        return {
            "doc_model": "proposal.sheet",
            "docs": sheets,
            "sections": sections,
            "total": total,
            "today": today,
            "company": company,
            "res_company": company,
        }
