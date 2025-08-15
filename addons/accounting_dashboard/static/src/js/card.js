/** @odoo-module */

import { Component } from "@odoo/owl";

export class Card extends Component {
  // props nhận từ parent
  static props = {
    name: { type: String },
    value: { type: Number },
    percentage: { type: Number },
  };
}

Card.template = "owl.Card";
