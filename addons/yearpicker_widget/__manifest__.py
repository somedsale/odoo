{
    'name': 'YearPicker Widget',
    'version': '17.0.0.1',
    'summary': 'Widget for picking year',
    'description': 'Widget for picking year',
    'category': 'Tools',
    'author': 'Mark Nguyen',
    'company': "efact solutions",
    'maintainer': 'Mark Nguyen',
    'depends': ['base','web'],
    'assets': {
        'web.assets_backend': {
            # 'https://cdn.jsdelivr.net/npm/moment@2.29.4/min/moment.min.js',
            'yearpicker_widget/static/src/css/yearpicker_widget.css',
            'yearpicker_widget/static/lib/bootstrap-yearpicker.min.js',
            'yearpicker_widget/static/src/js/yearpicker_widget.js',
            'yearpicker_widget/static/src/xml/yearpicker_widget.xml',
        },
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
    'currency': 'USD',
    'price': '0',
    'images': [
        'static/description/main_screenshot.jpg'
    ],

}
