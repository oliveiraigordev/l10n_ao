# -*- coding: utf-8 -*-
{
    'name': "l10nao_stock",
    'odoo_version': '16.1',
    'version': '1.2.1',
    'depends': ["product",
                "stock",
                "account",
                "stock_account",
                "purchase",
                "purchase_stock", ],

    'author': "Tistech",
    'category': 'l10nao_stock',
    'license': 'LGPL-3',
    'sequence': 2,
    'summary': """
    l10nao_stock for Odoo 
        """,
    'description': """   
     Angola Stock Account 
        """,
    'data': [
        'security/ir.model.access.csv',

        'data/sequence_data.xml',

        "wizards/stock_move_extract_wizard_view.xml",
        'views/stock_move_views.xml',
        'views/stock_picking_views.xml',
        'views/product_template_stock_account_views.xml',
        "reports/report_stockpicking_operations.xml",
        "reports/delivery_ship_agt.xml",
        "reports/report_stock_definition.xml",

    ],
    'demo': [
        #   'data/journal_saft_data.xml'

    ],
    'application': False,
    'installable': True,

}
