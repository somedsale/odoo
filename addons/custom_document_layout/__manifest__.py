{
    'name': 'Custom Document Layout',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Custom layout for sale Document with logo and company info',
    'depends': ['sale', 'web'],
    'data': [
        'views/custom_document_layout.xml',
        'views/paperformat.xml',
    ],
    'installable': True,
    'application': False,
}