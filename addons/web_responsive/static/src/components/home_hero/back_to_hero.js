/** @odoo-module **/
/* License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl). */

import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";

class BackToHeroSystray extends Component {
    _onClick() {
        window.location.assign("/web");
    }
}

BackToHeroSystray.template = xml`
    <div class="o-dropdown dropdown o-dropdown--no-caret">
        <button
            role="button"
            type="button"
            title="Back to Hero"
            class="dropdown-toggle o-dropdown--narrow"
            t-on-click="_onClick">
            <i class="fa fa-home fa-lg px-1"/>
        </button>
    </div>
`;

registry
    .category("systray")
    .add("BackToHeroSystray", { Component: BackToHeroSystray }, { sequence: 101 });