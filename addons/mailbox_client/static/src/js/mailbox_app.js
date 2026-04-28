/** @odoo-module **/

import { registry } from "@web/core/registry";
import {
    Component,
    onWillStart,
    onMounted,
    onWillUnmount,
    onPatched,
    useState,
    useRef,
} from "@odoo/owl";
import { markup } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class MailboxApp extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.user = useService("user");

        this.editorRef = useRef("composerEditor");
        this.savedSelection = null;
        this.editorInitialized = false;

        this.state = useState({
            loading: true,
            accounts: [],
            folders: [],
            messages: [],
            selectedAccountId: false,
            selectedFolderId: false,
            selectedMessageId: false,
            selectedMessage: null,
            selectedMessageIds: [],
            search: "",
            unreadOnly: false,
            starredOnly: false,
            filterKey: "all",
            showFilterMenu: false,
            pageSize: 50,
            currentPage: 1,
            totalCount: 0,
            currentUserId: this.user.userId || false,

            composerOpen: false,
            composerMode: "new",
            composerSending: false,
            composerShowCc: false,
            composerShowBcc: false,
            composerDragOver: false,
            composerData: {
                account_id: false,
                parent_message_id: false,
                to_recipients: "",
                cc_recipients: "",
                bcc_recipients: "",
                reply_to: "",
                name: "",
                body_text: "",
                attachment_ids: [],
                editor_html: "",
                quoted_html: "",
            },
        });

        this.refreshTimer = null;
        this.lastTopMessageId = null;
        this.lastUnreadCount = 0;

        onWillStart(async () => {
            await this.loadInitialData();
        });

        onMounted(() => {
            this.startAutoRefresh();
            this.syncComposerEditorContent();
        });

        onPatched(() => {
            this.syncComposerEditorContent();
        });

        onWillUnmount(() => {
            this.stopAutoRefresh();
        });
    }

    // =========================================================
    // Helpers
    // =========================================================

    escapeHtml(value) {
        const text = String(value || "");
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    isHtmlLike(content) {
        if (!content) {
            return false;
        }
        const text = String(content).trim().toLowerCase();
        return (
            text.startsWith("<!doctype") ||
            text.startsWith("<html") ||
            text.startsWith("<body") ||
            text.startsWith("<table") ||
            text.startsWith("<div") ||
            text.startsWith("<p") ||
            text.startsWith("<span") ||
            text.startsWith("<meta") ||
            text.startsWith("<style") ||
            text.startsWith("<ul") ||
            text.startsWith("<ol") ||
            text.startsWith("<li") ||
            text.startsWith("<br")
        );
    }

    stripHtmlToText(html) {
        if (!html) {
            return "";
        }

        const wrapper = document.createElement("div");
        wrapper.innerHTML = String(html);

        wrapper.querySelectorAll(".o_mailbox_quote_block").forEach((el) => el.remove());
        wrapper.querySelectorAll("blockquote").forEach((el) => el.remove());
        wrapper.querySelectorAll("style, script, img, svg, table, iframe, video, audio").forEach((el) => el.remove());

        return (wrapper.textContent || wrapper.innerText || "")
            .replace(/\u00a0/g, " ")
            .replace(/\s+/g, " ")
            .trim();
    }

    prepareMessageListItem(message) {
        if (!message) {
            return message;
        }

        const item = { ...message };
        const source = item.body_html || item.body_text || item.snippet || "";

        let textSnippet = "";
        if (this.isHtmlLike(source)) {
            textSnippet = this.stripHtmlToText(source);
        } else {
            textSnippet = String(source || "").replace(/\s+/g, " ").trim();
        }

        if (textSnippet.length > 180) {
            textSnippet = `${textSnippet.slice(0, 180)}...`;
        }

        item.list_snippet_text = textSnippet;
        return item;
    }

    buildReplySubject(subject) {
        const value = String(subject || "").trim();
        if (!value) {
            return "Re:";
        }
        return /^re\s*:/i.test(value) ? value : `Re: ${value}`;
    }

    buildForwardSubject(subject) {
        const value = String(subject || "").trim();
        if (!value) {
            return "Fwd:";
        }
        return /^fwd\s*:/i.test(value) ? value : `Fwd: ${value}`;
    }

    buildReplyQuotedHtml(message) {
        const originalHtml = message.body_html
            ? message.body_html
            : `<pre>${this.escapeHtml(message.body_text || "")}</pre>`;

        return `
            <div class="o_mailbox_quote_block">
                <p><strong>From:</strong> ${this.escapeHtml(message.sender || "")}</p>
                <p><strong>Date:</strong> ${this.escapeHtml(this.formatDate(message.message_date) || "")}</p>
                <p><strong>To:</strong> ${this.escapeHtml(message.to_recipients || "")}</p>
                <p><strong>Subject:</strong> ${this.escapeHtml(message.name || "")}</p>
                <div class="o_mailbox_quote_original">
                    ${originalHtml}
                </div>
            </div>
        `;
    }

    buildForwardQuotedHtml(message) {
        const originalHtml = message.body_html
            ? message.body_html
            : `<pre>${this.escapeHtml(message.body_text || "")}</pre>`;

        return `
            <hr/>
            <p><strong>From:</strong> ${this.escapeHtml(message.sender || "")}</p>
            <p><strong>Date:</strong> ${this.escapeHtml(this.formatDate(message.message_date) || "")}</p>
            <p><strong>To:</strong> ${this.escapeHtml(message.to_recipients || "")}</p>
            <p><strong>Cc:</strong> ${this.escapeHtml(message.cc_recipients || "")}</p>
            <p><strong>Subject:</strong> ${this.escapeHtml(message.name || "")}</p>
            <div class="o_mailbox_quote_original">
                ${originalHtml}
            </div>
        `;
    }

    prepareMessageForDisplay(message) {
        if (!message) {
            return null;
        }

        const prepared = { ...message };
        const htmlBody = prepared.body_html || "";
        const textBody = prepared.body_text || "";

        let renderHtml = "";
        let renderText = "";

        if (htmlBody && this.isHtmlLike(htmlBody)) {
            renderHtml = htmlBody;
        } else if (!htmlBody && this.isHtmlLike(textBody)) {
            renderHtml = textBody;
        } else if (htmlBody) {
            renderHtml = htmlBody;
        } else {
            renderText = textBody;
        }

        prepared.render_body_html = renderHtml ? markup(renderHtml) : null;
        prepared.render_body_text = renderText || "";
        prepared.attachments = prepared.attachments || [];

        return prepared;
    }

    formatDate(value) {
        if (!value) {
            return "";
        }

        let isoValue = String(value).trim();
        if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(isoValue)) {
            isoValue = isoValue.replace(" ", "T") + "Z";
        }

        const date = new Date(isoValue);
        if (Number.isNaN(date.getTime())) {
            return value;
        }

        const pad = (n) => String(n).padStart(2, "0");
        return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
    }

    formatAttachmentSize(size) {
        const value = Number(size || 0);
        if (value < 1024) return `${value} B`;
        if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
        if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
        return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
    }

    getAttachmentDownloadUrl(attachmentId) {
        return `/web/content/${attachmentId}?download=true`;
    }

    openAttachment(attachment) {
        if (!attachment || !attachment.id) {
            return;
        }
        window.open(this.getAttachmentDownloadUrl(attachment.id), "_blank");
    }

    downloadAttachment(attachment) {
        if (!attachment || !attachment.id) {
            return;
        }
        window.location = this.getAttachmentDownloadUrl(attachment.id);
    }

    get selectedFolderCode() {
        const folder = this.state.folders.find((f) => f.id === this.state.selectedFolderId);
        return folder ? folder.code : "";
    }

    get composerSelectedAccount() {
        return this.state.accounts.find((a) => a.id === this.state.composerData.account_id) || null;
    }

    get composerQuotedMarkup() {
        return markup(this.state.composerData.quoted_html || "");
    }

    get composerFullHtml() {
        const editor = this.editorRef.el;
        const liveEditorHtml = editor ? editor.innerHTML : (this.state.composerData.editor_html || "");
        return `${liveEditorHtml}${this.state.composerData.quoted_html || ""}`;
    }

    get hasSelectedMessages() {
        return this.state.selectedMessageIds.length > 0;
    }

    get allVisibleSelected() {
        return !!this.state.messages.length &&
            this.state.messages.every((m) => this.state.selectedMessageIds.includes(m.id));
    }

    get filterLabel() {
        const labels = {
            all: "All",
            unread: "Unread",
            starred: "Starred",
            attachment: "Has attachment",
            incoming: "Incoming",
            outgoing: "Outgoing",
            today: "Today",
            week: "This week",
        };
        return labels[this.state.filterKey] || "Filter";
    }

    get totalPages() {
        return Math.max(1, Math.ceil((this.state.totalCount || 0) / this.state.pageSize));
    }

    get pageStart() {
        if (!this.state.totalCount) {
            return 0;
        }
        return ((this.state.currentPage - 1) * this.state.pageSize) + 1;
    }

    get pageEnd() {
        return Math.min(this.state.currentPage * this.state.pageSize, this.state.totalCount || 0);
    }

    // =========================================================
    // Checkbox selection
    // =========================================================

    isMessageChecked(messageId) {
        return this.state.selectedMessageIds.includes(messageId);
    }

    toggleMessageChecked(messageId) {
        const checked = this.isMessageChecked(messageId);
        if (checked) {
            this.state.selectedMessageIds = this.state.selectedMessageIds.filter((id) => id !== messageId);
        } else {
            this.state.selectedMessageIds = [...this.state.selectedMessageIds, messageId];
        }
    }

    onToggleMessageCheckbox(messageId, ev) {
        ev.stopPropagation();
        this.toggleMessageChecked(messageId);
    }

    onToggleSelectAll(ev) {
        const checked = !!ev.target.checked;
        if (checked) {
            this.state.selectedMessageIds = this.state.messages.map((m) => m.id);
        } else {
            this.state.selectedMessageIds = [];
        }
    }

    clearSelectedMessages() {
        this.state.selectedMessageIds = [];
    }

    getBulkTargetIds() {
        if (this.state.selectedMessageIds.length) {
            return this.state.selectedMessageIds;
        }
        if (this.state.selectedMessageId) {
            return [this.state.selectedMessageId];
        }
        return [];
    }

    // =========================================================
    // Filter
    // =========================================================

    toggleFilterMenu() {
        this.state.showFilterMenu = !this.state.showFilterMenu;
    }

    async applyFilter(filterKey) {
        this.state.filterKey = filterKey;
        this.state.showFilterMenu = false;
        this.state.currentPage = 1;
        await this.loadMessages();
        this.captureCurrentMailboxState();
        this.clearSelectedMessages();
    }

    // =========================================================
    // Folder features
    // =========================================================

    async onCreateFolder() {
        if (!this.state.selectedAccountId) {
            this.notification.add("Chưa có mailbox account.", { type: "warning" });
            return;
        }

        const folderName = window.prompt("Nhập tên folder mới:");
        if (!folderName || !folderName.trim()) {
            return;
        }

        const name = folderName.trim();
        const imapName = name;

        try {
            await this.orm.create("mailbox.folder", [{
                account_id: this.state.selectedAccountId,
                name,
                imap_name: imapName,
                code: "custom",
                sequence: 100,
                active: true,
            }]);

            this.notification.add("Đã tạo folder mới.", { type: "success" });
            await this.loadFolders();
        } catch (error) {
            this.notification.add("Tạo folder thất bại.", { type: "danger" });
            throw error;
        }
    }

    async onDeleteFolder(folder) {
        if (!folder || !folder.id) {
            return;
        }

        if (folder.code !== "custom") {
            this.notification.add("Chỉ được xóa folder do người dùng tự tạo.", {
                type: "warning",
            });
            return;
        }

        const confirmed = window.confirm(`Bạn có chắc muốn xóa folder "${folder.name}" không?`);
        if (!confirmed) {
            return;
        }

        try {
            const inboxFolder = this.state.folders.find((f) => f.code === "inbox");

            if (!inboxFolder) {
                this.notification.add("Không tìm thấy Inbox để chuyển mail về.", {
                    type: "danger",
                });
                return;
            }

            const messages = await this.orm.searchRead(
                "mailbox.message",
                [["folder_id", "=", folder.id]],
                ["id"]
            );
            const messageIds = (messages || []).map((m) => m.id);

            if (messageIds.length) {
                await this.orm.write("mailbox.message", messageIds, {
                    folder_id: inboxFolder.id,
                    state: "received",
                });
            }

            await this.orm.unlink("mailbox.folder", [folder.id]);

            if (this.state.selectedFolderId === folder.id) {
                this.state.selectedFolderId = inboxFolder.id;
                this.state.selectedMessageId = false;
                this.state.selectedMessage = null;
            }

            this.notification.add(`Đã xóa folder "${folder.name}".`, {
                type: "success",
            });

            this.state.currentPage = 1;
            await this.loadFolders();
            await this.loadMessages();
            this.clearSelectedMessages();
        } catch (error) {
            this.notification.add("Xóa folder thất bại.", {
                type: "danger",
            });
            throw error;
        }
    }

    onDragMessageStart(messageId, ev) {
        const ids = this.state.selectedMessageIds.length && this.state.selectedMessageIds.includes(messageId)
            ? this.state.selectedMessageIds
            : [messageId];

        ev.dataTransfer.effectAllowed = "move";
        ev.dataTransfer.setData("text/plain", JSON.stringify(ids));
    }

    async onDropMessagesToFolder(folderId, ev) {
        ev.preventDefault();

        let ids = [];
        try {
            const data = ev.dataTransfer.getData("text/plain");
            ids = JSON.parse(data || "[]");
        } catch {
            ids = [];
        }

        if (!ids.length) {
            return;
        }

        const targetFolder = this.state.folders.find((f) => f.id === folderId);
        if (!targetFolder) {
            return;
        }

        try {
            if (targetFolder.code === "trash") {
                await this.orm.call("mailbox.message", "action_move_trash", [ids]);
            } else if (targetFolder.code === "inbox" && this.selectedFolderCode === "trash") {
                await this.orm.call("mailbox.message", "action_restore_inbox", [ids]);
            } else {
                await this.orm.write("mailbox.message", ids, {
                    folder_id: folderId,
                    state: targetFolder.code === "trash" ? "trash" : "received",
                });
            }

            this.notification.add(`Đã chuyển ${ids.length} mail vào folder ${targetFolder.name}.`, {
                type: "success",
            });

            await this.loadFolders();
            await this.loadMessages();
            if (this.state.selectedMessageId && ids.includes(this.state.selectedMessageId)) {
                await this.loadSelectedMessage();
            }
            this.clearSelectedMessages();
        } catch (error) {
            this.notification.add("Kéo thả mail vào folder thất bại.", { type: "danger" });
            throw error;
        }
    }

    // =========================================================
    // Composer editor
    // =========================================================

    syncComposerEditorContent() {
        const editor = this.editorRef.el;
        if (!editor || !this.state.composerOpen) {
            this.editorInitialized = false;
            return;
        }

        if (!this.editorInitialized) {
            editor.innerHTML = this.state.composerData.editor_html || "<p><br></p>";
            this.editorInitialized = true;
        }
    }

    saveEditorSelection() {
        const editor = this.editorRef.el;
        const selection = window.getSelection();
        if (!editor || !selection || selection.rangeCount === 0) {
            return;
        }

        const range = selection.getRangeAt(0);
        if (editor.contains(range.startContainer) && editor.contains(range.endContainer)) {
            this.savedSelection = range.cloneRange();
        }
    }

    restoreEditorSelection() {
        const editor = this.editorRef.el;
        const selection = window.getSelection();
        if (!editor || !selection) {
            return false;
        }

        editor.focus();

        if (this.savedSelection) {
            selection.removeAllRanges();
            selection.addRange(this.savedSelection);
            return true;
        }

        const range = document.createRange();
        range.selectNodeContents(editor);
        range.collapse(false);
        selection.removeAllRanges();
        selection.addRange(range);
        return true;
    }

    onComposerEditorFocus() {
        this.saveEditorSelection();
    }

    onComposerEditorKeyup() {
        const editor = this.editorRef.el;
        if (editor) {
            this.state.composerData.editor_html = editor.innerHTML || "";
        }
        this.saveEditorSelection();
    }

    onComposerEditorMouseup() {
        this.saveEditorSelection();
    }

    onComposerHtmlInput() {
        const editor = this.editorRef.el;
        if (!editor) {
            return;
        }
        this.state.composerData.editor_html = editor.innerHTML || "";
        this.saveEditorSelection();
    }

    applyEditorCommand(command, value = null) {
        const editor = this.editorRef.el;
        if (!editor) {
            return;
        }

        this.restoreEditorSelection();
        document.execCommand(command, false, value);
        this.state.composerData.editor_html = editor.innerHTML || "";
        this.saveEditorSelection();
        editor.focus();
    }

    applyEditorBlock(tag) {
        this.applyEditorCommand("formatBlock", tag);
    }

    insertEditorLink() {
        const url = window.prompt("Nhập link URL:");
        if (!url) {
            return;
        }
        this.applyEditorCommand("createLink", url);
    }

    removeEditorLink() {
        this.applyEditorCommand("unlink");
    }

    toggleComposerExtra(field) {
        if (field === "cc") {
            this.state.composerShowCc = !this.state.composerShowCc;
        }
        if (field === "bcc") {
            this.state.composerShowBcc = !this.state.composerShowBcc;
        }
    }

    // =========================================================
    // Composer attachments + drag drop
    // =========================================================

    async addComposerFiles(files) {
        const fileList = Array.from(files || []);
        if (!fileList.length) {
            return;
        }

        try {
            for (const file of fileList) {
                const dataUrl = await this.readFileAsDataURL(file);
                const base64 = dataUrl.split(",")[1] || "";

                const attachmentId = await this.orm.create("ir.attachment", [{
                    name: file.name,
                    datas: base64,
                    mimetype: file.type || "application/octet-stream",
                    res_model: "mailbox.compose.wizard",
                    res_id: 0,
                    type: "binary",
                }]);

                const realId = Array.isArray(attachmentId) ? attachmentId[0] : attachmentId;
                if (realId) {
                    this.state.composerData.attachment_ids.push({
                        id: realId,
                        name: file.name,
                        mimetype: file.type || "application/octet-stream",
                        size: file.size || 0,
                    });
                }
            }

            this.notification.add("Đã thêm tệp đính kèm.", { type: "success" });
        } catch (error) {
            this.notification.add("Tải tệp đính kèm thất bại.", { type: "danger" });
            throw error;
        }
    }

    async onComposerAttachmentChange(ev) {
        const files = ev.target.files || [];
        try {
            await this.addComposerFiles(files);
        } finally {
            ev.target.value = "";
        }
    }

    onComposerDragEnter(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this.state.composerDragOver = true;
    }

    onComposerDragOver(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        ev.dataTransfer.dropEffect = "copy";
        this.state.composerDragOver = true;
    }

    onComposerDragLeave(ev) {
        ev.preventDefault();
        ev.stopPropagation();

        const currentTarget = ev.currentTarget;
        const relatedTarget = ev.relatedTarget;

        if (currentTarget && relatedTarget && currentTarget.contains(relatedTarget)) {
            return;
        }

        this.state.composerDragOver = false;
    }

    async onComposerDrop(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this.state.composerDragOver = false;

        const files = ev.dataTransfer?.files || [];
        if (!files.length) {
            return;
        }

        await this.addComposerFiles(files);
    }

    readFileAsDataURL(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    removeComposerAttachment(attachmentId) {
        this.state.composerData.attachment_ids = this.state.composerData.attachment_ids.filter(
            (att) => att.id !== attachmentId
        );
    }

    // =========================================================
    // Auto refresh fallback
    // =========================================================

    startAutoRefresh() {
        this.stopAutoRefresh();
        this.refreshTimer = setInterval(async () => {
            try {
                await this.checkForNewMessages();
            } catch (e) {
                console.warn("Mailbox auto refresh failed:", e);
            }
        }, 10000);
    }

    stopAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }

    captureCurrentMailboxState() {
        this.lastTopMessageId = this.state.messages.length ? this.state.messages[0].id : null;
        this.lastUnreadCount = this.state.messages.filter((m) => !m.is_read).length;
    }

    async checkForNewMessages() {
        if (!this.state.selectedAccountId || !this.state.selectedFolderId) {
            return;
        }

        const previousTopMessageId = this.lastTopMessageId;
        const previousUnreadCount = this.lastUnreadCount;

        await this.loadFolders();
        await this.loadMessages(false);

        const currentTopMessageId = this.state.messages.length ? this.state.messages[0].id : null;
        const currentUnreadCount = this.state.messages.filter((m) => !m.is_read).length;

        const hasNewTopMessage =
            currentTopMessageId && previousTopMessageId && currentTopMessageId !== previousTopMessageId;

        const firstLoadCase = currentTopMessageId && !previousTopMessageId;
        const unreadIncreased = currentUnreadCount > previousUnreadCount;
        const diffUnread = Math.max(0, currentUnreadCount - previousUnreadCount);

        if (hasNewTopMessage || (firstLoadCase && currentUnreadCount > 0) || unreadIncreased) {
            this.notification.add(
                diffUnread > 1 ? `Bạn có ${diffUnread} email mới.` : "Bạn có email mới.",
                { type: "success" }
            );

            await this.loadMessages();
        }

        this.lastTopMessageId = currentTopMessageId;
        this.lastUnreadCount = currentUnreadCount;
    }

    // =========================================================
    // Pagination
    // =========================================================

    async goToPage(page) {
        const totalPages = this.totalPages;
        const nextPage = Math.max(1, Math.min(page, totalPages));

        if (nextPage === this.state.currentPage) {
            return;
        }

        this.state.currentPage = nextPage;
        this.state.selectedMessageId = false;
        this.state.selectedMessage = null;
        this.clearSelectedMessages();

        await this.loadMessages();
        this.captureCurrentMailboxState();
    }

    async onPrevPage() {
        await this.goToPage(this.state.currentPage - 1);
    }

    async onNextPage() {
        await this.goToPage(this.state.currentPage + 1);
    }

    // =========================================================
    // Load data
    // =========================================================

    async loadInitialData() {
        this.state.loading = true;

        const accounts = await this.orm.searchRead(
            "mailbox.account",
            [],
            ["name", "email_address", "last_fetch_date", "last_fetch_status", "user_id"]
        );

        this.state.accounts = accounts || [];

        if (this.state.accounts.length) {
            this.state.selectedAccountId = this.state.accounts[0].id;
            await this.loadFolders();
            await this.loadMessages();
            this.captureCurrentMailboxState();
            this.state.composerData.account_id = this.state.selectedAccountId;
        } else {
            this.state.selectedAccountId = false;
            this.state.selectedFolderId = false;
            this.state.selectedMessageId = false;
            this.state.folders = [];
            this.state.messages = [];
            this.state.selectedMessage = null;
            this.lastTopMessageId = null;
            this.lastUnreadCount = 0;
            this.state.totalCount = 0;
        }

        this.state.loading = false;
    }

    async loadFolders() {
        if (!this.state.selectedAccountId) {
            this.state.folders = [];
            this.state.selectedFolderId = false;
            return;
        }

        const folders = await this.orm.searchRead(
            "mailbox.folder",
            [
                ["account_id", "=", this.state.selectedAccountId],
                ["active", "=", true],
                ["name", "not in", [".", '""', "INBOX."]],
                ["imap_name", "not in", [".", '""', "INBOX."]],
            ],
            ["name", "code", "mailbox_message_count", "imap_name", "sequence"],
            { order: "sequence asc, id asc" }
        );

        this.state.folders = folders || [];

        if (
            !this.state.selectedFolderId ||
            !this.state.folders.find((f) => f.id === this.state.selectedFolderId)
        ) {
            const inbox = this.state.folders.find((f) => f.code === "inbox");
            this.state.selectedFolderId = inbox
                ? inbox.id
                : this.state.folders[0]
                    ? this.state.folders[0].id
                    : false;
        }
    }

    buildMessageDomain() {
        const domain = [];

        if (this.state.selectedAccountId) {
            domain.push(["account_id", "=", this.state.selectedAccountId]);
        }

        if (this.state.selectedFolderId) {
            domain.push(["folder_id", "=", this.state.selectedFolderId]);
        }

        const filterKey = this.state.filterKey || "all";

        if (filterKey === "unread" || this.state.unreadOnly) {
            domain.push(["is_read", "=", false]);
        }

        if (filterKey === "starred" || this.state.starredOnly) {
            domain.push(["is_starred", "=", true]);
        }

        if (filterKey === "attachment") {
            domain.push(["attachment_count", ">", 0]);
        }

        if (filterKey === "incoming") {
            domain.push(["direction", "=", "incoming"]);
        }

        if (filterKey === "outgoing") {
            domain.push(["direction", "=", "outgoing"]);
        }

        if (filterKey === "today" || filterKey === "week") {
            const now = new Date();
            let startDate = new Date(now);

            if (filterKey === "today") {
                startDate.setHours(0, 0, 0, 0);
            } else {
                const day = startDate.getDay();
                const diff = day === 0 ? 6 : day - 1;
                startDate.setDate(startDate.getDate() - diff);
                startDate.setHours(0, 0, 0, 0);
            }

            const pad = (n) => String(n).padStart(2, "0");
            const yyyy = startDate.getFullYear();
            const mm = pad(startDate.getMonth() + 1);
            const dd = pad(startDate.getDate());
            const hh = pad(startDate.getHours());
            const mi = pad(startDate.getMinutes());
            const ss = pad(startDate.getSeconds());

            domain.push(["message_date", ">=", `${yyyy}-${mm}-${dd} ${hh}:${mi}:${ss}`]);
        }

        const keyword = (this.state.search || "").trim();
        if (keyword) {
            domain.push(
                "|",
                "|",
                ["name", "ilike", keyword],
                ["sender", "ilike", keyword],
                ["snippet", "ilike", keyword]
            );
        }

        return domain;
    }

    async loadMessages(autoLoadSelected = true) {
        const domain = this.buildMessageDomain();

        const totalCount = await this.orm.searchCount("mailbox.message", domain);
        this.state.totalCount = totalCount || 0;

        const totalPages = Math.max(1, Math.ceil((this.state.totalCount || 0) / this.state.pageSize));
        if (this.state.currentPage > totalPages) {
            this.state.currentPage = totalPages;
        }
        if (this.state.currentPage < 1) {
            this.state.currentPage = 1;
        }

        const offset = (this.state.currentPage - 1) * this.state.pageSize;

        const messages = await this.orm.searchRead(
            "mailbox.message",
            domain,
            [
                "name",
                "sender",
                "sender_name",
                "snippet",
                "body_html",
                "body_text",
                "message_date",
                "is_read",
                "is_starred",
                "state",
                "direction",
                "attachment_count",
                "folder_id",
                "account_id",
            ],
            {
                limit: this.state.pageSize,
                offset: offset,
                order: "message_date desc, id desc",
            }
        );

        this.state.messages = (messages || []).map((message) => this.prepareMessageListItem(message));

        const visibleIds = this.state.messages.map((m) => m.id);
        this.state.selectedMessageIds = this.state.selectedMessageIds.filter((id) => visibleIds.includes(id));

        if (!autoLoadSelected) {
            return;
        }

        if (this.state.messages.length) {
            const stillExists = this.state.messages.find((m) => m.id === this.state.selectedMessageId);

            if (!this.state.selectedMessageId || !stillExists) {
                this.state.selectedMessageId = this.state.messages[0].id;
            }

            await this.loadSelectedMessage();
        } else {
            this.state.selectedMessageId = false;
            this.state.selectedMessage = null;
            this.clearSelectedMessages();
        }
    }

    async loadSelectedMessage() {
        if (!this.state.selectedMessageId) {
            this.state.selectedMessage = null;
            return;
        }

        const result = await this.orm.call(
            "mailbox.message",
            "get_message_full_data",
            [[this.state.selectedMessageId]]
        );

        const rawMessage = result || null;
        this.state.selectedMessage = this.prepareMessageForDisplay(rawMessage);

        if (this.state.selectedMessage && !this.state.selectedMessage.is_read) {
            await this.orm.call("mailbox.message", "action_mark_read", [
                [this.state.selectedMessageId],
            ]);

            this.state.selectedMessage.is_read = true;

            const row = this.state.messages.find((m) => m.id === this.state.selectedMessageId);
            if (row) {
                row.is_read = true;
            }
        }

        this.captureCurrentMailboxState();
    }

    // =========================================================
    // Composer
    // =========================================================

    resetComposer() {
        this.state.composerOpen = false;
        this.state.composerMode = "new";
        this.state.composerSending = false;
        this.state.composerShowCc = false;
        this.state.composerShowBcc = false;
        this.state.composerDragOver = false;
        this.savedSelection = null;
        this.editorInitialized = false;

        this.state.composerData = {
            account_id: this.state.selectedAccountId || false,
            parent_message_id: false,
            to_recipients: "",
            cc_recipients: "",
            bcc_recipients: "",
            reply_to: "",
            name: "",
            body_text: "",
            attachment_ids: [],
            editor_html: "",
            quoted_html: "",
        };
    }

    async onCompose() {
        this.state.composerOpen = true;
        this.state.composerMode = "new";
        this.state.composerShowCc = false;
        this.state.composerShowBcc = false;
        this.state.composerDragOver = false;
        this.savedSelection = null;
        this.editorInitialized = false;

        this.state.composerData = {
            account_id: this.state.selectedAccountId || false,
            parent_message_id: false,
            to_recipients: "",
            cc_recipients: "",
            bcc_recipients: "",
            reply_to: "",
            name: "",
            body_text: "",
            attachment_ids: [],
            editor_html: "<p><br></p>",
            quoted_html: "",
        };
    }

    async onReplyReal() {
        if (!this.state.selectedMessage) {
            return;
        }

        const parent = this.state.selectedMessage;

        this.state.composerOpen = true;
        this.state.composerMode = "reply";
        this.state.composerShowCc = false;
        this.state.composerShowBcc = false;
        this.state.composerDragOver = false;
        this.savedSelection = null;
        this.editorInitialized = false;

        this.state.composerData = {
            account_id: this.state.selectedAccountId || false,
            parent_message_id: parent.id,
            to_recipients: parent.reply_to || parent.sender || "",
            cc_recipients: "",
            bcc_recipients: "",
            reply_to: "",
            name: this.buildReplySubject(parent.name || ""),
            body_text: "",
            attachment_ids: [],
            editor_html: "<p><br></p>",
            quoted_html: this.buildReplyQuotedHtml(parent),
        };
    }

    async onForward() {
        if (!this.state.selectedMessage) {
            return;
        }

        const parent = this.state.selectedMessage;

        this.state.composerOpen = true;
        this.state.composerMode = "forward";
        this.state.composerShowCc = false;
        this.state.composerShowBcc = false;
        this.state.composerDragOver = false;
        this.savedSelection = null;
        this.editorInitialized = false;

        this.state.composerData = {
            account_id: this.state.selectedAccountId || false,
            parent_message_id: parent.id,
            to_recipients: "",
            cc_recipients: "",
            bcc_recipients: "",
            reply_to: "",
            name: this.buildForwardSubject(parent.name || ""),
            body_text: "",
            attachment_ids: [],
            editor_html: "<p><br></p>",
            quoted_html: this.buildForwardQuotedHtml(parent),
        };
    }

    async onComposerSend() {
        const data = this.state.composerData;

        if (!data.account_id) {
            this.notification.add("Chưa có mailbox account.", { type: "warning" });
            return;
        }

        if (!data.to_recipients) {
            this.notification.add("Bạn phải nhập người nhận.", { type: "warning" });
            return;
        }

        if (!data.name) {
            this.notification.add("Bạn phải nhập tiêu đề.", { type: "warning" });
            return;
        }

        this.state.composerSending = true;

        try {
            const createResult = await this.orm.create("mailbox.compose.wizard", [{
                mode: this.state.composerMode || "new",
                account_id: data.account_id,
                parent_message_id: data.parent_message_id || false,
                to_recipients: data.to_recipients || "",
                cc_recipients: data.cc_recipients || "",
                bcc_recipients: data.bcc_recipients || "",
                reply_to: data.reply_to || "",
                name: data.name || "",
                body_html: this.composerFullHtml || "",
                body_text: data.body_text || "",
                attachment_ids: [[6, 0, data.attachment_ids.map((att) => att.id)]],
            }]);

            const wizardId = Array.isArray(createResult) ? createResult[0] : createResult;
            if (!wizardId) {
                throw new Error("Không tạo được compose wizard.");
            }

            await this.orm.call("mailbox.compose.wizard", "action_send", [[wizardId]]);

            this.notification.add("Đã gửi mail.", { type: "success" });
            this.resetComposer();
            await this.loadFolders();
            await this.loadMessages();
            this.captureCurrentMailboxState();
        } catch (error) {
            this.notification.add("Gửi mail thất bại.", { type: "danger" });
            throw error;
        } finally {
            this.state.composerSending = false;
        }
    }

    onComposerInput(field, ev) {
        this.state.composerData[field] = ev.target.value || "";
    }

    onComposerClose() {
        this.resetComposer();
    }

    // =========================================================
    // Current message actions
    // =========================================================

    async onSelectAccount(accountId) {
        if (!accountId || accountId === this.state.selectedAccountId) {
            return;
        }

        this.state.selectedAccountId = accountId;
        this.state.selectedFolderId = false;
        this.state.selectedMessageId = false;
        this.state.selectedMessage = null;
        this.state.currentPage = 1;
        this.clearSelectedMessages();

        if (this.state.composerOpen) {
            this.state.composerData.account_id = accountId;
        }

        await this.loadFolders();
        await this.loadMessages();
        this.captureCurrentMailboxState();
    }

    async onSelectFolder(folderId) {
        if (!folderId || folderId === this.state.selectedFolderId) {
            return;
        }

        this.state.selectedFolderId = folderId;
        this.state.selectedMessageId = false;
        this.state.selectedMessage = null;
        this.state.currentPage = 1;
        this.clearSelectedMessages();

        await this.loadMessages();
        this.captureCurrentMailboxState();
    }

    async onSelectMessage(messageId) {
        if (!messageId) {
            return;
        }

        this.state.selectedMessageId = messageId;
        await this.loadSelectedMessage();
    }

    async onFetchMail() {
        if (!this.state.selectedAccountId) {
            this.notification.add("Chưa có account mail.", { type: "warning" });
            return;
        }

        try {
            await this.orm.call("mailbox.account", "action_fetch_mail", [
                [this.state.selectedAccountId],
            ]);

            this.notification.add("Đã fetch mail thành công.", { type: "success" });
            await this.loadFolders();
            await this.loadMessages();
            this.captureCurrentMailboxState();
        } catch (error) {
            this.notification.add("Fetch mail thất bại.", { type: "danger" });
            throw error;
        }
    }

    async onToggleRead() {
        if (!this.state.selectedMessageId || !this.state.selectedMessage) {
            return;
        }

        if (this.state.selectedMessage.is_read) {
            await this.orm.call("mailbox.message", "action_mark_unread", [
                [this.state.selectedMessageId],
            ]);
            this.state.selectedMessage.is_read = false;
        } else {
            await this.orm.call("mailbox.message", "action_mark_read", [
                [this.state.selectedMessageId],
            ]);
            this.state.selectedMessage.is_read = true;
        }

        const row = this.state.messages.find((m) => m.id === this.state.selectedMessageId);
        if (row) {
            row.is_read = this.state.selectedMessage.is_read;
        }

        await this.loadFolders();
        this.captureCurrentMailboxState();
    }

    async onToggleStar() {
        if (!this.state.selectedMessageId || !this.state.selectedMessage) {
            return;
        }

        await this.orm.call("mailbox.message", "action_toggle_star", [
            [this.state.selectedMessageId],
        ]);

        this.state.selectedMessage.is_starred = !this.state.selectedMessage.is_starred;

        const row = this.state.messages.find((m) => m.id === this.state.selectedMessageId);
        if (row) {
            row.is_starred = this.state.selectedMessage.is_starred;
        }
    }

    async onMoveTrash() {
        if (!this.state.selectedMessageId) {
            return;
        }

        await this.orm.call("mailbox.message", "action_move_trash", [
            [this.state.selectedMessageId],
        ]);

        this.notification.add("Đã chuyển vào thùng rác.", { type: "success" });
        await this.loadFolders();
        await this.loadMessages();
        this.captureCurrentMailboxState();
        this.clearSelectedMessages();
    }

    async onRestoreInbox() {
        if (!this.state.selectedMessageId) {
            return;
        }

        await this.orm.call("mailbox.message", "action_restore_inbox", [
            [this.state.selectedMessageId],
        ]);

        this.notification.add("Đã khôi phục về Inbox.", { type: "success" });
        await this.loadFolders();
        await this.loadMessages();
        this.captureCurrentMailboxState();
        this.clearSelectedMessages();
    }

    // =========================================================
    // Bulk actions
    // =========================================================

    async onBulkMarkRead() {
        const ids = this.getBulkTargetIds();
        if (!ids.length) {
            return;
        }

        await this.orm.call("mailbox.message", "action_mark_read", [ids]);
        this.notification.add("Đã đánh dấu đã đọc.", { type: "success" });
        await this.loadFolders();
        await this.loadMessages();
        if (this.state.selectedMessageId && ids.includes(this.state.selectedMessageId)) {
            await this.loadSelectedMessage();
        }
        this.clearSelectedMessages();
    }

    async onBulkMarkUnread() {
        const ids = this.getBulkTargetIds();
        if (!ids.length) {
            return;
        }

        await this.orm.call("mailbox.message", "action_mark_unread", [ids]);
        this.notification.add("Đã đánh dấu chưa đọc.", { type: "success" });
        await this.loadFolders();
        await this.loadMessages();
        if (this.state.selectedMessageId && ids.includes(this.state.selectedMessageId)) {
            await this.loadSelectedMessage();
        }
        this.clearSelectedMessages();
    }

    async onBulkToggleStar() {
        const ids = this.getBulkTargetIds();
        if (!ids.length) {
            return;
        }

        await this.orm.call("mailbox.message", "action_toggle_star", [ids]);
        this.notification.add("Đã cập nhật gắn sao.", { type: "success" });
        await this.loadMessages();
        if (this.state.selectedMessageId && ids.includes(this.state.selectedMessageId)) {
            await this.loadSelectedMessage();
        }
        this.clearSelectedMessages();
    }

    async onBulkMoveTrash() {
        const ids = this.getBulkTargetIds();
        if (!ids.length) {
            return;
        }

        await this.orm.call("mailbox.message", "action_move_trash", [ids]);
        this.notification.add("Đã chuyển các mail đã chọn vào thùng rác.", { type: "success" });
        await this.loadFolders();
        await this.loadMessages();
        this.clearSelectedMessages();
    }

    async onBulkRestoreInbox() {
        const ids = this.getBulkTargetIds();
        if (!ids.length) {
            return;
        }

        await this.orm.call("mailbox.message", "action_restore_inbox", [ids]);
        this.notification.add("Đã khôi phục các mail đã chọn về Inbox.", { type: "success" });
        await this.loadFolders();
        await this.loadMessages();
        this.clearSelectedMessages();
    }

    // =========================================================
    // Search / filter toggles
    // =========================================================

    async onSearchInput(ev) {
        this.state.search = ev.target.value || "";
        this.state.currentPage = 1;
        await this.loadMessages();
        this.captureCurrentMailboxState();
        this.clearSelectedMessages();
    }

    async onToggleUnreadOnly() {
        this.state.unreadOnly = !this.state.unreadOnly;
        this.state.currentPage = 1;
        await this.loadMessages();
        this.captureCurrentMailboxState();
        this.clearSelectedMessages();
    }

    async onToggleStarredOnly() {
        this.state.starredOnly = !this.state.starredOnly;
        this.state.currentPage = 1;
        await this.loadMessages();
        this.captureCurrentMailboxState();
        this.clearSelectedMessages();
    }
}

MailboxApp.template = "mailbox_client.MailboxApp";
registry.category("actions").add("mailbox_client.mailbox_app", MailboxApp);