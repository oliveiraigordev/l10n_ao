# -*- coding: utf-8 -*-
{
    'name': "Account Budget - Angola",

    'description': """
        Account Budget - Angola
    """,
    'author': "Tistech Angola",
    'contributors': [
        "Johnatan Souza <johnatan.souza.ext@tis.ao>",
        "António Daniel <antonio.daniel@tistech.co.ao>",
    ],
    'website': "https://www.tistech.co.ao",

    'category': 'Accounting/Accounting',
    'version': '0.1',

    'depends': [
        'l10n_ao_report',
        # 'base_automation'
    ],

    'data': [
        # 'data/base_automation_data.xml',

        'security/ir.model.access.csv',

        'views/account_budget_views.xml',
        'views/account_budget_group_views.xml',

        'views/account_budget_line_views.xml',
        'views/account_budget_economic_views.xml',
        'views/account_budget_financial_views.xml',
        'views/account_payment_views.xml',
        'wizard/view_account_payment_report_line_register_form.xml',

        'views/cash_flow_statement_views.xml',
        'views/account_budget_menus.xml',

    ],
    'assets': {
        'web.assets_backend': [
            'l10n_ao_account_budget/static/src/views/list/**/*',
        ],
    }

}
