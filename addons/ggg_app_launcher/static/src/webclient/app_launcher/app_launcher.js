/** @odoo-module */

import { Component, useState, useRef, onWillUnmount, onMounted } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";

const GESTURE_IDLE = "idle";
const GESTURE_PENDING = "pending";
const GESTURE_SWIPE = "swipe";
const GESTURE_DRAG = "drag";

const TAP_MAX_TIME = 200;
const TAP_MAX_MOVE = 10;
const SWIPE_MIN_DIST = 30;
const SWIPE_MAX_TIME = 300;
const DRAG_HOLD_TIME = 400;
const DRAG_MAX_MOVE = 10;
const DRAG_IMMEDIATE_MOVE = 5;
const DRAG_EDGE_ZONE = 50;
const DRAG_EDGE_DELAY = 500;
const FOLDER_DWELL_TIME = 300;

export class AppLauncher extends Component {
    static template = "ggg_app_launcher.AppLauncher";
    static props = {
        onClose: { type: Function },
        onAppSelect: { type: Function },
    };

    setup() {
        this.layoutService = useService("ggg_app_layout");
        this.menuService = useService("menu");
        this.orm = useService("orm");

        this.containerRef = useRef("pageContainer");
        this.overlayRef = useRef("overlay");

        this.state = useState({
            currentPage: 0,
            searchQuery: "",
            pages: [],
            totalPages: 0,
            // Gesture
            gestureState: GESTURE_IDLE,
            // Jiggle mode
            jiggleMode: false,
            // Drag
            dragging: false,
            dragAppId: null,
            dragX: 0,
            dragY: 0,
            dragOrigPage: 0,
            dragOrigIdx: 0,
            dropTargetPage: -1,
            dropTargetIdx: -1,
            // Folder creation zone
            folderZoneActive: false,
            folderZonePageIdx: -1,
            folderZoneItemIdx: -1,
            // Swipe
            swipeOffset: 0,
            // Folder popover
            openFolderPageIdx: -1,
            openFolderItemIdx: -1,
            folderPopoverBelow: true,
            // Folder rename
            renamingFolder: false,
            renameValue: "",
            // Folder edit mode (local to popover)
            popoverEditMode: false,
            // Hint
            showHint: true,
            // Favorites
            favorites: [],
            favoritesCollapsed: false,
            filteredFavorites: [],
            editingFavoriteId: null,
            editName: "",
            editUrl: "",
        });

        // Pointer tracking (not reactive)
        this._pointerStartX = 0;
        this._pointerStartY = 0;
        this._pointerStartTime = 0;
        this._pointerId = null;
        this._dragHoldTimer = null;
        this._dragEdgeTimer = null;
        this._folderDwellTimer = null;
        this._lastHoverTargetIdx = -1;
        this._draggingFromPopover = false;
        this._popoverDragFolderPage = -1;
        this._popoverDragFolderIdx = -1;
        this._popoverDragAppIdx = -1;
        this._appsPerPage = 18;

        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => {
            this.props.onClose();
        });

        onMounted(() => {
            this._loadAndRender();
            this._updateAppsPerPage();
            document.addEventListener("keydown", this._onKeyDown);
            window.addEventListener("resize", this._onResize);
        });

