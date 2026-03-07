{
    'name': 'Smart Avatars',
    'version': '17.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Auto-generate colorful avatars for contacts',
    'description': """
Smart Avatars
=============
Automatically generates professional, colorful avatars with initials for any contact that doesn't have an image.
Makes your Kanban views look lively and organized.
    """,
    'author': 'NEXERP PRIVATE LIMITED',
    'website': 'https://nexeerp.com',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [],
    'images': ['static/description/banner.png'],
    'external_dependencies': {
        'python': ['Pillow'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
