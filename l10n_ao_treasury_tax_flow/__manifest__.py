# -*- coding: utf-8 -*-
{
    'name': "treasury_cash_flow_ao",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Accounting Payment',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['account_accountant'],

    # always loaded
    'data': [
        'data/tax_payment_sequence_data.xml',

        # 'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'views/account_payment.xml',
        'views/account_tax_view.xml',
        'views/menu_itens.xml',
    ],
}
