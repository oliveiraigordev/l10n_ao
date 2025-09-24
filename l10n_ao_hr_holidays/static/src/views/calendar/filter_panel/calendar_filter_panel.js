/** @odoo-module */

import { TimeOffCalendarFilterPanel } from "@hr_holidays/views/calendar/filter_panel/calendar_filter_panel";

import { useState, onWillStart, onMounted } from "@odoo/owl";

import { qweb } from "web.core";

export class L10nTimeOffCalendarFilterPanel extends TimeOffCalendarFilterPanel {

    setup() {
        super.setup();
    }
}

L10nTimeOffCalendarFilterPanel.template = 'hr_holidays.CalendarFilterPanel';
