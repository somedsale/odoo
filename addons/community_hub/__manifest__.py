# -*- coding: utf-8 -*-
{
    "name": "Community Hub (Owl + Realtime)",
    "version": "17.0.1.0.0",
    "category": "Productivity",
    "summary": "Communities with channels, posts, comments, reactions - Owl dashboard realtime like Discuss",
    "depends": ["base", "web", "mail", "bus", "web_editor"],
    "data": [
        "security/ir.model.access.csv",
        "security/community_hub_rules.xml",
        "views/community_views.xml",
        "views/menu.xml",
        # "views/assets.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "community_hub/static/src/client_action/community_hub.xml",
            "community_hub/static/src/client_action/community_hub.scss",
            # "community_hub/static/src/patches/action_service_hub_redirect.js",
            "community_hub/static/src/patches/hub_redirect_all.js",
            "community_hub/static/src/js/community_hub_desktop_notification_patch.js",
            'community_hub/static/src/js/community_hub_desktop_notify.js',
            'community_hub/static/src/js/skip_mail_desktop_notify.js',
            'community_hub/static/src/js/kill_mail_desktop_notify_for_hub.js',
            "community_hub/static/src/client_action/api.js",
            "community_hub/static/src/client_action/app.js",
        ],
        "mail.assets_discuss": [
        "community_hub/static/src/patches/hub_redirect_all.js",
    ],
    },

    "application": True,
    "installable": True,
    "license": "LGPL-3",
}
