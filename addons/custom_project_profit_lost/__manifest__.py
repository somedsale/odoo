{
    'name': 'Project Profit Lost',
    'version': '1.0',
    'summary': 'Phân tích lời lỗ công trình',
    'depends': ['base','project','contract_management','custom_account_payment_request','custom_accounting_receipt'],  # thêm module bạn cần
    'data': [
        'security/ir.model.access.csv',
        'views/project_profit_lost_views.xml',
    ],
    "assets": {
        "web.assets_backend": [
            "custom_project_profit_lost/static/src/js/custom_render_tree.esm.js",
        ]
    },
    'installable': True,
    'application': False,
}
