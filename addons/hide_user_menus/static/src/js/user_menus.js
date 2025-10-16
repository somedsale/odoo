/** @odoo-module **/

import { UserMenu } from "@web/webclient/user_menu/user_menu";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const userMenuRegistry = registry.category("user_menuitems");

patch(UserMenu.prototype, {
    setup() {
        super.setup();

        // 🧹 Xóa menu mặc định
        userMenuRegistry.remove("documentation");
        userMenuRegistry.remove("support");
        userMenuRegistry.remove("shortcuts");
        userMenuRegistry.remove("separator");
        userMenuRegistry.remove("odoo_account");
        userMenuRegistry.add("user_settings", (env) => ({
            type: "item",
            description: _t("Cài đặt cá nhân"),
            sequence: 100,
            async callback() {
                const uid =
                    env.services.user?.userId ||
                    env.services.user?.id ||
                    env.services.session?.uid ||
                    (window.odoo?.session?.uid);

                if (!uid) {
                    console.warn("⚠️ Không xác định được user ID hiện tại");
                    return;
                }

                // 🔹 Gọi action custom (của bạn) và truyền res_id = uid
                await env.services.action.doAction("hide_user_menus.action_user_settings_my", {
                    additionalContext: {
                        active_id: uid,
                        active_ids: [uid],
                        uid,
                        from_my_profile: true,
                    },
                    props: {
                        res_id: uid,   // ✅ bắt buộc để form hiển thị record hiện tại
                    },
                });
            },
        }));
    },

});
