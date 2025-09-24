/** @odoo-module */

import { TimeOffCalendarController } from '@hr_holidays/views/calendar/calendar_controller';

import { L10nTimeOffCalendarFilterPanel } from './filter_panel/calendar_filter_panel';

import { useState, onWillStart , onMounted} from "@odoo/owl";

import { qweb } from "web.core";

export class L10nAOTimeOffCalendarController  extends TimeOffCalendarController {
    setup() {
        super.setup();

        this.vacationState = useState({
            total_balance_days: [],
            vacation_logo: [],
            year_selected: [],
        });

        onWillStart(async () => {
            this.getVacationBalanceByEmployeeId();
            this.getVacationLogo();
            this.getYearSelected();
        });

        onMounted(() => {
            let $sidebar = $(".o_calendar_sidebar");
            if($sidebar.length > 0) {
                $sidebar.prepend(qweb.render("l10n_ao_hr_holidays.DaysToEnjoy", {
                    total_balance_days: this.vacationState.total_balance_days,
                    vacation_logo: this.vacationState.vacation_logo,
                    year_selected: this.model.date.year
                }))
            }
        });
    }

    async setDate(move){
        await super.setDate(move);
        //this.current_year = this.model.date.year
        $("#DaysToEnjoy").remove();

        var total_balance_days = await this.orm.call(
            "vacation.balance.report", "getVacationBalance",
            [[]],
            {'user_id': this.model.user.userId, 'year_selected': this.model.date.year}
        );

        var year_selected = await this.orm.call(
            "vacation.balance.report", "getYearSelected",
            [[]],
            {'user_id': this.model.user.userId, 'year_selected': this.model.date.year}
        );

        this.vacationState.year_selected = year_selected
        this.vacationState.total_balance_days = total_balance_days

        let $sidebar = $(".o_calendar_sidebar");
        if($sidebar.length > 0) {
            $sidebar.prepend(qweb.render("l10n_ao_hr_holidays.DaysToEnjoy", {
                total_balance_days: this.vacationState.total_balance_days,
                vacation_logo: this.vacationState.vacation_logo,
                year_selected: this.vacationState.year_selected
            }))
        }
    }

     async getVacationBalanceByEmployeeId(){
       var total_balance_days = await this.orm.call(
            "vacation.balance.report", "getVacationBalance",
            [[]],
            {'user_id': this.model.user.userId, 'year_selected': this.model.date.year}
        );

        this.vacationState.total_balance_days = total_balance_days
        return this.vacationState.total_balance_days
    }

    async getVacationLogo(){
        var image_src = await this.orm.call(
        "hr.leave.type",'getVacationLogo',
        [[]],
        );

        this.vacationState.vacation_logo = image_src
        return this.vacationState.vacation_logo
    }

    async getYearSelected(){
       var year_selected = await this.orm.call(
            "vacation.balance.report", "getYearSelected",
            [[]],
            {'user_id': this.model.user.userId, 'year_selected': this.model.date.year}
        );

        this.vacationState.year_selected = year_selected
        return this.vacationState.year_selected
    }

}

L10nAOTimeOffCalendarController.components = {
...L10nAOTimeOffCalendarController.components,
FilterPanel: L10nTimeOffCalendarFilterPanel,
}