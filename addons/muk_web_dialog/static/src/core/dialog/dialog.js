/** @odoo-module **/

import { session } from "@web/session";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { browser } from "@web/core/browser/browser";
import { Dialog } from "@web/core/dialog/dialog";

const STORAGE_KEY = "mk_dialog_size"; // chỉ lưu 'fs' khi đang phóng to

patch(Dialog.prototype, {
  setup() {
    super.setup();
    this.ui = useService("ui");

    // size gốc của dialog (theo props)
    this.data.initalSize = this.props?.size || "lg";

    // khôi phục trạng thái fullscreen nếu trước đó đang bật
    const saved = browser.localStorage.getItem(STORAGE_KEY); // 'fs' hoặc null
    const wantFs = saved === "fs" || session.dialog_size === "maximize";

    this.data.size = wantFs ? "fs" : this.data.initalSize;

    // đồng bộ env.dialogData để khi dialog recreate vẫn đúng size
    if (this.env?.dialogData) {
      this.env.dialogData.initalSize = this.data.initalSize;
      this.env.dialogData.size = this.data.size;
    }
  },

  _notifyDialogResized() {
    this.ui?.bus?.trigger("resize");
    window.dispatchEvent(new Event("resize"));
  },

  toggleDialogSize() {
    const current =
      this.env?.dialogData?.size || this.data.size || this.props?.size || "lg";
    const initial =
      this.env?.dialogData?.initalSize || this.data.initalSize || "lg";

    const newSize = current === "fs" ? initial : "fs";

    // set size
    if (this.env?.dialogData) {
      this.env.dialogData.size = newSize;
      this.env.dialogData.initalSize = initial;
    }
    this.data.size = newSize;

    // persist để "Load data" / reload view không bị tụt size
    if (newSize === "fs") {
      session.dialog_size = "maximize";
      browser.localStorage.setItem(STORAGE_KEY, "fs");
    } else {
      session.dialog_size = "normal";
      browser.localStorage.removeItem(STORAGE_KEY);
    }

    browser.setTimeout(() => this._notifyDialogResized(), 250);
  },
});
