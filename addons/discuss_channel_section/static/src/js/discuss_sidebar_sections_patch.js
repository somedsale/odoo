/** @odoo-module **/

import { DiscussSidebarCategories } from "@mail/discuss/core/web/discuss_sidebar_categories";
import { cleanTerm } from "@mail/utils/common/format";
import { onWillStart } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(DiscussSidebarCategories.prototype, {
    setup() {
        super.setup(...arguments);

        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state.sections = [];
        this.state.sectionsLoading = false;

        this.state.bulkSelecting = false;
        this.state.selectedThreadIds = [];
        this.state.bulkTargetSectionId = "";

        this.state.dragging = {
            active: false,
            threadIds: [],
            overSectionId: "",
            overThreadId: "",
            dropPosition: "",
        };

        onWillStart(async () => {
            await this.loadSidebarSections();
        });
    },

    async loadSidebarSections() {
        this.state.sectionsLoading = true;
        try {
            const sections = await this.orm.call(
                "discuss.sidebar.section",
                "get_my_sections",
                []
            );
            this.state.sections = sections || [];

            if (this.state.bulkSelecting && !this.hasUnsectionedChannels) {
                this.state.bulkSelecting = false;
                this.state.selectedThreadIds = [];
                this.state.bulkTargetSectionId = "";
            }
        } catch (e) {
            console.error("Failed to load sidebar sections", e);
            this.state.sections = [];
        } finally {
            this.state.sectionsLoading = false;
        }
    },

    _getThreadChannelId(thread) {
        return String(
            thread?.id ??
            thread?.resId ??
            thread?.channel_id ??
            thread?.channel?.id ??
            ""
        );
    },

    _normalizeThreads(raw) {
        return Array.isArray(raw) ? raw : Object.values(raw || {});
    },

    _getAllChannelThreads() {
        const threads = this._normalizeThreads(this.store?.Thread?.records);
        return threads.filter((thread) => {
            return (
                thread &&
                thread.model === "discuss.channel" &&
                (
                    thread.displayToSelf ||
                    thread.isLocallyPinned ||
                    thread.type === "channel" ||
                    thread.type === "group" ||
                    thread.channel_type === "channel" ||
                    thread.channel_type === "group"
                )
            );
        });
    },

    _getCurrentUnsectionedChannelThreads() {
        const threads = this._getAllChannelThreads();
        const map = this.sectionMap;

        return threads.filter((thread) => {
            return (
                !map[this._getThreadChannelId(thread)] &&
                (!this.state.quickSearchVal ||
                    cleanTerm(thread.displayName || "").includes(
                        cleanTerm(this.state.quickSearchVal || "")
                    ))
            );
        });
    },

    get hasUnsectionedChannels() {
        return this._getCurrentUnsectionedChannelThreads().length > 0;
    },

    get sectionMap() {
        const map = {};
        for (const section of this.state.sections || []) {
            for (const channelId of section.channel_ids || []) {
                map[String(channelId)] = section.id;
            }
        }
        return map;
    },

    get sidebarSectionsWithThreads() {
        const channels = this._getAllChannelThreads();

        return (this.state.sections || []).map((section) => {
            const ids = new Set((section.channel_ids || []).map((id) => String(id)));
            const matchedThreads = channels.filter((thread) =>
                ids.has(this._getThreadChannelId(thread))
            );

            return {
                ...section,
                threads: matchedThreads,
            };
        });
    },

    filteredThreads(category) {
        const threads = this._normalizeThreads(category?.threads);

        let result = threads.filter((thread) => {
            return (
                (thread.displayToSelf || thread.isLocallyPinned) &&
                (!this.state.quickSearchVal ||
                    cleanTerm(thread.displayName || "").includes(
                        cleanTerm(this.state.quickSearchVal || "")
                    ))
            );
        });

        if (category?.id === "channels") {
            const map = this.sectionMap;
            result = result.filter((thread) => !map[this._getThreadChannelId(thread)]);
        }
        return result;
    },

    async onCreateSection() {
        const name = window.prompt("Nhập tên section");
        if (!name || !name.trim()) {
            return;
        }
        try {
            await this.orm.call(
                "discuss.sidebar.section",
                "create_section",
                [name.trim()]
            );
            await this.loadSidebarSections();
            this.notification?.add?.("Đã tạo section", { type: "success" });
        } catch (e) {
            console.error(e);
            this.notification?.add?.("Không tạo được section", { type: "danger" });
        }
    },

    async onRenameSection(section) {
        const name = window.prompt("Đổi tên section", section.name || "");
        if (!name || !name.trim()) {
            return;
        }
        try {
            await this.orm.call(
                "discuss.sidebar.section",
                "rename_section",
                [[section.id], name.trim()]
            );
            await this.loadSidebarSections();
            this.notification?.add?.("Đã đổi tên section", { type: "success" });
        } catch (e) {
            console.error(e);
            this.notification?.add?.("Không đổi tên được section", { type: "danger" });
        }
    },

    async onDeleteSection(section) {
        const ok = window.confirm(`Xóa section "${section.name}"?`);
        if (!ok) {
            return;
        }
        try {
            await this.orm.call(
                "discuss.sidebar.section",
                "delete_section",
                [[section.id]]
            );
            await this.loadSidebarSections();
            this.notification?.add?.("Đã xóa section", { type: "success" });
        } catch (e) {
            console.error(e);
            this.notification?.add?.("Không xóa được section", { type: "danger" });
        }
    },

    async onToggleSection(section) {
        try {
            await this.orm.call(
                "discuss.sidebar.section",
                "toggle_fold",
                [[section.id]]
            );
            await this.loadSidebarSections();
        } catch (e) {
            console.error(e);
        }
    },

    async onAssignThreadToSection(thread, section) {
        try {
            await this.orm.call(
                "discuss.channel",
                "sidebar_assign_section",
                [[thread.id], section.id]
            );
            await this.loadSidebarSections();
            this.notification?.add?.("Đã đưa kênh vào section", { type: "success" });
        } catch (e) {
            console.error(e);
            this.notification?.add?.("Không đưa được kênh vào section", { type: "danger" });
        }
    },

    async onUnassignThreadFromSection(thread) {
        try {
            await this.orm.call(
                "discuss.channel",
                "sidebar_unassign_section",
                [[thread.id]]
            );
            await this.loadSidebarSections();
            this.notification?.add?.("Đã bỏ kênh khỏi section", { type: "success" });
        } catch (e) {
            console.error(e);
            this.notification?.add?.("Không bỏ được kênh khỏi section", { type: "danger" });
        }
    },

    toggleBulkSelectMode() {
        this.state.bulkSelecting = !this.state.bulkSelecting;
        if (!this.state.bulkSelecting) {
            this.state.selectedThreadIds = [];
            this.state.bulkTargetSectionId = "";
        }
    },

    isThreadSelected(thread) {
        return this.state.selectedThreadIds.includes(String(thread.id));
    },

    toggleThreadSelection(thread) {
        const id = String(thread.id);
        if (this.state.selectedThreadIds.includes(id)) {
            this.state.selectedThreadIds = this.state.selectedThreadIds.filter((x) => x !== id);
        } else {
            this.state.selectedThreadIds = [...this.state.selectedThreadIds, id];
        }
    },

    clearBulkSelection() {
        this.state.selectedThreadIds = [];
    },

    setBulkTargetSection(sectionId) {
        this.state.bulkTargetSectionId = String(sectionId || "");
    },

    async onConfirmBulkAssign() {
        if (!this.state.selectedThreadIds.length) {
            this.notification?.add?.("Chưa chọn kênh nào", { type: "warning" });
            return;
        }
        if (!this.state.bulkTargetSectionId) {
            this.notification?.add?.("Vui lòng chọn section", { type: "warning" });
            return;
        }

        try {
            await this.orm.call(
                "discuss.channel",
                "sidebar_assign_section_multi",
                [
                    this.state.selectedThreadIds.map((id) => Number(id)),
                    Number(this.state.bulkTargetSectionId),
                ]
            );

            this.state.selectedThreadIds = [];
            this.state.bulkTargetSectionId = "";
            this.state.bulkSelecting = false;

            await this.loadSidebarSections();
            this.notification?.add?.("Đã đưa các kênh vào section", { type: "success" });
        } catch (e) {
            console.error(e);
            this.notification?.add?.("Không đưa được các kênh vào section", { type: "danger" });
        }
    },

    _getDraggedThreadIds(thread) {
        const id = String(thread.id);
        if (
            this.state.bulkSelecting &&
            this.state.selectedThreadIds.includes(id)
        ) {
            return [...this.state.selectedThreadIds];
        }
        return [id];
    },

    _resetDragState() {
        this.state.dragging = {
            active: false,
            threadIds: [],
            overSectionId: "",
            overThreadId: "",
            dropPosition: "",
        };
    },

    onThreadDragStart(ev, thread) {
        const ids = this._getDraggedThreadIds(thread);

        this.state.dragging = {
            active: true,
            threadIds: ids,
            overSectionId: "",
            overThreadId: "",
            dropPosition: "",
        };

        try {
            ev.dataTransfer.effectAllowed = "move";
            ev.dataTransfer.setData(
                "text/plain",
                JSON.stringify({
                    type: "sidebar_threads",
                    thread_ids: ids,
                })
            );
        } catch {
            // ignore
        }
    },

    onThreadDragEnd() {
        this._resetDragState();
    },

    onSectionDragOver(ev, section) {
        ev.preventDefault();
        ev.stopPropagation();
        try {
            ev.dataTransfer.dropEffect = "move";
        } catch {
            // ignore
        }

        this.state.dragging.overSectionId = String(section.id);
        this.state.dragging.overThreadId = "";
        this.state.dragging.dropPosition = "inside";
    },

    async onSectionDrop(ev, section) {
        ev.preventDefault();
        ev.stopPropagation();

        const ids = (this.state.dragging.threadIds || []).map((id) => Number(id));
        if (!ids.length) {
            this._resetDragState();
            return;
        }

        try {
            await this.orm.call(
                "discuss.channel",
                "sidebar_drag_to_section",
                [ids, Number(section.id)]
            );

            this.state.selectedThreadIds = [];
            this.state.bulkTargetSectionId = "";
            this.state.bulkSelecting = false;

            await this.loadSidebarSections();
            this.notification?.add?.("Đã chuyển kênh vào section", { type: "success" });
        } catch (e) {
            console.error(e);
            this.notification?.add?.("Không kéo được kênh vào section", { type: "danger" });
        } finally {
            this._resetDragState();
        }
    },

    onThreadDragOver(ev, thread) {
        ev.preventDefault();
        ev.stopPropagation();

        const rect = ev.currentTarget.getBoundingClientRect();
        const offsetY = ev.clientY - rect.top;
        const position = offsetY < rect.height / 2 ? "before" : "after";

        this.state.dragging.overSectionId = "";
        this.state.dragging.overThreadId = String(thread.id);
        this.state.dragging.dropPosition = position;

        try {
            ev.dataTransfer.dropEffect = "move";
        } catch {
            // ignore
        }
    },

    async onThreadDrop(ev, thread) {
        ev.preventDefault();
        ev.stopPropagation();

        const ids = (this.state.dragging.threadIds || []).map((id) => Number(id));
        const targetId = Number(thread.id);
        const position = this.state.dragging.dropPosition || "after";

        if (!ids.length || !targetId) {
            this._resetDragState();
            return;
        }

        if (ids.length === 1 && ids[0] === targetId) {
            this._resetDragState();
            return;
        }

        try {
            if (position === "before") {
                await this.orm.call(
                    "discuss.channel",
                    "sidebar_drag_before_channel",
                    [ids, targetId]
                );
            } else {
                await this.orm.call(
                    "discuss.channel",
                    "sidebar_drag_after_channel",
                    [ids, targetId]
                );
            }

            this.state.selectedThreadIds = [];
            this.state.bulkTargetSectionId = "";
            this.state.bulkSelecting = false;

            await this.loadSidebarSections();
            this.notification?.add?.("Đã sắp xếp lại kênh", { type: "success" });
        } catch (e) {
            console.error(e);
            this.notification?.add?.("Không sắp xếp được kênh", { type: "danger" });
        } finally {
            this._resetDragState();
        }
    },

    isDragOverSection(section) {
        return (
            this.state.dragging.active &&
            this.state.dragging.overSectionId === String(section.id) &&
            this.state.dragging.dropPosition === "inside"
        );
    },

    isDropBeforeThread(thread) {
        return (
            this.state.dragging.active &&
            this.state.dragging.overThreadId === String(thread.id) &&
            this.state.dragging.dropPosition === "before"
        );
    },

    isDropAfterThread(thread) {
        return (
            this.state.dragging.active &&
            this.state.dragging.overThreadId === String(thread.id) &&
            this.state.dragging.dropPosition === "after"
        );
    },
});