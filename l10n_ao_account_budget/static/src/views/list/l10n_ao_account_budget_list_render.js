/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { getFormattedValue } from "@web/views/utils";
import { registry } from "@web/core/registry";

import {
    onMounted,
    onWillUpdateProps,
    onPatched,
    useState,
    useExternalListener
} from "@odoo/owl";

const MONTHS_AVAILABILITY = [
    { id:1, month: "january", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:2, month: "february", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:3, month: "march", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:4, month: "april", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:5, month: "may", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:6, month: "june", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:7, month: "july", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:8, month: "august", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:9, month: "september", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:10, month: "october", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:11, month: "november", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:12, month: "december", balance: 0, variance: 0, accomplished: 0, record: null}
]

const MONTHS_INITIAL_BALANCE = [
    { id:1, month: "january", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:2, month: "february", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:3, month: "march", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:4, month: "april", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:5, month: "may", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:6, month: "june", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:7, month: "july", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:8, month: "august", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:9, month: "september", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:10, month: "october", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:11, month: "november", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:12, month: "december", balance: 0, variance: 0, accomplished: 0, record: null}
]

const MONTHS_CASH_IN_COMING = [
    { id:1, month: "january", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:2, month: "february", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:3, month: "march", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:4, month: "april", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:5, month: "may", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:6, month: "june", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:7, month: "july", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:8, month: "august", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:9, month: "september", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:10, month: "october", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:11, month: "november", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:12, month: "december", balance: 0, variance: 0, accomplished: 0, record: null}
]
const MONTHS_CASH_OUT_COMING = [
    { id:1, month: "january", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:2, month: "february", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:3, month: "march", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:4, month: "april", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:5, month: "may", balance: 0, variance: 0, accomplished: 0, record: null},
    {id:6, month: "june", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:7, month: "july", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:8, month: "august", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:9, month: "september", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:10, month: "october", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:11, month: "november", balance: 0, variance: 0, accomplished: 0, record: null},
     {id:12, month: "december", balance: 0, variance: 0, accomplished: 0, record: null}
]

