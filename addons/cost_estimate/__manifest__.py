{
    'name': 'Project Cost Estimate',
    'version': '1.0',
    'summary': 'Dự toán chi phí dự án',
    'category': 'Project',
    'depends': ['project', 'sale', 'project_material','contract_management'],
    'data': [
        'data/cost_estimate_sequence.xml',
        'security/ir.model.access.csv',
        'views/cost_estimate_views.xml',
        'views/project_expense_view.xml',
        'views/cost_additional_expense_line_views.xml',
        'wizard/cost_estimate_copy_cost_wizard_views.xml',
    ],
    'assets': {
    'web.assets_backend': [
        'cost_estimate/static/src/css/popup.css',
            "cost_estimate/static/src/cost_estimate_owl/cost_estimate_list.js",
            "cost_estimate/static/src/cost_estimate_owl/cost_estimate_list.xml",
            "cost_estimate/static/src/cost_estimate_owl/cost_estimate_list.scss",
    ],
},
    'installable': True,
    'application': False,
}
