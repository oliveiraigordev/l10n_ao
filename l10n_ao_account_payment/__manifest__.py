{
    'name': 'l10n AO Account',
    'version': '16.0',
    'description': 'Contabilidade Localização Angola',
    'summary': 'Extensão à Localização Angola',
    'author': 'TIS',
    'website': 'https://tis.ao',
    'license': 'LGPL-3',
    'category': 'account',
    "data": [
        "views/account_journal_views.xml",
        "views/account_move_views.xml",
        "views/account_account_views.xml",
        "views/account_payment_views.xml"
    ],
    'depends': [
        'base', 'account',
    ],
    'auto_install': False,
    'application': False,
}