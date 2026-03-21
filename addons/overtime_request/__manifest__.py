{
    "name": "Overtime Request",
    "version": "17.0.1.0.0",
    "depends": ["base", "mail", "hr", "project", "custom_director_role", "project_work_from_so", "custom_quotation_content"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "security/overtime_rules.xml",
        "data/sequence.xml",
        "views/overtime_request_views.xml",
        "report/overtime_request_report.xml",
        "views/menus.xml",
    ],
"assets": {
    "web.assets_backend": [
        "overtime_request/static/src/js/time_dropdown_split_field.js",
        "overtime_request/static/src/xml/time_dropdown_split_field.xml",
        "overtime_request/static/src/scss/time_dropdown_split_field.scss",
    ],
},
    "application": True,
    "license": "LGPL-3",
}