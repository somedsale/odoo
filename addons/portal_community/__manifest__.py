# -*- coding: utf-8 -*-
{
    "name": "Portal Community (Teams-like)",
    "version": "17.0.1.0.0",
    "category": "Tools",
    "summary": "Communities, channels, posts and comments (Teams-like)",
    "author": "You",
    "depends": ["base", "web"],
    "data": [
        "security/ir.model.access.csv",
        "security/portal_community_rules.xml",
        "views/portal_community_views.xml",
    ],
"assets": {
    "web.assets_backend": [
        "portal_community/static/src/js/communities_app.js",
        "portal_community/static/src/xml/communities_templates.xml",
        "portal_community/static/src/scss/communities.scss",
    ],
},


    "application": True,
    "installable": True,
}
