# -*- coding: utf-8 -*-
{
    "name": "Bank Balance",
    "version": "17.0.1.0.0",
    "category": "Accounting",
    "summary": "Tồn ngân hàng theo ngày cho nhiều ngân hàng (snapshot bank.daily.balance)",
    "depends": ["base", "account"],
    "data": [
        "security/ir.model.access.csv",
        "views/bank_balance_wizard_views.xml",
        "reports/bank_daily_balance_report.xml",
    ],
    "installable": True,
    "application": False,
}
