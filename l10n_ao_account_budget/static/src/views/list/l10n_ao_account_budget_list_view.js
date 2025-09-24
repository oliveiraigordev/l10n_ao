/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";

import { L10nAOAccountBudgetListRenderer } from "./l10n_ao_account_budget_list_render";
import { L10nAOAccountBudgetListController } from "./l10n_ao_account_budget_list_controller";


export const L10nAOAccountBudgetListView = Object.assign({}, listView, {
    Controller: L10nAOAccountBudgetListController,
    searchMenuTypes: ["groupBy"],
    Renderer: L10nAOAccountBudgetListRenderer,
});

registry.category("views").add("l10n_ao_account_budget_list", L10nAOAccountBudgetListView);