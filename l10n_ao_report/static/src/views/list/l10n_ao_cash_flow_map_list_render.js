/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { getFormattedValue } from "@web/views/utils";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { onWillStart, useState , onWillUpdateProps } from "@odoo/owl";

import { qweb } from "web.core";

export class L10nAOCashFlowMapListRenderer extends ListRenderer {
    setup() {
        super.setup();

        this.actionService = useService("action");
        this.orm = useService("orm");
        var shouldCallOnPatched = true;

        this.state = useState({...this.state,
            credit_init_total_balance: 0,
            debit_init_total_balance: 0,
            amount_init_total_balance: 0,

            credit_accumulated_total_balance: 0,
            debit_accumulated_total_balance: 0,
            amount_accumulated_total_balance: 0,

            showInitialBalance: true
        });

        onWillStart(async () => {
            this.getCashFlowMapAmountTotal();
            this.getAmountAccumulatedTotal();
            shouldCallOnPatched = false;
        });

        onWillUpdateProps((nextProps) => {
            // Call my method getUpdateAmountTotal
            this.getUpdateAmountTotal(nextProps.list);
        });

    }

    async getCashFlowMapAmountTotal(){

        this.props.list.groups.forEach( (group) =>{

            let debit = group.aggregates.debit
            let credit = group.aggregates.credit
            let balance = group.aggregates.balance

            if(debit != 0){
                this.state.debit_init_total_balance += debit;
            }

            if(credit != 0){
               this.state.credit_init_total_balance += credit;
            }

            if(balance != 0){
                this.state.amount_init_total_balance += balance;
            }

        });
    }

    async getAmountAccumulatedTotal(){

       var amount_values = await this.orm.call(
            "cash.flow.statement.map", "get_amount_accumulated_total",
            [[]],
            {'domain': this.props.list.domain, 'domain_selected': false}
        );

       this.state.credit_accumulated_total_balance = amount_values.credit_total
//       + this.state.credit_init_total_balance
       this.state.debit_accumulated_total_balance = amount_values.debit_balance
//       + this.state.debit_init_total_balance
       this.state.amount_accumulated_total_balance = amount_values.balance_total
//        + this.state.amount_init_total_balance
    }

    async getUpdateAmountTotal(list){

        this.state.credit_init_total_balance = 0
        this.state.debit_init_total_balance = 0
        this.state.amount_init_total_balance = 0
        this.state.debit_init_total_balance = 0
        this.state.credit_init_total_balance = 0
        this.state.amount_init_total_balance = 0

        if(list.groups){

            list.groups.forEach( (group) =>{

                let debit = group.aggregates.debit
                let credit = group.aggregates.credit
                let balance = group.aggregates.balance

                if(debit != 0){
                    this.state.debit_init_total_balance += debit;
                }

                if(credit != 0){
                   this.state.credit_init_total_balance += credit;
                }

                if(balance != 0){
                    this.state.amount_init_total_balance += balance;
                }

            });

        } else{

                let domain = list.domain
                var amount_values = await this.orm.call(
                    "cash.flow.statement.map", "get_amount_total",
                    [[]],
                    {'domain_selected': list.domain}
                );

                this.state.credit_init_total_balance = amount_values.credit_total
                this.state.debit_init_total_balance = amount_values.debit_balance
                this.state.amount_init_total_balance = amount_values.balance_total

        }

       var amount_values = await this.orm.call(
            "cash.flow.statement.map", "get_amount_accumulated_total",
            [[]],
            {'domain': list.domain, 'domain_selected': list.domain}
        );

       this.state.credit_accumulated_total_balance = amount_values.credit_total
//       + this.state.credit_init_total_balance
       this.state.debit_accumulated_total_balance = amount_values.debit_balance
//       + this.state.debit_init_total_balance
       this.state.amount_accumulated_total_balance = amount_values.balance_total
//        + this.state.amount_init_total_balance
    }

}

L10nAOCashFlowMapListRenderer.template = "l10n_ao_report.L10nAOCashFlowMapListRenderer";
L10nAOCashFlowMapListRenderer.props = [...L10nAOCashFlowMapListRenderer.props]
