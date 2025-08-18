/** @odoo-module */

import { Component } from "@odoo/owl";

export class Card extends Component {
  // props nhận từ parent
  static props = {
    name: { type: String },
    value: { type: Number },
    percentage: { type: Number },
  };
  get formattedValue() {
    const num = this.props.value;
    if (num >= 1_000_000_000) {
      return (num / 1_000_000_000).toFixed(1) + " Tỷ";
    } else if (num >= 1_000_000) {
      return (num / 1_000_000).toFixed(1) + " Triệu";
    } else if (num >= 1_000) {
      return (num / 1_000).toFixed(1) + " Ngàn";
    }
    return num;
  }
}

Card.template = "owl.Card";
