# -*- coding: utf-8 -*-
{
    'name': "l10n_ao_debit_note",
    'version': "1.0.0.1",
    'summary': "Cria Nota de Débito semelhante à Nota de Crédito (ND/…)",
    'category': "Accounting",
    'author': "@tis",
    'license': "LGPL-3",
    'website': "https://www.tis.cao",
    'depends': [
        'account','account_debit_note'
    ],
    'data': [
        # 1) Criação da sequência "ND/…"
        'data/debit_note_sequence.xml',
        # 2) Views (form, tree, action, menus)
        'views/account_move_debit_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
