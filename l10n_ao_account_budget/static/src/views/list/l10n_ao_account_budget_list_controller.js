/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { useModel } from "@web/views/model";
import { evaluateExpr } from "@web/core/py_js/py";
import { usePager } from "@web/search/pager_hook";

import {
    onWillStart,
    useState,
    onMounted
} from "@odoo/owl";


export class L10nAOAccountBudgetListController extends ListController {
    setup(){
        super.setup();
        this.state = useState({...this.state,
            budgetList: [],
        });
        this.initialDomain = this.props.domain;
        this.props.domain = [...this.props.domain, ["budget_year", "=", (new Date()).getFullYear()]];


        onMounted(() => {
          $("#budget_year_"+ (new Date()).getFullYear()).addClass("selected").click();
        });

        onWillStart( async () => {
            this.state.budgetList = await this.model.orm.searchRead("account.budget", [...this.initialDomain],
                ["id", "name", "initial_balance", "budget_year", "budget_type"],
                {
                    order: "id DESC"
                }
            );
        });


        usePager(() => {
            const list = this.model.root;
            const { count, hasLimitedCount, isGrouped, limit, offset } = list;
            return {
                offset: offset,
                limit: limit,
                total: count,
                onUpdate: async ({ offset, limit }, hasNavigated) => {
                    if (this.model.root.editedRecord) {
                        if (!(await this.model.root.editedRecord.save())) {
                            return;
                        }
                    }
                    await list.load({ limit, offset });
                    this.render(true);
                    if (hasNavigated) {
                        this.onPageChangeScroll();
                    }
                    // Re-render initial balance, availability and cash flow
                    this.parent.updateBalanceAvailability();
                },
                updateTotal: !isGrouped && hasLimitedCount ? () => list.fetchCount() : undefined,
            };
        });
    }
    async getBudget(year, parent){
        this.parent = parent
        $(".l10n_ao_account_budget_search_panel ul li ").removeClass("selected");
        $("#budget_year_" + year).addClass("selected");

        this.model.rootParams.domain = [...this.initialDomain, ["budget_year", "=", "" + year]];

        await this.model.load();
    }
}

L10nAOAccountBudgetListController.template = "l10n_ao_account_budget.L10nAOAccountBudgetListController";
