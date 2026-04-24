{
    # App information
    'name': 'Column Reorder',
    'version': '17.0.1.0.0',
    'summary': 'Allow users to reorder list view columns from the backend UI.',
    'description': 'Column Reorder lets backend users drag and reorder columns in Odoo list views. The selected order is remembered per view in the browser, giving users a more flexible and personalized list-view layout experience.',
    'category': 'Tools',
    'license': 'LGPL-3',

    # Author
    'author': 'Techno Stellar',
    'maintainer': 'Techno Stellar',

    # Dependencies
    'depends': ['web'],

    # Views & Data
    'assets': {
        'web.assets_backend': [
            'column_reorder_tspl/static/src/js/list_renderer_patch.js',
            'column_reorder_tspl/static/src/xml/list_renderer.xml',
            'column_reorder_tspl/static/src/scss/list_renderer.scss',
        ],
    },

    # Technical
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
