/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
const { Component, useRef, useState, onMounted, onWillUnmount } = owl;

export class DomainSelectorTextField extends Component {
  static template = "FieldYear";
  static props = {
    ...standardFieldProps,
  };

  setup() {
    super.setup();
    this.input = useRef("inputyear");
    const currentYear = new Date().getFullYear();
    this.state = useState({
      year: this.props.value || currentYear,
    });
    this.datepicker = null;

    onMounted(() => {
      if (this.input.el) {
        this.datepicker = $(this.input.el);
        this.datepicker
          .datepicker({
            minViewMode: "years",
            format: "yyyy",
            autoclose: true,
            showOnFocus: false,
          })
          .on("changeDate", (ev) => this.onSelectYear(ev));
      }
    });

    onWillUnmount(() => {
      if (this.datepicker) {
        this.datepicker.datepicker("destroy");
      }
    });
  }

  _onSelectYearField(ev) {
    if (this.datepicker) {
      this.datepicker.datepicker("show");
    }
  }

  async onSelectYear(ev) {
    if (!ev.date) return;
    const newYear = ev.date.getFullYear();
    this.state.year = newYear;

    const toUpdate = {};
    toUpdate[this.props.name] = this.state.year;
    await this.props.record.update(toUpdate);
  }
}

registry.category("fields").add("yearpicker", {
  component: DomainSelectorTextField,
  displayName: "Year Picker",
  supportedTypes: ["char", "integer", "date"], // tùy field bạn dùng
});
