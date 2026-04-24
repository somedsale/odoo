/** @odoo-module */

import { registry } from "@web/core/registry";
import { session } from "@web/session";

const serviceRegistry = registry.category("services");

export const appLayoutService = {
    dependencies: ["menu", "orm"],

    async start(env, { menu, orm }) {
        let layout = null;
        let dirty = false;
        let loaded = false;

        function getInstalledApps() {
            return menu.getApps();
        }

        function buildDefaultLayout(apps) {
            return {
                showHint: true,
                pages: [
                    {
                        items: apps.map((app) => ({
                            type: "app",
                            appId: app.id,
                        })),
                    },
                ],
            };
        }

        function reconcile() {
            if (!layout) {
                return;
            }
            const installedApps = getInstalledApps();
            const installedIds = new Set(installedApps.map((a) => a.id));
            const layoutIds = new Set();

            for (const page of layout.pages) {
                page.items = page.items.filter((item) => {
                    if (item.type === "app") {
                        if (installedIds.has(item.appId)) {
                            layoutIds.add(item.appId);
                            return true;
                        }
                        return false;
                    }
                    if (item.type === "folder") {
                        // Filter uninstalled apps from folder
                        item.appIds = item.appIds.filter((id) => {
                            if (installedIds.has(id)) {
                                layoutIds.add(id);
                                return true;
                            }
                            return false;
                        });
                        // Empty folder → remove
                        if (item.appIds.length === 0) {
                            return false;
                        }
                        // Single-app folder → unwrap
                        if (item.appIds.length === 1) {
                            item.type = "app";
                            item.appId = item.appIds[0];
                            delete item.appIds;
                            delete item.name;
                            return true;
                        }
                        return true;
                    }
                    return true;
                });
            }

            // Remove empty pages
            layout.pages = layout.pages.filter((page) => page.items.length > 0);

            // Append new apps to last page
            const newApps = installedApps.filter((a) => !layoutIds.has(a.id));
            if (newApps.length > 0) {
                if (layout.pages.length === 0) {
                    layout.pages.push({ items: [] });
                }
                const lastPage = layout.pages[layout.pages.length - 1];
                for (const app of newApps) {
                    lastPage.items.push({ type: "app", appId: app.id });
                }
            }

            // Ensure at least one page exists
            if (layout.pages.length === 0) {
                layout.pages.push({ items: [] });
            }
        }

        async function loadLayout() {
            if (loaded) {
                return;
            }
            const result = await orm.read("res.users", [session.uid], ["ggg_app_layout"]);
            const raw = result && result[0] && result[0].ggg_app_layout;
            if (raw) {
                try {
                    layout = JSON.parse(raw);
                    dirty = false;
                } catch {
                    layout = null;
                }
            }
            if (!layout) {
                layout = buildDefaultLayout(getInstalledApps());
                dirty = false;
            }
            // Default showHint for legacy layouts
            if (layout.showHint === undefined) {
                layout.showHint = true;
            }
            reconcile();
            loaded = true;
        }

        function getPages(appsPerPage) {
            if (!layout) {
                return [];
            }
            if (!appsPerPage || appsPerPage <= 0) {
                return layout.pages;
            }
            const allItems = [];
            for (const page of layout.pages) {
                allItems.push(...page.items);
            }
            const displayPages = [];
            for (let i = 0; i < allItems.length; i += appsPerPage) {
                displayPages.push({
                    items: allItems.slice(i, i + appsPerPage),
                });
            }
            if (displayPages.length === 0) {
                displayPages.push({ items: [] });
            }
            return displayPages;
        }

        function moveApp(fromPage, fromIdx, toPage, toIdx) {
            if (!layout) {
                return;
            }
            const pages = layout.pages;
            if (fromPage < 0 || fromPage >= pages.length) {
                return;
            }
            if (toPage < 0 || toPage >= pages.length) {
                return;
            }
            const [item] = pages[fromPage].items.splice(fromIdx, 1);
            if (!item) {
                return;
            }
            pages[toPage].items.splice(toIdx, 0, item);

            layout.pages = pages.filter((p) => p.items.length > 0);
            if (layout.pages.length === 0) {
                layout.pages.push({ items: [] });
            }
            dirty = true;
        }

        function createFolder(pageIdx, targetIdx, draggedAppId, fromPage, fromIdx) {
            if (!layout) {
                return;
            }
            const pages = layout.pages;
            const targetItem = pages[pageIdx].items[targetIdx];
            if (!targetItem || targetItem.type !== "app") {
                return;
            }
            const targetAppId = targetItem.appId;

            // Remove dragged app from its original position first
            // Adjust indices if on the same page and dragged is before target
            let adjustedTargetIdx = targetIdx;
            if (fromPage === pageIdx && fromIdx < targetIdx) {
                adjustedTargetIdx--;
            }
            pages[fromPage].items.splice(fromIdx, 1);

            // Replace target with folder
            pages[pageIdx].items[adjustedTargetIdx] = {
                type: "folder",
                name: "Folder",
                appIds: [targetAppId, draggedAppId],
            };

            layout.pages = pages.filter((p) => p.items.length > 0);
            if (layout.pages.length === 0) {
                layout.pages.push({ items: [] });
            }
            dirty = true;
        }

        function deleteFolder(pageIdx, folderIdx) {
            if (!layout) {
                return;
            }
            const pages = layout.pages;
            const folder = pages[pageIdx].items[folderIdx];
            if (!folder || folder.type !== "folder") {
                return;
            }
            // Replace folder with its contained apps
            const appItems = folder.appIds.map((id) => ({ type: "app", appId: id }));
            pages[pageIdx].items.splice(folderIdx, 1, ...appItems);
            dirty = true;
        }

        function addAppToFolder(pageIdx, folderIdx, appId, fromPage, fromIdx) {
            if (!layout) {
                return;
            }
            const pages = layout.pages;
            const folder = pages[pageIdx].items[folderIdx];
            if (!folder || folder.type !== "folder") {
                return;
            }
            // Remove app from original position
            pages[fromPage].items.splice(fromIdx, 1);
            // Add to folder
            folder.appIds.push(appId);

            layout.pages = pages.filter((p) => p.items.length > 0);
            if (layout.pages.length === 0) {
                layout.pages.push({ items: [] });
            }
            dirty = true;
        }

        function removeAppFromFolder(pageIdx, folderIdx, appIdxInFolder, toPage, toIdx) {
            if (!layout) {
                return;
            }
            const pages = layout.pages;
            const folder = pages[pageIdx].items[folderIdx];
            if (!folder || folder.type !== "folder") {
                return;
            }
            const [appId] = folder.appIds.splice(appIdxInFolder, 1);
            if (appId === undefined) {
                return;
            }

            // Insert app at target position
            pages[toPage].items.splice(toIdx, 0, { type: "app", appId });

            // Auto-unwrap or delete folder
            if (folder.appIds.length === 0) {
                pages[pageIdx].items.splice(folderIdx, 1);
            } else if (folder.appIds.length === 1) {
                pages[pageIdx].items[folderIdx] = {
                    type: "app",
                    appId: folder.appIds[0],
                };
            }

            layout.pages = pages.filter((p) => p.items.length > 0);
            if (layout.pages.length === 0) {
                layout.pages.push({ items: [] });
            }
            dirty = true;
        }

        function renameFolder(pageIdx, folderIdx, newName) {
            if (!layout) {
                return;
            }
            const folder = layout.pages[pageIdx]?.items[folderIdx];
            if (!folder || folder.type !== "folder") {
                return;
            }
            if (!newName || !newName.trim()) {
                return;
            }
            folder.name = newName.trim();
            dirty = true;
        }

        function getFavoritesCollapsed() {
            return layout ? layout.favoritesCollapsed === true : false;
        }

        async function setFavoritesCollapsed(value) {
            if (!layout) {
                return;
            }
            layout.favoritesCollapsed = value;
            dirty = true;
            await saveLayout();
        }

        function getShowHint() {
            return layout ? layout.showHint !== false : true;
        }

        async function setShowHint(value) {
            if (!layout) {
                return;
            }
            layout.showHint = value;
            dirty = true;
            await saveLayout();
        }

        async function saveLayout() {
            if (!layout || !dirty) {
                return;
            }
            const json = JSON.stringify(layout);
            try {
                await orm.write("res.users", [session.uid], {
                    ggg_app_layout: json,
                });
                dirty = false;
            } catch {
                // Keep dirty flag so next save retries
            }
        }

        function getAppById(appId) {
            return getInstalledApps().find((a) => a.id === appId);
        }

        return {
            loadLayout,
            getPages,
            moveApp,
            saveLayout,
            getAppById,
            getInstalledApps,
            createFolder,
            deleteFolder,
            addAppToFolder,
            removeAppFromFolder,
            renameFolder,
            getFavoritesCollapsed,
            setFavoritesCollapsed,
            getShowHint,
            setShowHint,
        };
    },
};

serviceRegistry.add("ggg_app_layout", appLayoutService);
