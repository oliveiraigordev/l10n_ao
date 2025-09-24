# -*- coding: utf-8 -*-
{
    "name": "l10n ao edit posted invoice line Tis",
    "summary": """
        This addon allows account manager users to edit accounts and taxes
        on invoice lines of already posted invoices without changing the document status.
    """,
    "author": "Tis Tech Angola",
    "website": "https://www.tistech.co.ao",
    "contributors": [
        "Johnatan Souza <johnatan.souza.ext@tis.ao>,",
    ],
    "category": "Account",
    "version": "16.0.0.1",
    "license": "OPL-1",
    "depends": ["account"],
    "data": [
        
        # Security
        "security/ir.model.access.csv",

        # Views
        "views/account_move_view.xml",
        
        # Wizard
        "wizard/account_move_edit_wizard.xml",

    ],
    "installable": True,
    "application": False,
}
