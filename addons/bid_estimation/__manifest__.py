{
    'name': 'Bid Estimation',
    'version': '17.0.1.6.0',
    'category': 'Project',
    'summary': 'Import Excel dự toán dự thầu bằng OWL',
    'author': 'Somed',
    'depends': ['base', 'web', 'sale_management', 'project'],
    'data': [
        'security/ir.model.access.csv',
        'views/bid_estimation_views.xml',
        'views/bid_estimation_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bid_estimation/static/src/components/bid_project_list/bid_project_list.xml',
            'bid_estimation/static/src/components/bid_project_list/bid_project_list.js',
            'bid_estimation/static/src/components/bid_project_list/bid_project_list.scss',
            'bid_estimation/static/src/components/bid_import/bid_import.xml',
            'bid_estimation/static/src/components/bid_import/bid_import.js',
            'bid_estimation/static/src/components/bid_import/bid_import.scss',
            'bid_estimation/static/src/components/bid_project_view/bid_project_view.xml',
            'bid_estimation/static/src/components/bid_project_view/bid_project_view.js',
            'bid_estimation/static/src/components/bid_project_view/bid_project_view.scss',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
