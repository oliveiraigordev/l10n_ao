{
    'name': 'Salary Payment Angola',
    'version': '16.0',
    'summary': 'Gestão de pagamentos salariais com IRT e INSS para Angola',
    'description': 'Permite gerir o pagamento de salários com integração contábil e cálculo fiscal para o contexto angolano.',
    'category': 'Accounting',
    'author': '@tis-Angola',
    'website': 'www.tis.ao',
    'depends': ['account', 'account_accountant', 'hr_payroll', 'hr','hr_payroll_account'],
    'data': [
        'security/ir.model.access.csv',
        'security/group.xml',

        #'data/email_template_salary_done.xml',
        #'data/automation_payslip_batch.xml',

        'views/hr_payment_view.xml',
        'views/account_payment_expat.xml',
        'views/payslip_view.xml',
        'views/payslip_employee_view.xml',
        'views/account_payment.xml',
        'views/bank_rec_views.xml',

        #'reports/cash_flow_report.xml',
        'wizard/wizard_partial_salary_payment_view.xml',
        'wizard/wizard_penalty_view.xml',
        'wizard/wizard_penalty_tax_views.xml',

    ],
    'installable': True,
    'auto_install': False,
    'price':0,
    'currency': 'AOA',
    'license': 'OPL-1',
}