        onWillUnmount(() => {
            this._clearTimers();
            document.removeEventListener("keydown", this._onKeyDown);
            window.removeEventListener("resize", this._onResize);
        });
    }

    // -------------------------------------------------------------------------
    // Layout
    // -------------------------------------------------------------------------

    async _loadAndRender() {
        await this.layoutService.loadLayout();
        this.state.showHint = this.layoutService.getShowHint();
        this.state.favoritesCollapsed = this.layoutService.getFavoritesCollapsed();
        await this._loadFavorites();
        this._renderPages();
    }

    async _loadFavorites() {
        const records = await this.orm.searchRead(
            "ggg.favorite", [], ["name", "url", "sequence"],
            { order: "sequence, id" },
        );
        this.state.favorites = records;
    }

    _renderPages() {
        const query = this.state.searchQuery.trim().toLowerCase();
        if (query) {
            this._renderSearchResults(query);
        } else {
            this._renderNormalPages();
        }
    }

    _renderNormalPages() {
        this.state.filteredFavorites = [];
        const pages = this.layoutService.getPages(this._appsPerPage);
        const resolvedPages = pages.map((page) => ({
            items: page.items
                .map((item) => {
                    if (item.type === "app") {
                        const app = this.layoutService.getAppById(item.appId);
                        return app ? { ...item, app } : null;
                    }
                    if (item.type === "folder") {
                        // Resolve folder app previews
                        const resolvedApps = item.appIds
                            .map((id) => this.layoutService.getAppById(id))
                            .filter(Boolean);
                        return { ...item, resolvedApps };
                    }
                    return item;
                })
                .filter(Boolean),
        }));
        this.state.pages = resolvedPages;
        this.state.totalPages = resolvedPages.length;
        if (this.state.currentPage >= resolvedPages.length) {
            this.state.currentPage = Math.max(0, resolvedPages.length - 1);
        }
    }

    _renderSearchResults(query) {
        const apps = this.layoutService.getInstalledApps();
        const filtered = apps.filter((a) =>
            a.name.toLowerCase().includes(query)
        );
        this.state.pages = [
            {
                items: filtered.map((app) => ({
                    type: "app",
                    appId: app.id,
                    app,
                })),
            },
        ];
        this.state.totalPages = 1;

        // Filter favorites
        this.state.filteredFavorites = this.state.favorites.filter((f) =>
            f.name.toLowerCase().includes(query) ||
            f.url.toLowerCase().includes(query)
        );
    }

    _updateAppsPerPage() {
        const w = window.innerWidth;
        let cols, rows = 3;
        if (w < 576) {
            cols = 3;
        } else if (w < 992) {
            cols = 4;
        } else {
            cols = 6;
        }
        this._appsPerPage = cols * rows;
    }

    // -------------------------------------------------------------------------
    // Jiggle mode
    // -------------------------------------------------------------------------

    enterJiggleMode() {
        this.state.jiggleMode = true;
        this._closeFolderPopover();
    }

    exitJiggleMode() {
        this.state.jiggleMode = false;
        this._cancelDrag();
        this._closeFolderPopover();
    }

    onEditClick() {
        this.enterJiggleMode();
    }

    onDoneClick() {
        this.exitJiggleMode();
    }

    // -------------------------------------------------------------------------
    // Event handlers
    // -------------------------------------------------------------------------

    _onKeyDown = (ev) => {
        if (ev.key === "Escape") {
            if (this.state.dragging) {
                this._cancelDrag();
            } else if (this.state.openFolderPageIdx >= 0) {
                this._closeFolderPopover();
            } else if (this.state.jiggleMode) {
                this.exitJiggleMode();
            } else {
                this.props.onClose();
            }
            ev.preventDefault();
        }
    };

    _onResize = () => {
        const firstVisibleAppId = this._getFirstVisibleAppId();
        this._updateAppsPerPage();
        this._renderPages();
        if (firstVisibleAppId !== null && !this.state.searchQuery) {
            this._jumpToPageContaining(firstVisibleAppId);
        }
    };

    _getFirstVisibleAppId() {
        const page = this.state.pages[this.state.currentPage];
        if (page && page.items.length > 0) {
            const item = page.items[0];
            if (item.type === "app") {
                return item.appId;
            }
            if (item.type === "folder" && item.appIds && item.appIds.length > 0) {
                return item.appIds[0];
            }
        }
        return null;
    }

    _jumpToPageContaining(appId) {
        for (let i = 0; i < this.state.pages.length; i++) {
            const found = this.state.pages[i].items.some((item) => {
                if (item.type === "app") return item.appId === appId;
                if (item.type === "folder") return item.appIds?.includes(appId);
                return false;
            });
            if (found) {
                this.state.currentPage = i;
                return;
            }
        }
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value;
        this._closeFolderPopover();
        this._renderPages();
    }

    onClearSearch() {
        this.state.searchQuery = "";
        this._renderPages();
    }

    onAppClick(app) {
        if (this.state.dragging) {
            return;
        }
        if (this.state.jiggleMode) {
            this.exitJiggleMode();
        }

        this.env.bus.trigger("HOME_HERO:CLOSE");
        this.props.onAppSelect(app);
        this.props.onClose();
    }

    onFolderClick(pageIdx, itemIdx, ev) {
        if (this.state.dragging) {
            return;
        }
        // Position popover above or below based on click Y
        const below = ev.clientY < window.innerHeight / 2;
        this.state.openFolderPageIdx = pageIdx;
        this.state.openFolderItemIdx = itemIdx;
        this.state.folderPopoverBelow = below;
        this.state.renamingFolder = false;
    }

    _closeFolderPopover() {
        this.state.openFolderPageIdx = -1;
        this.state.openFolderItemIdx = -1;
        this.state.renamingFolder = false;
        this.state.popoverEditMode = false;
    }

    onPopoverBackdropClick() {
        this._closeFolderPopover();
    }

    onPopoverAppClick(app) {
        if (this.state.popoverEditMode || this.state.jiggleMode) {
            return;
        }

        this.env.bus.trigger("HOME_HERO:CLOSE");
        this._closeFolderPopover();
        this.props.onAppSelect(app);
        this.props.onClose();
    }

    // Folder rename
    onFolderNameClick() {
        const folder = this.openFolder;
        if (folder) {
            this.state.renamingFolder = true;
            this.state.renameValue = folder.name;
        }
    }

    onRenameInput(ev) {
        this.state.renameValue = ev.target.value;
    }

    onRenameKeydown(ev) {
        if (ev.key === "Enter") {
            this._commitRename();
        } else if (ev.key === "Escape") {
            this.state.renamingFolder = false;
            ev.stopPropagation();
        }
    }

    onRenameBlur() {
        this._commitRename();
    }

    _commitRename() {
        const { openFolderPageIdx, openFolderItemIdx, renameValue } = this.state;
        if (renameValue && renameValue.trim()) {
            this.layoutService.renameFolder(openFolderPageIdx, openFolderItemIdx, renameValue);
            this.layoutService.saveLayout();
            this._renderPages();
        }
        this.state.renamingFolder = false;
    }

    // Folder delete via badge
    onFolderDeleteBadge(pageIdx, itemIdx, ev) {
        ev.stopPropagation();
        this.layoutService.deleteFolder(pageIdx, itemIdx);
        this.layoutService.saveLayout();
        this._renderPages();

        const updatedItem = this.state.pages[this.state.openFolderPageIdx]?.items[this.state.openFolderItemIdx];
        if (!updatedItem || updatedItem.type !== "folder") {
            this._closeFolderPopover();
        }
    }

    // Remove app from folder via popover
    onPopoverRemoveApp(folderApp, folderAppIndex) {
        const { openFolderPageIdx, openFolderItemIdx } = this.state;
        const page = this.layoutService.getPages()[openFolderPageIdx];
        const toIdx = page ? page.items.length : 0;
        this.layoutService.removeAppFromFolder(
            openFolderPageIdx, openFolderItemIdx, folderAppIndex,
            openFolderPageIdx, toIdx
        );
        this.layoutService.saveLayout();
        this._renderPages();
        // Check if folder still exists after removal
        const updatedPage = this.state.pages[openFolderPageIdx];
        const updatedItem = updatedPage && updatedPage.items[openFolderItemIdx];
        if (!updatedItem || updatedItem.type !== "folder") {
            this._closeFolderPopover();
        }
    }

    // Popover drag-out
    onPopoverPointerDown(ev, folderApp, folderAppIndex) {
        ev.preventDefault();
        this._pointerId = ev.pointerId;
        this._pointerStartX = ev.clientX;
        this._pointerStartY = ev.clientY;
        this._pointerStartTime = Date.now();
        this._gestureItemId = folderApp.id;
        this._gestureItemType = "app";
        this._popoverDragFolderPage = this.state.openFolderPageIdx;
        this._popoverDragFolderIdx = this.state.openFolderItemIdx;
        this._popoverDragAppIdx = folderAppIndex;
        this.state.gestureState = GESTURE_PENDING;

        if (this.state.jiggleMode || this.state.popoverEditMode) {
            // Jiggle/popover edit mode: drag starts on move
            this._draggingFromPopover = true;
        } else {
            // Normal mode: long-press enters popover edit mode
            this._draggingFromPopover = false;
            this._dragHoldTimer = setTimeout(() => {
                if (this.state.gestureState === GESTURE_PENDING) {
                    this.state.popoverEditMode = true;
                    this.state.gestureState = GESTURE_IDLE;
                }
            }, DRAG_HOLD_TIME);
        }
    }

    // -------------------------------------------------------------------------
    // Favorites
    // -------------------------------------------------------------------------

    onFavoriteClick(favorite) {
        window.location.assign(favorite.url);
        this.props.onClose();
    }

    onToggleFavoritesCollapsed() {
        this.state.favoritesCollapsed = !this.state.favoritesCollapsed;
        this.layoutService.setFavoritesCollapsed(this.state.favoritesCollapsed);
    }

    async onDeleteFavorite(favorite, ev) {
        ev.stopPropagation();
        await this.orm.unlink("ggg.favorite", [favorite.id]);
        this.state.favorites = this.state.favorites.filter((f) => f.id !== favorite.id);
    }

    onEditFavorite(favorite, ev) {
        ev.stopPropagation();
        this.state.editingFavoriteId = favorite.id;
        this.state.editName = favorite.name;
        this.state.editUrl = favorite.url;
    }

    onEditNameInput(ev) {
        this.state.editName = ev.target.value;
    }

    onEditUrlInput(ev) {
        this.state.editUrl = ev.target.value;
    }

    async onEditSave(ev) {
        ev.stopPropagation();
        const name = this.state.editName.trim();
        const url = this.state.editUrl.trim();
        if (!name || !url) {
            return;
        }
        const id = this.state.editingFavoriteId;
        await this.orm.write("ggg.favorite", [id], { name, url });
        const fav = this.state.favorites.find((f) => f.id === id);
        if (fav) {
            fav.name = name;
            fav.url = url;
        }
        this.state.editingFavoriteId = null;
    }

    onEditCancel(ev) {
        ev.stopPropagation();
        this.state.editingFavoriteId = null;
    }

    onEditKeydown(ev) {
        if (ev.key === "Enter") {
            this.onEditSave(ev);
        } else if (ev.key === "Escape") {
            this.onEditCancel(ev);
            ev.stopPropagation();
        }
    }

    getAppIconForUrl(url) {
        // Odoo 17 uses /web#action=ID format
        const allMenus = this.menuService.getAll();
        // Extract action ID from URL hash (e.g., /web#action=123)
        let urlActionId = null;
        const hashIdx = url.indexOf("#");
        if (hashIdx >= 0) {
            const hash = url.substring(hashIdx + 1);
            const params = new URLSearchParams(hash);
            const actionStr = params.get("action");
            if (actionStr) {
                urlActionId = parseInt(actionStr, 10) || actionStr;
            }
        }
        if (!urlActionId) {
            return null;
        }
        // Find menu matching this action
        let bestMenu = null;
        for (const menu of allMenus) {
            if (menu.actionID && menu.actionID == urlActionId) {
                bestMenu = menu;
                break;
            }
        }
        if (bestMenu && bestMenu.appID) {
            return this.layoutService.getAppById(bestMenu.appID) || null;
        }
        return null;
    }

    get showFavoritesSection() {
        return this.state.favorites.length > 0 && !this.state.searchQuery;
    }

    // Hint
    onDismissHint() {
        this.state.showHint = false;
        this.layoutService.setShowHint(false);
    }

    onToggleHint() {
        const newValue = !this.state.showHint;
        this.state.showHint = newValue;
        this.layoutService.setShowHint(newValue);
    }

    onDotClick(pageIndex) {
        this._goToPage(pageIndex);
    }

    onOverlayClick(ev) {
        const el = ev.target;
        if (
            el === this.overlayRef.el ||
            el.classList.contains("ggg-launcher-content") ||
            el.classList.contains("ggg-favorites-section") ||
            el.classList.contains("ggg-favorites-table")
        ) {
            this.props.onClose();
        }
    }

    // -------------------------------------------------------------------------
    // Page navigation
    // -------------------------------------------------------------------------

    _goToPage(index) {
        if (index < 0 || index >= this.state.totalPages) {
            return;
        }
        this.state.currentPage = index;
        this.state.swipeOffset = 0;
    }

    _nextPage() {
        if (this.state.currentPage < this.state.totalPages - 1) {
            this._goToPage(this.state.currentPage + 1);
        }
    }

    _prevPage() {
        if (this.state.currentPage > 0) {
            this._goToPage(this.state.currentPage - 1);
        }
    }

    get pageContainerStyle() {
        const offset = -(this.state.currentPage * 100) + this.state.swipeOffset;
        const transition = this.state.gestureState === GESTURE_SWIPE ? "none" : "transform 0.3s ease";
        return `transform: translateX(${offset}%); transition: ${transition};`;
    }

    // -------------------------------------------------------------------------
    // Gesture state machine
    // -------------------------------------------------------------------------

    onPointerDown(ev, itemId, itemType, pageIdx, itemIdx) {
        if (this.state.searchQuery) {
            return;
        }
        this._pointerId = ev.pointerId;
        this._pointerStartX = ev.clientX;
        this._pointerStartY = ev.clientY;
        this._pointerStartTime = Date.now();
        this._gestureItemId = itemId;
        this._gestureItemType = itemType;
        this._gesturePageIdx = pageIdx;
        this._gestureItemIdx = itemIdx;
        this.state.gestureState = GESTURE_PENDING;

        if (this.state.jiggleMode) {
            // In jiggle mode: no hold timer, drag starts on move
        } else {
            // Normal mode: long-press enters jiggle
            this._dragHoldTimer = setTimeout(() => {
                if (this.state.gestureState === GESTURE_PENDING) {
                    this.enterJiggleMode();
                }
            }, DRAG_HOLD_TIME);
        }

        ev.target.setPointerCapture?.(ev.pointerId);
        ev.preventDefault();
    }

    onPointerDownEmpty(ev) {
        this._pointerId = ev.pointerId;
        this._pointerStartX = ev.clientX;
        this._pointerStartY = ev.clientY;
        this._pointerStartTime = Date.now();
        this._gestureItemId = null;
        this.state.gestureState = GESTURE_PENDING;
        ev.preventDefault();
    }

    onPointerMove(ev) {
        if (ev.pointerId !== this._pointerId) {
            return;
        }
        const dx = ev.clientX - this._pointerStartX;
        const dy = ev.clientY - this._pointerStartY;
        const absDx = Math.abs(dx);
        const absDy = Math.abs(dy);
        const elapsed = Date.now() - this._pointerStartTime;

        if (this.state.gestureState === GESTURE_PENDING) {
            // Check for swipe
            if (absDx > SWIPE_MIN_DIST && elapsed < SWIPE_MAX_TIME) {
                this._clearTimers();
                this.state.gestureState = GESTURE_SWIPE;
            }
            // In jiggle mode: immediate drag on small move (grid or popover)
            else if (this.state.jiggleMode && this._gestureItemId &&
                (absDx > DRAG_IMMEDIATE_MOVE || absDy > DRAG_IMMEDIATE_MOVE)) {
                this._clearTimers();
                if (this._draggingFromPopover) {
                    this._closeFolderPopover();
                }
                this._startDrag(ev.clientX, ev.clientY);
            }
            // Normal mode: any movement before hold completes → swipe
            else if (!this.state.jiggleMode && (absDx > DRAG_MAX_MOVE || absDy > DRAG_MAX_MOVE)) {
                this._clearTimers();
                this.state.gestureState = GESTURE_SWIPE;
            }
        }

        if (this.state.gestureState === GESTURE_SWIPE) {
            const containerWidth = this.containerRef.el?.offsetWidth || window.innerWidth;
            let pct = (dx / containerWidth) * 100;
            if (
                (this.state.currentPage === 0 && pct > 0) ||
                (this.state.currentPage === this.state.totalPages - 1 && pct < 0)
            ) {
                pct *= 0.3;
            }
            this.state.swipeOffset = pct;
        }

        if (this.state.gestureState === GESTURE_DRAG || this.state.dragging) {
            this.state.dragX = ev.clientX;
            this.state.dragY = ev.clientY;
            this._updateDropTarget(ev.clientX, ev.clientY);
            this._checkEdgeScroll(ev.clientX);
            this._checkFolderDwell(ev.clientX, ev.clientY);
        }
    }

    onPointerUp(ev) {
        if (ev.pointerId !== this._pointerId) {
            return;
        }
        const dx = ev.clientX - this._pointerStartX;
        const absDx = Math.abs(dx);
        const elapsed = Date.now() - this._pointerStartTime;

        if (this.state.gestureState === GESTURE_PENDING) {
            this._clearTimers();
            if (elapsed < TAP_MAX_TIME && absDx < TAP_MAX_MOVE) {
                if (this._gestureItemId) {
                    if (this._gestureItemType === "folder") {
                        // Tap on folder in normal mode opens popover
                        // In jiggle mode, tap on folder also opens popover
                        this.onFolderClick(this._gesturePageIdx, this._gestureItemIdx, ev);
                    } else {
                        const app = this.layoutService.getAppById(this._gestureItemId);
                        if (app) {
                            this.onAppClick(app);
                        }
                    }
                } else if (this.state.jiggleMode) {
                    this.exitJiggleMode();
                    this.layoutService.saveLayout();
                } else {
                    this.props.onClose();
                }
            }
        } else if (this.state.gestureState === GESTURE_SWIPE) {
            const threshold = 15;
            if (this.state.swipeOffset < -threshold && this.state.currentPage < this.state.totalPages - 1) {
                this._nextPage();
            } else if (this.state.swipeOffset > threshold && this.state.currentPage > 0) {
                this._prevPage();
            }
            this.state.swipeOffset = 0;
        } else if (this.state.dragging) {
            this._completeDrag();
        }

        this.state.gestureState = GESTURE_IDLE;
        this._pointerId = null;
        this._clearTimers();
    }

    // -------------------------------------------------------------------------
    // Drag-to-reorder
    // -------------------------------------------------------------------------

    _startDrag(x, y) {
        this.state.gestureState = GESTURE_DRAG;
        this.state.dragging = true;
        this.state.dragAppId = this._gestureItemId;
        this.state.dragX = x;
        this.state.dragY = y;
        this.state.dragOrigPage = this._gesturePageIdx;
        this.state.dragOrigIdx = this._gestureItemIdx;
        this.state.dropTargetPage = this._gesturePageIdx;
        this.state.dropTargetIdx = this._gestureItemIdx;
        this.state.folderZoneActive = false;
    }

    _updateDropTarget(x, y) {
        const container = this.containerRef.el;
        if (!container) {
            return;
        }
        const pageEl = container.querySelector(`.ggg-app-page[data-page="${this.state.currentPage}"]`);
        if (!pageEl) {
            return;
        }
        const icons = pageEl.querySelectorAll(".ggg-app-icon-wrapper");
        let closestIdx = 0;
        let closestDist = Infinity;

        icons.forEach((icon, idx) => {
            const rect = icon.getBoundingClientRect();
            const cx = rect.left + rect.width / 2;
            const cy = rect.top + rect.height / 2;
            const dist = Math.hypot(x - cx, y - cy);
            if (dist < closestDist) {
                closestDist = dist;
                closestIdx = idx;
            }
        });

        this.state.dropTargetPage = this.state.currentPage;
        this.state.dropTargetIdx = closestIdx;
    }

    _checkFolderDwell(x, y) {
        // Check if hovering over an app icon (not folder) for folder creation
        if (!this.state.jiggleMode || !this.state.dragging) {
            return;
        }
        const container = this.containerRef.el;
        if (!container) {
            return;
        }
        const pageEl = container.querySelector(`.ggg-app-page[data-page="${this.state.currentPage}"]`);
        if (!pageEl) {
            return;
        }
        const icons = pageEl.querySelectorAll(".ggg-app-icon-wrapper");
        let hoverIdx = -1;

        icons.forEach((icon, idx) => {
            const rect = icon.getBoundingClientRect();
            if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
                hoverIdx = idx;
            }
        });

        // Check if hovering over a different item than the dragged one
        const page = this.state.pages[this.state.currentPage];
        if (hoverIdx >= 0 && page) {
            const hoverItem = page.items[hoverIdx];
            if (hoverItem && hoverItem.appId !== this.state.dragAppId) {
                if (this._lastHoverTargetIdx !== hoverIdx) {
                    this._lastHoverTargetIdx = hoverIdx;
                    this._clearFolderDwell();
                    this._folderDwellTimer = setTimeout(() => {
                        this.state.folderZoneActive = true;
                        this.state.folderZonePageIdx = this.state.currentPage;
                        this.state.folderZoneItemIdx = hoverIdx;
                    }, FOLDER_DWELL_TIME);
                }
                return;
            }
        }
        // Not hovering over valid target
        if (this._lastHoverTargetIdx !== -1) {
            this._lastHoverTargetIdx = -1;
            this._clearFolderDwell();
            this.state.folderZoneActive = false;
        }
    }

    _checkEdgeScroll(x) {
        const w = window.innerWidth;
        if (x < DRAG_EDGE_ZONE && this.state.currentPage > 0) {
            if (!this._dragEdgeTimer) {
                this._dragEdgeTimer = setTimeout(() => {
                    this._prevPage();
                    this._dragEdgeTimer = null;
                }, DRAG_EDGE_DELAY);
            }
        } else if (x > w - DRAG_EDGE_ZONE && this.state.currentPage < this.state.totalPages - 1) {
            if (!this._dragEdgeTimer) {
                this._dragEdgeTimer = setTimeout(() => {
                    this._nextPage();
                    this._dragEdgeTimer = null;
                }, DRAG_EDGE_DELAY);
            }
        } else {
            if (this._dragEdgeTimer) {
                clearTimeout(this._dragEdgeTimer);
                this._dragEdgeTimer = null;
            }
        }
    }

    _completeDrag() {
        const { dragOrigPage, dragOrigIdx, dropTargetPage, dropTargetIdx } = this.state;

        if (this._draggingFromPopover) {
            // Dragging app out of folder popover
            this.layoutService.removeAppFromFolder(
                this._popoverDragFolderPage, this._popoverDragFolderIdx,
                this._popoverDragAppIdx, dropTargetPage, dropTargetIdx
            );
            this.layoutService.saveLayout();
            this._draggingFromPopover = false;
            this._popoverDragFolderPage = -1;
            this._popoverDragFolderIdx = -1;
            this._popoverDragAppIdx = -1;
            this.state.dragging = false;
            this.state.dragAppId = null;
            this.state.folderZoneActive = false;
            this._lastHoverTargetIdx = -1;
            this._renderPages();
            return;
        }

        if (this.state.folderZoneActive) {
            // Drop on folder creation zone or existing folder
            const targetPage = this.state.pages[this.state.folderZonePageIdx];
            const targetItem = targetPage?.items[this.state.folderZoneItemIdx];
            if (targetItem?.type === "folder") {
                this.layoutService.addAppToFolder(
                    this.state.folderZonePageIdx, this.state.folderZoneItemIdx,
                    this.state.dragAppId, dragOrigPage, dragOrigIdx
                );
            } else {
                this.layoutService.createFolder(
                    this.state.folderZonePageIdx, this.state.folderZoneItemIdx,
                    this.state.dragAppId, dragOrigPage, dragOrigIdx
                );
            }
            this.layoutService.saveLayout();
        } else if (dragOrigPage !== dropTargetPage || dragOrigIdx !== dropTargetIdx) {
            this.layoutService.moveApp(dragOrigPage, dragOrigIdx, dropTargetPage, dropTargetIdx);
            this.layoutService.saveLayout();
        }

        this.state.dragging = false;
        this.state.dragAppId = null;
        this.state.folderZoneActive = false;
        this._lastHoverTargetIdx = -1;
        this._renderPages();
    }

    _cancelDrag() {
        this.state.dragging = false;
        this.state.dragAppId = null;
        this.state.gestureState = GESTURE_IDLE;
        this.state.folderZoneActive = false;
        this._lastHoverTargetIdx = -1;
        this._draggingFromPopover = false;
        this._popoverDragFolderPage = -1;
        this._popoverDragFolderIdx = -1;
        this._popoverDragAppIdx = -1;
        this._clearTimers();
    }

    // -------------------------------------------------------------------------
    // Utilities
    // -------------------------------------------------------------------------

    _clearTimers() {
        if (this._dragHoldTimer) {
            clearTimeout(this._dragHoldTimer);
            this._dragHoldTimer = null;
        }
        if (this._dragEdgeTimer) {
            clearTimeout(this._dragEdgeTimer);
            this._dragEdgeTimer = null;
        }
        this._clearFolderDwell();
    }

    _clearFolderDwell() {
        if (this._folderDwellTimer) {
            clearTimeout(this._folderDwellTimer);
            this._folderDwellTimer = null;
        }
    }

    isDraggedItem(appId) {
        return this.state.dragging && this.state.dragAppId === appId;
    }

    isDropTarget(pageIdx, itemIdx) {
        return (
            this.state.dragging &&
            !this.state.folderZoneActive &&
            this.state.dropTargetPage === pageIdx &&
            this.state.dropTargetIdx === itemIdx
        );
    }

    isFolderZone(pageIdx, itemIdx) {
        return (
            this.state.folderZoneActive &&
            this.state.folderZonePageIdx === pageIdx &&
            this.state.folderZoneItemIdx === itemIdx
        );
    }

    get dragStyle() {
        if (!this.state.dragging) {
            return "";
        }
        return `left: ${this.state.dragX}px; top: ${this.state.dragY}px;`;
    }

    get draggedApp() {
        if (!this.state.dragAppId) {
            return null;
        }
        return this.layoutService.getAppById(this.state.dragAppId);
    }

    get showDots() {
        return !this.state.searchQuery && this.state.totalPages > 1;
    }

    get dotPages() {
        return Array.from({ length: this.state.totalPages }, (_, i) => i);
    }

    get openFolder() {
        const { openFolderPageIdx, openFolderItemIdx } = this.state;
        if (openFolderPageIdx < 0) {
            return null;
        }
        const page = this.state.pages[openFolderPageIdx];
        if (!page) {
            return null;
        }
        return page.items[openFolderItemIdx] || null;
    }

    get hintText() {
        if (this.state.jiggleMode) {
            return "Drag to reorder \u00B7 Drop on another to folder \u00B7 Press Done to finish";
        }
        return "Hold an app to rearrange";
    }

    get showHintBar() {
        return (
            this.state.showHint &&
            !this.state.searchQuery
        );
    }

    getAppIconSrc(app) {
        if (!app) {
            return "";
        }
        const data = app.webIconData;
        if (data) {
            if (data.startsWith("data:") || data.startsWith("/")) {
                return data;
            }
            // Raw base64 — build data URI
            const mime = app.webIconDataMimetype || "image/png";
            return `data:${mime};base64,${data}`;
        }
        return "/base/static/description/icon.png";
    }

    getFolderPreviewApps(item) {
        if (!item.resolvedApps) {
            return [];
        }
        // Return first 4 apps for 2x2 preview
        const apps = item.resolvedApps.slice(0, 4);
        // Pad to 4 with nulls for empty slots
        while (apps.length < 4) {
            apps.push(null);
        }
        return apps;
    }
}
