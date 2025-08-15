/** @odoo-module */

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { Card } from "./card";
import { ChartRenderer } from "./chart_render";
import { rpc } from "@web/core/rpc";

export class AccountingDashboard extends Component {
  setup() {
    // Initialize state to store dashboard data
    this.state = useState({
      dashboardData: {
        quotations: 0,
        orders: 0,
        revenues: 0,
        avg_order: 0,
      },
    });

    // Fetch data when the component is about to start
    onWillStart(async () => {
      await this.fetchDashboardData();
    });
  }

  // Method to fetch data from the controller
  async fetchDashboardData() {
    try {
      const result = await rpc.query({
        route: "/accounting/dashboard/data", // Call the controller's JSON route
        params: {}, // Optional: add parameters if needed
      });
      console.log("Fetched data:", result); // Debug: verify the response
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
