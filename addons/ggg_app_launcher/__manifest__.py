{
    'name': 'GGG App Launcher',
    'version': '17.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Quick app launcher for fast navigation between Odoo modules',
    'description': '',
    'author': 'GGG',
    'website': 'https://gggsolution.com',
    'license': 'LGPL-3',
    'price': 0,
    'currency': 'EUR',
    'depends': [
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/ggg_favorite_rule.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ggg_app_launcher/static/src/webclient/**/*.js',
            'ggg_app_launcher/static/src/webclient/**/*.xml',
            'ggg_app_launcher/static/src/webclient/**/*.scss',
        ],
    },
    'images': [
        'static/description/screenshots/app_grid.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
