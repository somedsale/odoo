/** @odoo-module */

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { Card } from "./card";
import { ChartRenderer } from "./chart_render";
import { useService } from "@web/core/utils/hooks"; // ✅ lấy service

export class AccountingDashboard extends Component {
  setup() {
    this.rpc = useService("rpc"); // ✅ dùng service rpc

    this.state = useState({
      dashboardData: {
        quotations: 0,
        orders: 0,
        revenues: 0,
        avg_order: 0,
      },
    });

    onWillStart(async () => {
      await this.fetchDashboardData();
    });
  }

  async fetchDashboardData() {
    try {
      const result = await this.rpc("/accounting/dashboard/data", {}); // ✅ gọi qua this.rpc
      console.log("Fetched data:", result);
      this.state.dashboardData = { ...this.state.dashboardData, ...result };
    } catch (error) {
      console.error("Error fetching dashboard data:", error);
    }
  }
}

AccountingDashboard.template = "owl.AccountingDashboardMain";
AccountingDashboard.components = { Card, ChartRenderer };

registry
  .category("actions")
  .add("accounting_dashboard_main", AccountingDashboard);
