/** @odoo-module **/

import { registry } from "@web/core/registry";

function stableStringify(obj) {
    const allKeys = [];
    JSON.stringify(obj, (k, v) => (allKeys.push(k), v));
    allKeys.sort();
    return JSON.stringify(obj, allKeys);
}

export const futureProjectDashboardRepo = {
    name: "future_project_dashboard_repo",
    dependencies: ["orm"],
    start(env, { orm }) {
        const cache = new Map();
        const TTL_MS = 15 * 1000;

        function normalizePayload(payload) {
            const p = { ...(payload || {}) };

            // xoá key rỗng để backend dễ xử lý
            if (!p.location_id) delete p.location_id;
            if (!p.list_stage_id) delete p.list_stage_id;

            return p;
        }

        async function getDashboardData(payload, { force = false } = {}) {
            const norm = normalizePayload(payload);
            const key = stableStringify(norm);
            const now = Date.now();

            if (!force && cache.has(key)) {
                const hit = cache.get(key);
                if (now - hit.ts < TTL_MS) return hit.data;
            }

            const data = await orm.call("future.project", "get_dashboard_data", [norm]);
            cache.set(key, { ts: now, data });
            return data;
        }

        function clearCache() {
            cache.clear();
        }

        return {
            getDashboardData,
            clearCache,
        };
    },
};

// ✅ KEY PHẢI TRÙNG 100% với useService("future_project_dashboard_repo")
registry.category("services").add("future_project_dashboard_repo", futureProjectDashboardRepo);
