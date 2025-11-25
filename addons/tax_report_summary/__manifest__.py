# -*- coding: utf-8 -*-
{
    "name": "Tax Report Summary",
    "summary": "Báo cáo tổng hợp thuế đầu vào và đầu ra",
    "version": "1.0",
    "author": "Somed",
    "category": "Accounting",
    "depends": ["base", "mail", "project"],
"data": [
    "security/ir.model.access.csv",
    "wizard/tax_report_wizard_views.xml",
    "wizard/wizard_input_only_view.xml",
    "report/report_input_only_template.xml",
    "report/tax_report_templates.xml",
    "views/tax_report_menu.xml",          # 👈 thêm dòng này
],


    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
