# -*- coding: utf-8 -*-
{
    "name": "HR Holidays Extension",
    "summary": """
        Custom HR  Holidays module for using in l10n_ao_hr
    """,
    "author": "Tis Tech Angola",
    "website": "https://www.tistech.co.ao",
    "contributors": [
        "Salvador Bila <salvador.bila@tistech.co.ao>",
        "Felipe Paloschi <felipe.paloschi.ext@tis.ao>"
    ],
    "category": "Human Resource",
    "version": "16.0.1.3",
    "license": "OPL-1",
    "depends": ["l10n_ao_hr", "hr_holidays", "hr_payroll_attendance"],
    "data": [
        "security/ir.model.access.csv",
        "data/hr_leave_type_data.xml",
        "data/ir_crons.xml",
        'email_template/templates_data.xml',
        "views/vacation_balance_report.xml",
        "views/hr_leave.xml",
        "views/hr_leave_type.xml",
        "views/hr_employee.xml",
        'views/hr_resource_calendar_leaves.xml',
        "views/res_config_settings.xml",
        'views/hr_calendar_view.xml',
        "views/hr_holiday_menu.xml",
        'wizard/holiday_map.xml',
        'wizard/vacation_balance_report_wizard.xml',
    ],
    'assets': {
        'web.assets_qweb': [
            'l10n_ao_hr_holidays/static/src/views/calendar/**/*.xml',
        ],
        'web.assets_backend': [
            'l10n_ao_hr_holidays/static/src/views/calendar/**/*',
        ],

    }
}
