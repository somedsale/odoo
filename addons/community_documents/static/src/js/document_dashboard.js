/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class DocumentDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.user = useService("user");

        this.state = useState({
            folders: [],
            tags: [],
            docs: [],
            folderId: null,
            tagIds: new Set(),
            search: "",
            selectedId: null,
            selected: null,
            allowedFolderIds: [],
        });

        onWillStart(async () => {
            await this.loadSidebars();
            await this.loadDocs();
        });
    }

    async loadSidebars() {
        const uid = this.user.userId;

        // 1) lấy danh sách folder (tối thiểu fields)
        const folders = await this.orm.searchRead(
            "document.folder",
            [],
            ["name", "parent_id", "access_level", "owner_id"]
        );

        // 2) lấy member rows của user hiện tại
        const memberRows = await this.orm.searchRead(
            "document.folder.member",
            [["user_id", "=", uid]],
            ["folder_id", "role", "own_only"]
        );
        const memberFolderIds = new Set(memberRows.map((r) => r.folder_id?.[0]).filter(Boolean));

        // 3) lọc folder được phép
        const allowed = folders.filter((f) => {
            const ownerId = f.owner_id?.[0];
            if (f.access_level === "internal") return true;
            if (ownerId === uid) return true;
            if (f.access_level === "shared" && memberFolderIds.has(f.id)) return true;
            return false;
        });

        // lưu lại allowed ids để lọc docs
        this.state.allowedFolderIds = allowed.map((f) => f.id);

        // Optional: build tree UI nếu bạn đang hiển thị theo parent_id
        this.state.folders = allowed;

        // tags không cần quyền
        this.state.tags = await this.orm.searchRead("document.tag", [], ["name", "color"]);
    }


    buildDomain() {
        const domain = [];

        // ✅ bắt buộc: lọc theo allowed folders
        if (this.state.allowedFolderIds?.length) {
            domain.push(["folder_id", "in", this.state.allowedFolderIds]);
        } else {
            // nếu chưa có folder nào được phép -> không load gì
            domain.push(["id", "=", 0]);
            return domain;
        }

        if (this.state.folderId) domain.push(["folder_id", "=", this.state.folderId]);
        if (this.state.tagIds.size) domain.push(["tag_ids", "in", Array.from(this.state.tagIds)]);
        if (this.state.search && this.state.search.trim()) domain.push(["name", "ilike", this.state.search.trim()]);

        return domain;
    }


    async loadDocs() {
        const fields = ["name", "write_date", "owner_id", "folder_id", "mimetype", "attachment_id", "tag_ids", "is_link"];
        this.state.docs = await this.orm.searchRead("document.document", this.buildDomain(), fields, { limit: 200 });

        if (this.state.selectedId) {
            const found = this.state.docs.find((d) => d.id === this.state.selectedId);
            this.state.selected = found || null;
            if (!found) this.state.selectedId = null;
        }
    }

    // ---------- SAFE EVENT HANDLERS ----------
    async onFolderClick(ev) {
        const raw = ev.currentTarget.dataset.id;
        const folderId = raw ? Number(raw) : null;

        if (folderId && !this.state.allowedFolderIds.includes(folderId)) {
            return; // không cho chọn folder ngoài quyền
        }

        this.state.folderId = folderId;
        await this.loadDocs();

    }

    async onTagToggle(ev) {
        const tagId = Number(ev.currentTarget.dataset.id);
        if (this.state.tagIds.has(tagId)) this.state.tagIds.delete(tagId);
        else this.state.tagIds.add(tagId);
        await this.loadDocs();
    }

    onDocClick(ev) {
        const id = Number(ev.currentTarget.dataset.id);
        this.state.selectedId = id;
        this.state.selected = this.state.docs.find((d) => d.id === id) || null;
    }

    async onSearchInput() {
        await this.loadDocs();
    }

    // ---------- Helpers ----------
    contentUrl(attachmentId) {
        if (!attachmentId) return "";
        return `/web/content/${attachmentId}?download=false`;
    }
    isPdf(mimetype) { return (mimetype || "") === "application/pdf"; }
    isImage(mimetype) { return (mimetype || "").startsWith("image/"); }

    iconFor(mimetype, isLink) {
        if (isLink) return "🔗";
        if (!mimetype) return "📄";
        if (mimetype === "application/pdf") return "📕";
        if (mimetype.includes("spreadsheet") || mimetype.includes("excel")) return "📗";
        if (mimetype.startsWith("image/")) return "🖼️";
        if (mimetype.includes("word")) return "📘";
        return "📄";
    }

    async onUpload() {
        const input = document.createElement("input");
        input.type = "file";
        input.multiple = true;
        input.style.display = "none";
        document.body.appendChild(input);

        const fileToBase64 = (file) =>
            new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => {
                    const result = String(reader.result || "");
                    const base64 = result.includes(",") ? result.split(",")[1] : "";
                    resolve(base64);
                };
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });

        input.addEventListener("change", async () => {
            try {
                const files = Array.from(input.files || []);
                if (!files.length) return;

                // Upload tuần tự cho ổn định
                for (const f of files) {
                    const b64 = await fileToBase64(f);
                    const vals = {
                    name: f.name,              // ✅ bắt buộc để khỏi lỗi Name
                    datas_filename: f.name,
                    datas: b64,
                    };

                        if (this.state.folderId) {
                        vals.folder_id = this.state.folderId;
                        }
                    await this.orm.create("document.document", [vals]);
                }

                await this.loadDocs();
            } finally {
                input.remove();
            }
        });

        input.click();
    }


    async onAddLink() {
        await this.action.doAction("community_documents.action_document_add_link_wizard", {
            additionalContext: {
                default_folder_id: this.state.folderId || false,
            },
            onClose: async () => {
                await this.loadDocs();
            },
        });
    }
    async onCreateFolder() {
        await this.action.doAction("community_documents.action_document_create_folder_wizard", {
            additionalContext: {
                // nếu đang chọn folder thì tạo subfolder của folder đó
                default_parent_id: this.state.folderId || false,
            },
            onClose: async () => {
                await this.loadSidebars();
                // nếu bạn muốn reload docs luôn (khi user đang filter theo folder)
                await this.loadDocs();
            },
        });
    }


    async openSelected() {
        if (!this.state.selectedId) return;
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "document.document",
            res_id: this.state.selectedId,
            views: [[false, "form"]],
        });
    }
    async onEditFolder(ev) {
        ev.stopPropagation();
        const id = Number(ev.currentTarget.dataset.id);
        if (!id) return;

        await this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: "Edit Folder",
                res_model: "document.folder",
                res_id: id,
                views: [[false, "form"]],
                target: "new",
            },
            {
                onClose: async () => {
                    await this.loadSidebars();
                    await this.loadDocs();
                },
            }
        );
    }

    async onDeleteFolder(ev) {
        ev.stopPropagation();
        const id = Number(ev.currentTarget.dataset.id);
        if (!id) return;

        if (!window.confirm("Delete this folder?")) return;

        // Xóa folder
        await this.orm.unlink("document.folder", [id]);

        // Nếu đang chọn folder đó thì reset
        if (this.state.folderId === id) this.state.folderId = null;

        await this.loadSidebars();
        await this.loadDocs();
    }


    downloadSelected() {
        const a = this.state.selected?.attachment_id?.[0];
        if (!a) return;
        window.open(`/web/content/${a}?download=true`, "_blank");
    }
}

DocumentDashboard.template = "community_documents.DocumentDashboard";
registry.category("actions").add("community_documents.dashboard", DocumentDashboard);
