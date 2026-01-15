# -*- coding: utf-8 -*-
from odoo import api, fields, models
from collections import OrderedDict


class ReportPlannedPayment(models.AbstractModel):
    _name = "report.expense_proposal.report_planned_payment"
    _description = "QWeb Report: Planned Payment (Wizard only, group by Project then Vendor)"

    @api.model
    def _get_report_values(self, docids, data=None):
        today = fields.Date.context_today(self)
        company = self.env.company
        data = data or {}

        # --------------------------
        # Resolve wizard record
        # --------------------------
        Wizard = self.env["planned.payment.wizard"]

        # docids có thể là None / "0" / [0]...
        ids = []
        if docids:
            if isinstance(docids, str):
                ids = [int(x) for x in docids.split(",") if x.strip().isdigit()]
            else:
                try:
                    ids = [int(x) for x in docids if int(x)]
                except Exception:
                    ids = []
        # fallback theo context (trường hợp report_action không truyền docids như mong muốn)
        active_model = self.env.context.get("active_model")
        active_id = self.env.context.get("active_id")
        if not ids and active_model == "planned.payment.wizard" and active_id:
            ids = [int(active_id)]

        wizard = Wizard.browse(ids[:1]).exists() if ids else Wizard.browse([])

        # Nếu không có wizard => trả report rỗng để KHÔNG bị NoneType
        if not wizard:
            return {
                "doc_model": "planned.payment.wizard",
                "docs": Wizard.browse([]),
                "sections": [],
                "total": 0.0,
                "today": today,
                "company": company,
                "res_company": company,
            }

        # --------------------------
        # Build data from wizard lines (include=True)
        # --------------------------
        lines = wizard.line_ids.filtered("include")

        project_map = OrderedDict()

        def _ensure_project(project_name: str):
            if project_name not in project_map:
                project_map[project_name] = {
                    "project": project_name,
                    "total": 0.0,
                    "idx": 0,  # STT chạy liên tục trong dự án
                    "vendors": OrderedDict(),  # vendor_name -> {vendor,total,lines}
                }
            return project_map[project_name]

        def _ensure_vendor(sec, vendor_name: str):
            key = (vendor_name or "khác").strip() or "khác"
            if key not in sec["vendors"]:
                sec["vendors"][key] = {"vendor": key, "total": 0.0, "lines": []}
            return sec["vendors"][key]

        def _add(wline):
            project_name = wline.project_id.display_name if wline.project_id else "KHÔNG CÓ CÔNG TRÌNH"
            vendor_name = (wline.vendor_name or (wline.vendor_id.display_name if wline.vendor_id else "khác")) or "khác"

            sec = _ensure_project(project_name)
            vgrp = _ensure_vendor(sec, vendor_name)

            sec["idx"] += 1
            amount = wline.amount or 0.0

            row = {
                "stt": sec["idx"],
                "name": wline.name or "",
                "amount": amount,
                "note": wline.note or "",
                "date": wline.date,
            }

            vgrp["total"] += amount
            vgrp["lines"].append(row)
            sec["total"] += amount

        for l in lines:
            _add(l)

        sections = []
        for sec in project_map.values():
            sec["vendor_groups"] = list(sec["vendors"].values())
            sections.append(sec)

        total = sum(sec["total"] for sec in sections)

        return {
            "doc_model": "planned.payment.wizard",
            "docs": wizard,
            "sections": sections,
            "total": total,
            "today": today,
            "company": company,
            "res_company": company,
        }
