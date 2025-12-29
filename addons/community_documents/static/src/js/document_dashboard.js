/** @odoo-module **/

import { registry } from "@web/core/registry";
import {
  Component,
  onWillStart,
  useState,
  onMounted,
  onWillUnmount,
  useRef,
} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class DocumentDashboard extends Component {
  setup() {
    const saved = parseInt(
      localStorage.getItem("comm_docs_sidebar_width") || "280",
      10
    );
    const sidebarWidth = Math.max(
      220,
      Math.min(520, Number.isFinite(saved) ? saved : 280)
    );

    this.orm = useService("orm");
    this.action = useService("action");
    this.user = useService("user");
    this.dropRoot = useRef("dropRoot");

    this.state = useState({
      folders: [],
      folderTree: [],
      expandedFolderIds: new Set(),
      tags: [],
      docs: [],
      folderId: null,
      tagIds: new Set(),
      search: "",
      selectedId: [],
      allSelected: false,
      selected: null,
      allowedFolderIds: [],
      isDragging: false,
      isUploading: false,
      sidebarWidth,
      isSidebarOpen: false,
      renaming: false,
      renameValue: "",
      renameExt: "",
      renameBusy: false,
    });
    this._dragDepth = 0;
    this._isFilesDrag = (ev) => {
      const types = ev.dataTransfer?.types || [];
      return Array.from(types).includes("Files");
    };

    this._showDrag = () => {
      this.state.isDragging = true;
    };

    this._hideDrag = () => {
      this._dragDepth = 0;
      this.state.isDragging = false;
    };
    this._onDragEnter = (ev) => {
      if (!this._isFilesDrag(ev)) return;
      ev.preventDefault();
      ev.dataTransfer.dropEffect = "copy";

      this._dragDepth += 1;
      this._showDrag();
    };
    this._preventBrowserFileDrop = (ev) => {
      const types = ev.dataTransfer?.types || [];
      const isFiles = Array.from(types).includes("Files");
      if (!isFiles) return;

      // nếu đang thả trong vùng dashboard -> để handler _onDrop xử lý
      const root = this.dropRoot?.el;
      if (root && root.contains(ev.target)) return;

      ev.preventDefault(); // chặn mở tab
      ev.dataTransfer.dropEffect = "copy";
    };

    this._onDragOver = (ev) => {
      if (!this._isFilesDrag(ev)) return;
      ev.preventDefault();
      ev.dataTransfer.dropEffect = "copy";
      this._showDrag();
    };

    this._onDragLeave = (ev) => {
      if (!this._isFilesDrag(ev)) return;
      ev.preventDefault();

      this._dragDepth -= 1;
      if (this._dragDepth <= 0) {
        this._hideDrag();
      }
    };

    this._onDrop = async (ev) => {
      if (!this._isFilesDrag(ev)) return;
      ev.preventDefault();
      ev.stopPropagation();

      this._hideDrag();

      const files = Array.from(ev.dataTransfer?.files || []);
      if (!files.length) return;

      await this.uploadDroppedFiles(files);
    };
    // ✅ Khi kéo ra khỏi cửa sổ browser (cancel), Chrome bắn dragleave với clientX/Y = 0
    this._onWindowDragLeave = (ev) => {
      if (!this._isFilesDrag(ev)) return;
      if (ev.clientX === 0 && ev.clientY === 0) {
        this._hideDrag();
      }
    };

    // ✅ Khi cancel kéo (ESC / thả ra ngoài), dragend đôi khi bắn
    this._onWindowDragEnd = (ev) => {
      if (!this._isFilesDrag(ev)) return;
      this._hideDrag();
    };
    onMounted(async () => {
      // chặn browser mở file khi thả ngoài dashboard
      window.addEventListener("dragover", this._preventBrowserFileDrop, true);
      window.addEventListener("drop", this._preventBrowserFileDrop, true);

      // ✅ bắt cancel kéo / rời cửa sổ
      window.addEventListener("dragleave", this._onWindowDragLeave, true);
      window.addEventListener("dragend", this._onWindowDragEnd, true);

      const el = this.dropRoot.el;
      if (!el) return;

      el.addEventListener("dragenter", this._onDragEnter);
      el.addEventListener("dragover", this._onDragOver);
      el.addEventListener("dragleave", this._onDragLeave);
      el.addEventListener("drop", this._onDrop);
    });
    onWillUnmount(() => {
      window.removeEventListener(
        "dragover",
        this._preventBrowserFileDrop,
        true
      );
      window.removeEventListener("drop", this._preventBrowserFileDrop, true);

      window.removeEventListener("dragleave", this._onWindowDragLeave, true);
      window.removeEventListener("dragend", this._onWindowDragEnd, true);

      const el = this.dropRoot.el;
      if (!el) return;

      el.removeEventListener("dragenter", this._onDragEnter);
      el.removeEventListener("dragover", this._onDragOver);
      el.removeEventListener("dragleave", this._onDragLeave);
      el.removeEventListener("drop", this._onDrop);
    });

    onWillStart(async () => {
      await this.loadSidebars();
      await this.loadFolders();
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
    const memberFolderIds = new Set(
      memberRows.map((r) => r.folder_id?.[0]).filter(Boolean)
    );

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
    this.state.tags = await this.orm.searchRead(
      "document.tag",
      [],
      ["name", "color"]
    );
  }
  async loadFolders() {
    const fields = ["name", "parent_id"];
    const folders = await this.orm.searchRead("document.folder", [], fields, {
      limit: 2000,
    });

    this.state.folders = folders;

    // mở root mặc định
    if (
      !this.state.expandedFolderIds ||
      this.state.expandedFolderIds.size === 0
    ) {
      const s = new Set();
      for (const f of folders) {
        if (!f.parent_id) s.add(f.id);
      }
      this.state.expandedFolderIds = s;
    }

    this.state.folderTree = this._buildFolderTree(
      this.state.folders,
      this.state.expandedFolderIds
    );
  }
  _buildFolderTree(folders, expandedSet) {
    const byParent = new Map();
    for (const f of folders) {
      const pid = f.parent_id ? f.parent_id[0] : 0;
      if (!byParent.has(pid)) byParent.set(pid, []);
      byParent.get(pid).push(f);
    }

    for (const arr of byParent.values()) {
      arr.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    }

    const out = [];
    const walk = (parentId, level) => {
      const children = byParent.get(parentId) || [];
      for (const f of children) {
        const hasChildren = (byParent.get(f.id) || []).length > 0;
        const isExpanded = expandedSet?.has(f.id);

        out.push({
          id: f.id,
          name: f.name,
          level,
          hasChildren,
          isExpanded,
        });

        if (hasChildren && isExpanded) {
          walk(f.id, level + 1);
        }
      }
    };
    walk(0, 0);
    return out;
  }
  onToggleFolder(ev) {
    const id = parseInt(ev.currentTarget.dataset.id, 10);
    if (!id) return;

    const s = new Set(this.state.expandedFolderIds || []);
    if (s.has(id)) s.delete(id);
    else s.add(id);

    this.state.expandedFolderIds = s;
    this.state.folderTree = this._buildFolderTree(this.state.folders, s);
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

    if (this.state.folderId)
      domain.push(["folder_id", "=", this.state.folderId]);
    if (this.state.tagIds.size)
      domain.push(["tag_ids", "in", Array.from(this.state.tagIds)]);
    if (this.state.search && this.state.search.trim())
      domain.push(["name", "ilike", this.state.search.trim()]);

    return domain;
  }

  async loadDocs() {
    const fields = [
      "name",
      "write_date",
      "owner_id",
      "folder_id",
      "mimetype",
      "attachment_id",
      "tag_ids",
      "is_link",
    ];

    const docs = await this.orm.searchRead(
      "document.document",
      this.buildDomain(),
      fields,
      { limit: 200 }
    );

    this.state.docs = docs;

    // --- giữ selection nhiều file nếu còn tồn tại ---
    const existingIds = new Set(docs.map((d) => d.id));

    // selectedIds là ARRAY
    const keptSelectedIds = (this.state.selectedIds || []).filter((id) =>
      existingIds.has(id)
    );
    this.state.selectedIds = keptSelectedIds;

    // allSelected
    this.state.allSelected =
      docs.length > 0 && keptSelectedIds.length === docs.length;

    // --- xử lý selectedId/selected (single select) ---
    // Nếu vẫn còn 1 item được chọn -> set selectedId/selected
    if (keptSelectedIds.length === 1) {
      const onlyId = keptSelectedIds[0];
      this.state.selectedId = onlyId;
      this.state.selected = docs.find((d) => d.id === onlyId) || null;
    } else {
      // multi select hoặc none -> không có selected single
      this.state.selectedId = null;
      this.state.selected = null;
    }

    // Nếu trước đó bạn có selectedId (legacy) thì ưu tiên giữ lại nếu còn tồn tại
    // (trường hợp bạn chưa chuyển hết sang selectedIds)
    if (!keptSelectedIds.length && this.state.selectedId) {
      const found = docs.find((d) => d.id === this.state.selectedId);
      if (found) {
        this.state.selectedIds = [this.state.selectedId];
        this.state.selected = found;
      } else {
        this.state.selectedId = null;
        this.state.selected = null;
      }
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
  isPdf(mimetype) {
    return (mimetype || "") === "application/pdf";
  }
  isImage(mimetype) {
    return (mimetype || "").startsWith("image/");
  }

  iconFor(mimetype, isLink) {
    if (isLink) return "🔗";
    if (!mimetype) return "📄";
    if (mimetype === "application/pdf") return "📕";
    if (mimetype.includes("spreadsheet") || mimetype.includes("excel"))
      return "📗";
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
            name: f.name, // ✅ bắt buộc để khỏi lỗi Name
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
    await this.action.doAction(
      "community_documents.action_document_add_link_wizard",
      {
        additionalContext: {
          default_folder_id: this.state.folderId || false,
        },
        onClose: async () => {
          await this.loadDocs();
        },
      }
    );
  }
  async onCreateFolder() {
    await this.action.doAction(
      "community_documents.action_document_create_folder_wizard",
      {
        additionalContext: {
          // nếu đang chọn folder thì tạo subfolder của folder đó
          default_parent_id: this.state.folderId || false,
        },
        onClose: async () => {
          await this.loadSidebars();
          // nếu bạn muốn reload docs luôn (khi user đang filter theo folder)
          await this.loadDocs();
          await this.loadFolders();
        },
      }
    );
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
          await this.loadFolders();
        },
      }
    );
  }

  async onDeleteFolder(ev) {
    const id = parseInt(ev.currentTarget.dataset.id, 10);
    if (!id) return;

    if (!confirm("Xóa folder và toàn bộ file bên trong (kể cả folder con)?"))
      return;

    try {
      const res = await this.orm.call(
        "document.folder",
        "action_delete_recursive",
        [[id]]
      );
      console.log("delete_recursive_result", res);

      // ✅ clear selection để tránh UI còn render preview attachment đã xóa
      this.state.selected = null;
      this.state.selectedId = null;
      this.state.selectedIds = [];
      this.state.allSelected = false;

      if (this.state.folderId === id) this.state.folderId = null;

      await this.loadFolders();
      await this.loadDocs();

      if (res?.still_exists_folder_ids?.length) {
        this.notification?.add?.(
          "Folder vẫn còn tồn tại do bị ràng buộc. Xem console: still_exists_folder_ids",
          { type: "warning" }
        );
      }
    } catch (e) {
      console.error(e);
      this.notification?.add?.(e?.message || "Không xóa được folder", {
        type: "danger",
      });
    }
  }

  async onShareSelected() {
    const docIds = this.state.selectedIds || [];
    const folderId = this.state.folderId; // folder đang chọn ở sidebar

    // 1) Có chọn file -> share file
    if (docIds.length) {
      return this._openShareWizardForDocs(docIds);
    }

    // 2) Không chọn file -> share folder hiện tại
    if (folderId) {
      return this._openShareWizardForFolder(folderId);
    }

    // 3) Không có gì -> cảnh báo
    this.notification?.add?.("Chọn file hoặc chọn folder để chia sẻ.", {
      type: "warning",
    });
  }

  async onShareFolder(ev) {
    ev.stopPropagation();
    const folderId = Number(ev.currentTarget.dataset.id);
    if (!folderId) return;

    await this.action.doAction(
      "community_documents.action_document_share_wizard",
      {
        additionalContext: {
          default_share_type: "folder",
          default_folder_id: folderId,
        },
        onClose: async () => {
          await this.loadSidebars();
          await this.loadDocs();
        },
      }
    );
  }
  async onDeleteSelected() {
    const id = this.state.selectedId;
    if (!id) return;

    const ok = window.confirm("Delete this file?");
    if (!ok) return;

    await this.orm.unlink("document.document", [id]);

    // reset selection
    this.state.selectedId = null;
    this.state.selected = null;

    await this.loadDocs();
  }

  async onDeleteDoc(ev) {
    ev.stopPropagation();
    const id = Number(ev.currentTarget.dataset.id);
    if (!id) return;
    if (!window.confirm("Delete this file?")) return;

    await this.orm.unlink("document.document", [id]);
    this._setSelectedIds(
      (this.state.selectedIds || []).filter((x) => x !== id)
    );
    await this.loadDocs();
  }

  async deleteSelected() {
    const ids = this.state.selectedIds || [];
    if (!ids.length) return;
    if (!window.confirm(`Delete ${ids.length} file(s)?`)) return;

    await this.orm.unlink("document.document", ids);
    this.clearSelection();
    await this.loadDocs();
  }

  downloadSelected() {
    const ids = this.state.selectedIds || [];
    if (!ids.length) return;

    // 1 file -> tải thẳng, không zip
    if (ids.length === 1) {
      const id = ids[0];
      const d = (this.state.docs || []).find((x) => x.id === id);
      if (!d) return;

      const attId = d.attachment_id && d.attachment_id[0];
      if (!attId) return;

      window.location.href = `/web/content/${attId}?download=1`;
      return;
    }

    // >1 file -> tải zip (1 request, không bị browser chặn)
    const url = `/community_documents/download_zip?ids=${encodeURIComponent(
      ids.join(",")
    )}`;
    window.location.href = url;
  }

  _docById(id) {
    return (this.state.docs || []).find((d) => d.id === id);
  }

  _setSelectedIds(idsArray) {
    // idsArray là Array<number>
    const ids = Array.isArray(idsArray) ? idsArray : [];
    this.state.selectedIds = ids;

    // allSelected
    this.state.allSelected =
      this.state.docs.length > 0 && ids.length === this.state.docs.length;

    if (ids.length === 1) {
      const onlyId = ids[0];
      this.state.selectedId = onlyId;
      this.state.selected = this._docById(onlyId) || null;
    } else {
      this.state.selectedId = null;
      this.state.selected = null;
    }
  }

  _toggleId(arr, id) {
    if (arr.includes(id)) return arr.filter((x) => x !== id);
    return [...arr, id];
  }
  onToggleDoc(ev) {
    const id = Number(ev.currentTarget.dataset.id);
    this._setSelectedIds(this._toggleId(this.state.selectedIds, id));
  }
  onDocClick(ev) {
    const id = Number(ev.currentTarget.dataset.id);
    const idx = this.state.docs.findIndex((d) => d.id === id);

    if (
      ev.shiftKey &&
      this.state.lastIndex !== null &&
      this.state.lastIndex !== undefined
    ) {
      const start = Math.min(this.state.lastIndex, idx);
      const end = Math.max(this.state.lastIndex, idx);

      const rangeIds = this.state.docs.slice(start, end + 1).map((d) => d.id);
      const merged = Array.from(
        new Set([...this.state.selectedIds, ...rangeIds])
      );
      this._setSelectedIds(merged);
      return;
    }

    if (ev.ctrlKey || ev.metaKey) {
      this._setSelectedIds(this._toggleId(this.state.selectedIds, id));
      this.state.lastIndex = idx;
      return;
    }

    this._setSelectedIds([id]);
    this.state.lastIndex = idx;
  }
  clearSelection() {
    this._setSelectedIds([]);
    this.state.lastIndex = null;
  }

  toggleSelectAll() {
    if (!this.state.docs?.length) return;
    if (this.state.allSelected) {
      this.clearSelection();
    } else {
      this._setSelectedIds(this.state.docs.map((d) => d.id));
    }
  }
  _getExt(name) {
    const n = (name || "").trim();
    const i = n.lastIndexOf(".");
    return i > -1 ? n.slice(i + 1).toLowerCase() : "";
  }

  fileType(d) {
    if (d?.is_link) return "link";

    const mt = (d?.mimetype || "").toLowerCase();
    const ext = this._getExt(d?.name);

    if (mt === "application/pdf" || ext === "pdf") return "pdf";

    if (
      mt.includes("spreadsheet") ||
      mt.includes("excel") ||
      ["xls", "xlsx", "csv"].includes(ext)
    )
      return "excel";

    if (mt.includes("word") || ["doc", "docx"].includes(ext)) return "word";

    if (
      mt.includes("presentation") ||
      mt.includes("powerpoint") ||
      ["ppt", "pptx"].includes(ext)
    )
      return "ppt";

    if (
      mt.startsWith("image/") ||
      ["png", "jpg", "jpeg", "webp", "gif"].includes(ext)
    )
      return "image";
    if (mt.startsWith("video/") || ["mp4", "mov", "avi", "mkv"].includes(ext))
      return "video";
    if (mt.startsWith("text/") || ["txt", "md"].includes(ext)) return "text";
    if (mt.includes("zip") || ["zip", "rar", "7z"].includes(ext)) return "zip";

    return "file";
  }

  fileIconClass(d) {
    const t = this.fileType(d);
    const map = {
      pdf: "fa fa-file-pdf-o",
      word: "fa fa-file-word-o",
      excel: "fa fa-file-excel-o",
      ppt: "fa fa-file-powerpoint-o",
      image: "fa fa-file-image-o",
      video: "fa fa-file-video-o",
      text: "fa fa-file-text-o",
      zip: "fa fa-file-archive-o",
      link: "fa fa-link",
      file: "fa fa-file-o",
    };
    return `o_comm_docs_file_i ${map[t] || map.file}`;
  }

  fileIconWrapClass(d) {
    return `type-${this.fileType(d)}`;
  }
  async uploadDroppedFiles(files) {
    let folderId = this.state.folderId;
    if (!folderId) folderId = this.state.folders?.[0]?.id || null;
    if (!folderId) {
      this.notification?.add?.("Chưa có folder. Tạo folder trước.", {
        type: "danger",
      });
      return;
    }

    this.state.isUploading = true;
    try {
      for (const f of files) {
        if (!f?.name) continue;
        await this._uploadSingleFileToFolder(f, folderId);
      }
      await this.loadDocs();
    } catch (e) {
      console.error(e);
      this.notification?.add?.(e?.message || "Upload failed", {
        type: "danger",
      });
    } finally {
      this.state.isUploading = false;
    }
  }

  async _uploadSingleFileToFolder(file, folderId) {
    const { base64, mimetype } = await this._readFileAsBase64(file);

    // 1) create attachment (chưa cần res_model/res_id)
    const attIds = await this.orm.create("ir.attachment", [
      {
        name: file.name,
        datas: base64,
        mimetype: mimetype || "application/octet-stream",
        type: "binary",
      },
    ]);
    const attId = Array.isArray(attIds) ? attIds[0] : attIds;

    // 2) create document (đủ required: name + folder_id)
    const docIds = await this.orm.create("document.document", [
      {
        name: file.name,
        folder_id: folderId,
        attachment_id: attId,
        mimetype: mimetype || "application/octet-stream",
        is_link: false,
      },
    ]);
    const docId = Array.isArray(docIds) ? docIds[0] : docIds;

    // 3) gắn res_model/res_id cho attachment để “thuộc” document
    await this.orm.write("ir.attachment", [attId], {
      res_model: "document.document",
      res_id: docId,
    });

    return docId;
  }

  _readFileAsBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error("FileReader error"));
      reader.onload = () => {
        const result = reader.result || "";
        // result dạng: data:<mimetype>;base64,xxxx
        const comma = result.indexOf(",");
        const base64 = comma >= 0 ? result.slice(comma + 1) : "";
        const mimetype =
          file.type ||
          result.slice(5, result.indexOf(";")) ||
          "application/octet-stream";
        resolve({ base64, mimetype });
      };
      reader.readAsDataURL(file);
    });
  }
  onSidebarResizeStart(ev) {
    ev.preventDefault();
    ev.stopPropagation();

    const startX = ev.clientX;
    const startW = this.state.sidebarWidth || 280;

    const minW = 220;
    const maxW = 520;

    const onMove = (e) => {
      const dx = e.clientX - startX;
      let w = startW + dx;
      w = Math.max(minW, Math.min(maxW, w));
      this.state.sidebarWidth = w;
    };

    const onUp = () => {
      window.removeEventListener("mousemove", onMove, true);
      window.removeEventListener("mouseup", onUp, true);
      localStorage.setItem(
        "comm_docs_sidebar_width",
        String(this.state.sidebarWidth || startW)
      );
      document.body.classList.remove("o_comm_docs_resizing");
    };

    document.body.classList.add("o_comm_docs_resizing");
    window.addEventListener("mousemove", onMove, true);
    window.addEventListener("mouseup", onUp, true);
  }
  toggleSidebar() {
    this.state.isSidebarOpen = !this.state.isSidebarOpen;
  }
  _openShareWizardForDocs(docIds) {
    // Nếu bạn đang dùng wizard share file
    return this.action.doAction({
      type: "ir.actions.act_window",
      name: "Share",
      res_model: "document.share.wizard",
      views: [[false, "form"]],
      target: "new",
      context: {
        default_document_ids: docIds, // Many2many
        default_share_type: "document", // optional
      },
    });
  }

  _openShareWizardForFolder(folderId) {
    // Nếu bạn đang dùng wizard share folder (hoặc cùng wizard nhưng có folder_id)
    return this.action.doAction({
      type: "ir.actions.act_window",
      name: "Share",
      res_model: "document.share.wizard",
      views: [[false, "form"]],
      target: "new",
      context: {
        default_folder_id: folderId, // Many2one
        default_share_type: "folder", // optional
      },
    });
  }
  _openMoveCopyWizard(operation) {
    const ids = this.state.selectedIds || [];
    if (!ids.length) return;

    this.action.doAction(
      "community_documents.action_document_move_copy_wizard",
      {
        additionalContext: {
          default_operation: operation,
          default_document_ids: ids,
          default_folder_id: this.state.folderId || false, // optional
        },
        onClose: async () => {
          // clear selection sau thao tác
          this.state.selected = null;
          this.state.selectedId = null;
          this.state.selectedIds = [];
          this.state.allSelected = false;

          await this.loadFolders(); // optional
          await this.loadDocs(); // ✅ bắt buộc để thấy file đã move/copy
        },
      }
    );
  }

  onCopySelected() {
    this._openMoveCopyWizard("copy");
  }

  onMoveSelected() {
    this._openMoveCopyWizard("move");
  }
  async onRenameSelected() {
    const ids = this.state.selectedIds || [];
    if (ids.length !== 1) {
      this.notification?.add?.("Chỉ đổi tên khi chọn đúng 1 file.", {
        type: "warning",
      });
      return;
    }

    const docId = ids[0];
    const doc = (this.state.docs || []).find((d) => d.id === docId);
    const currentName = doc?.name || "";

    const newName = window.prompt("Nhập tên mới:", currentName);
    if (newName === null) return; // cancel

    const trimmed = (newName || "").trim();
    if (!trimmed) {
      this.notification?.add?.("Tên không được để trống.", { type: "warning" });
      return;
    }

    await this.orm.call("document.document", "action_rename", [
      [docId],
      trimmed,
    ]);

    // reload danh sách + refresh selection
    await this.loadDocs();
    this.state.selectedId = docId;
    this.state.selected =
      (this.state.docs || []).find((d) => d.id === docId) || null;
  }
  _splitFilename(filename) {
    filename = (filename || "").trim();
    if (!filename) return { base: "", ext: "" };
    const idx = filename.lastIndexOf(".");
    if (idx > 0 && idx < filename.length - 1) {
      return { base: filename.slice(0, idx), ext: filename.slice(idx) }; // ext includes "."
    }
    return { base: filename, ext: "" };
  }

  _docFilename(doc) {
    // ưu tiên attachment filename nếu có
    // searchRead thường trả attachment_id=[id,name] nên không có datas_fname; dùng doc.name là chính
    return doc && doc.name ? doc.name : "";
  }
}

DocumentDashboard.template = "community_documents.DocumentDashboard";
registry
  .category("actions")
  .add("community_documents.dashboard", DocumentDashboard);
