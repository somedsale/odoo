{
    'name': 'Dự toán chi phí đơn hàng',
    'version': '1.0',
    'depends': ['base', 'sale', 'project'],
    'summary': 'Quản lý dự toán chi phí cho đơn hàng',
    'data': [
        'security/ir.model.access.csv',
        'views/cost_estimate_menu.xml', 
        'views/cost_estimate_views.xml',   
    ],
    'installable': True,
    'application': True,
}
