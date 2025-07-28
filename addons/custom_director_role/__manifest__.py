{
    'name': 'Director Access Rights',
    'version': '1.0',
    'category': 'Users & Companies',
    'summary': 'Full access for Director like Administrator',
    'depends': ['base'],
    'data': [
        'security/director_security.xml',
        'security/ir.model.access.csv',
        # 'data/director_group.xml',
    ],
    'installable': True,
    'application': False,
}
