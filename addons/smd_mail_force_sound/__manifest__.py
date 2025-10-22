# -*- coding: utf-8 -*-
{
    "name": "Somed: Force Message Sound",
    "version": "17.0.1.0",
    "summary": "Luôn phát âm thanh khi có tin nhắn Discuss/Private (kể cả khi bật Desktop Notifications).",
    "category": "Discuss",
    "license": "LGPL-3",
    "depends": ["web", "mail","base"],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "smd_mail_force_sound/static/src/js/force_default_sound.js",
            "smd_mail_force_sound/static/src/audio/my_sound.mp3",
        ],
    },
}