export class L10nAOAccountBudgetListRenderer extends ListRenderer {
    setup() {
        super.setup();
        this.state = useState({...this.state,
            availability: [],
            selectedBudget: null,
            initial_balance: [],
            cash_in_coming: [],
            cash_out_coming: [],
            cash_in_coming_total_balance: 0,
            cash_in_coming_total_accomplished: 0,
            cash_in_coming_total_variance: 0,

            cash_out_coming_total_balance: 0,
            cash_out_coming_total_accomplished: 0,
            cash_out_coming_total_variance: 0,

            total_balance: 0,
            total_accomplished: 0,
            total_variance: 0,
            initial_total_balance: 0,
            initial_total_accomplished: 0,
            initial_total_variance: 0,
            showInitialBalance: false
        })


         //TODO: Apagar a linha abaixo
         useExternalListener(window, "click", this.onWindowClick);
    }
    async onWindowClick(ev){
    //TODO: Apagar este metodo
        console.log(ev)

    }
    async onSelectBudget(event, budget){
        this.state.selectedBudget = budget;
        this.state.showInitialBalance = budget.budget_type == "financial"? true : false;
        await this.props.getBudget(budget.budget_year, this);

        setTimeout(() => {
            if(this.state.showInitialBalance)
                this.updateBalanceAvailability();
        }, 100);
    }
    updateBalanceAvailability(){
        for (var a=0; a <= MONTHS_AVAILABILITY.length; a++){
              let data = MONTHS_AVAILABILITY;
              let initial_balance = MONTHS_INITIAL_BALANCE;
              let cash_in_coming = MONTHS_CASH_IN_COMING;
              let cash_out_coming = MONTHS_CASH_OUT_COMING;

              initial_balance = MONTHS_INITIAL_BALANCE[a];
              data = MONTHS_AVAILABILITY[a];
              cash_in_coming = MONTHS_CASH_IN_COMING[a];
              cash_out_coming = MONTHS_CASH_OUT_COMING[a];

              if(data){

                if(this.state.showInitialBalance){
                    if(data.month == "january"){
                        initial_balance.balance = this.state.selectedBudget.initial_balance;
                        initial_balance.accomplished = 0;
                    }else{
                        initial_balance.balance = MONTHS_AVAILABILITY[a - 1].balance;
                        initial_balance.accomplished = MONTHS_AVAILABILITY[a - 1].accomplished;
                    }
                    data.balance = initial_balance.balance;
                    data.accomplished = initial_balance.accomplished;

                }else{
                    data.balance = 0;
                    data.accomplished = 0;
                }
                cash_out_coming.balance = 0;
                cash_in_coming.balance = 0;

                cash_out_coming.accomplished = 0;
                cash_in_coming.accomplished = 0;

                this.props.list.records.forEach( (record) =>{
                    if(record.data.budget_line_type == "out_coming"){
                        data.balance = data.balance - record.data[data.month];
                        data.accomplished = data.accomplished - record.data[data.month + "_accomplished"];

                        cash_out_coming.balance = cash_out_coming.balance + record.data[data.month];
                        cash_out_coming.accomplished = cash_out_coming.accomplished + record.data[data.month + "_accomplished"];
                    }
                    else if(record.data.budget_line_type == "in_coming"){
                        data.balance = data.balance + record.data[data.month];
                        data.accomplished = data.accomplished + record.data[data.month + "_accomplished"];

                        cash_in_coming.balance = cash_in_coming.balance + record.data[data.month];
                        cash_in_coming.accomplished = cash_in_coming.accomplished + record.data[data.month + "_accomplished"];
                    }
                    data.record = record;
                    cash_in_coming.record = record;
                    cash_out_coming.record = record;

                    if(this.state.showInitialBalance){
                        initial_balance.record = record;
                    }
                });

                if(data.balance != 0){
                    data.variance = Math.round(- ((data.balance - data.accomplished) / data.balance) * 100);
                }else
                    data.variance = 0;

                if(cash_out_coming.balance != 0){
                    cash_out_coming.variance = Math.round(- ((cash_out_coming.balance - cash_out_coming.accomplished) / cash_out_coming.balance) * 100);
                }else
                    cash_out_coming.variance = 0;

                if(cash_in_coming.balance != 0){
                    cash_in_coming.variance = Math.round(- ((cash_in_coming.balance - cash_in_coming.accomplished) / cash_in_coming.balance) * 100);
                }else
                    cash_in_coming.variance = 0;
              }
        }

        if(this.state.showInitialBalance){
            this.state.total_balance = 0;
            this.state.total_accomplished = 0;
            this.state.availability = [];
            this.state.availability = MONTHS_AVAILABILITY;

            this.state.availability.forEach( (elem) =>{
                this.state.total_balance += elem.balance;
                this.state.total_accomplished += elem.accomplished;
            });

            if(this.state.total_balance != 0)
                this.state.total_variance = Math.round((-(this.state.total_balance - this.state.total_accomplished) / this.state.total_balance) * 100);


            this.state.initial_total_balance = 0;
            this.state.initial_total_accomplished = 0;
            this.state.initial_balance = [];
            this.state.initial_balance = MONTHS_INITIAL_BALANCE;

            this.state.initial_balance.forEach( (elem) =>{
                this.state.initial_total_balance += elem.balance;
                this.state.initial_total_accomplished += elem.accomplished;
            });
            if(this.state.initial_total_balance != 0)
                this.state.initial_total_variance = Math.round((-(this.state.initial_total_balance - this.state.initial_total_accomplished) / this.state.initial_total_balance) * 100);


            this.state.cash_in_coming = MONTHS_CASH_IN_COMING;
            this.state.cash_in_coming_total_balance = 0;
            this.state.cash_in_coming_total_accomplished = 0;
            this.state.cash_in_coming_total_variance = 0;

            this.state.cash_in_coming.forEach( (elem) =>{
                this.state.cash_in_coming_total_balance += elem.balance;
                this.state.cash_in_coming_total_accomplished += elem.accomplished;
            });
            if(this.state.cash_in_coming_total_balance != 0)
                this.state.cash_in_coming_total_variance = Math.round((-(this.state.cash_in_coming_total_balance - this.state.cash_in_coming_total_accomplished) / this.state.cash_in_coming_total_balance) * 100);

            this.state.cash_out_coming = MONTHS_CASH_OUT_COMING;
            this.state.cash_out_coming_total_balance = 0;
            this.state.cash_out_coming_total_accomplished = 0;
            this.state.cash_out_coming_total_variance = 0;

            this.state.cash_out_coming.forEach( (elem) =>{
                this.state.cash_out_coming_total_balance += elem.balance;
                this.state.cash_out_coming_total_accomplished += elem.accomplished;
            });
            if(this.state.cash_out_coming_total_balance != 0)
                this.state.cash_out_coming_total_variance = Math.round((-(this.state.cash_out_coming_total_balance - this.state.cash_out_coming_total_accomplished) / this.state.cash_out_coming_total_balance) * 100);
        }


    }
    _getFormattedValue(record, fieldName, balance){

        if(record){
            const field = record.fields[fieldName];
            const formatter = registry.category("formatters").get(field.type, (val) => val);
            return formatter(balance);
        }
    }


}

L10nAOAccountBudgetListRenderer.template = "l10n_ao_account_budget.L10nAOAccountBudgetListRenderer";
L10nAOAccountBudgetListRenderer.props = [...L10nAOAccountBudgetListRenderer.props, "getBudget?", "budgetList?"]
