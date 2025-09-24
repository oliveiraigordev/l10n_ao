from odoo import fields, models, api


class HrPayment(models.Model):
    _name = 'hr.payment'
    _description = 'Employee Payment'

    name = fields.Char(string="Ref")

    date = fields.Date(string="Date", default=fields.Date.today)
    company_id = fields.Many2one(comodel_name="res.company", string="Company", related='payslip_run_id.company_id')
    journal_id = fields.Many2one(comodel_name="account.journal", string="Journal")
    payslip_run_id = fields.Many2one(comodel_name="hr.payslip.run", string="PaySlip Batch")
    lines = fields.One2many('hr.payment.line', 'hr_payment', 'Payment Line')
    state = fields.Selection([
        ('treasury', 'In Treasury'), ('paid', 'Paid'),
    ], string="State", default="treasury")
    payslip_id = fields.Many2one('hr.payslip', string='Payslip')
    amount_paid = fields.Float(string="Total Bruto", compute='_compute_amounts', store=True)
    total_deductions = fields.Float(string="Total Descontos", compute='_compute_amounts', store=True)

    @api.depends('payslip_id.total_remunerations',
                 'payslip_id.total_deductions',
                 'lines.amount',
                 'lines.irt_amount',
                 'lines.ss_amount')
    def _compute_amounts(self):
        for rec in self:
            if rec.payslip_id:
                # individual:
                rec.amount_paid = rec.payslip_id.total_remunerations
                rec.total_deductions = rec.payslip_id.total_deductions
            elif rec.payslip_run_id:
                # batch:
                rec.amount_paid = sum(l.amount for l in rec.lines)
                rec.total_deductions = sum(l.irt_amount + l.ss_amount for l in rec.lines)
            else:
                rec.amount_paid = rec.total_deductions = 0.0

    def unlink(self):
        run_ids = self.mapped('payslip_run_id')
        result = super().unlink()
        for run in run_ids:
            other_payments = self.search_count([('payslip_run_id', '=', run.id)])
            if other_payments == 0:
                run.payment_state = 'not_paid'
        return result






class HrPaymentLine(models.Model):
    _name = 'hr.payment.line'
    _description = 'Employee Payment Line'

    hr_payment = fields.Many2one(comodel_name="hr.payment")
    employee_id = fields.Many2one(comodel_name="hr.employee", string="Employee")
    irt_amount = fields.Float(string="IRT Amount")
    ss_amount = fields.Float(string="SS Amount")
    ss8_amount = fields.Float(string="INSS 8% (Patronal)")
    amount = fields.Float(string="Processed Amount")
    amount_paid = fields.Float(string="Amount Paid")
    amount_debt = fields.Float(string="Amount Debt")
    payslip_id = fields.Many2one('hr.payslip', string='Payslip')
    other_earnings = fields.Float(string="Outros Ganhos")
    other_deductions = fields.Float(string="Outros Descontos")
    total_gross = fields.Float(string="Total Bruto")
    ali = fields.Float(string="Subsídio Alimentação (ALI)")
    trans = fields.Float(string="Subsídio Transporte (TRANS)")
    fami = fields.Float(string="Subsídio Familiar (FAMI)")
    renc = fields.Float(string="RENÇ")
    eat = fields.Float(string="EAT")
    comu = fields.Float(string="COMU")
    falha = fields.Float(string="FALHA")
    bon = fields.Float(string="BON")
    r92 = fields.Float(string="R92")
    atra = fields.Float(string="ATRA")
    famexc = fields.Float(string="FAMEXC")
    comission = fields.Float(string="COMISSION")
    chef = fields.Float(string="CHEF")
    cfng = fields.Float(string="CFNG")
    thirteen = fields.Float(string="13º")
    fjr = fields.Float(string="FJR")
    fi = fields.Float(string="FI")
    r75 = fields.Float(string="R75")
    gozo_ferias = fields.Float(string="Gozo Férias")
    ata = fields.Float(string="ATA")
    adi = fields.Float(string="ADI")
    hextra_50 = fields.Float(string="H.Extra 50%")
    hextra_75 = fields.Float(string="H.Extra 75%")
    adi_alimentacao = fields.Float(string="Adi Alimentação")
    isen_hora = fields.Float(string="Insenção de Horário")




