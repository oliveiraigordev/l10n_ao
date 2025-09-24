/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";

import { L10nAOCashFlowMapListRenderer } from "./l10n_ao_cash_flow_map_list_render";
//import { L10nAOCashFlowMapListController } from "./l10n_ao_cash_flow_map_list_controller";


export const L10nAOCashFlowMapListView = Object.assign({}, listView, {
    //Controller: L10nAOCashFlowMapListController,
    //searchMenuTypes: ["groupBy"],
    Renderer: L10nAOCashFlowMapListRenderer,
});

registry.category("views").add("l10n_ao_report_cash_flow_map_list", L10nAOCashFlowMapListView);