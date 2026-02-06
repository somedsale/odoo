/** @odoo-module **/

import { Component } from "@odoo/owl";

export class ProposalSheetPopover extends Component {
    static template = "proposal_sheet_popup.ProposalSheetPopover";
    static props = {
        close: { type: Function, optional: true },
        proposalInfo: { type: Object },
    };
}
