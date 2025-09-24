# -*- coding: utf-8 -*-
{
    'name': "Sales - Angola Localization",

    'summary': """Documents of sales with Angola localization""",

    'author': "Tis Tech Angola",
    'website': "https://www.tistech.co.ao",
    'category': 'Sales',
    'version': '1.0',
    'license': 'LGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['base', 'sale','sale_management','l10n_ao'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',

        'data/document_type.xml',
        'reports/sale_order_report.xml',
        'reports/report_definition.xml',
        #'data/document_type_sequence.xml',

        'views/sales_res_config_settings.xml',
        #'views/sale_order_line.xml',
        'views/sales_order.xml',
        'views/sales_order_menu.xml',

    ],
    # only loaded in demonstration mode
    'demo': [],
    'application': True,
    'installable': True,
    'auto_install': False,
}
