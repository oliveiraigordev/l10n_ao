/** @odoo-module */

import { calendarView } from '@web/views/calendar/calendar_view';

import { L10nAOTimeOffCalendarController } from './holidays_calendar_controller';

import { registry } from '@web/core/registry';

const L10nAOTimeOffCalendarView = {
    ...calendarView,

    Controller: L10nAOTimeOffCalendarController,
    buttonTemplate: "hr_holidays.CalendarController.controlButtons",
}

registry.category('views').add('l10n_ao_time_off_calendar_dashboard', L10nAOTimeOffCalendarView);