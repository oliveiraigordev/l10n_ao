# -*- coding: utf-8 -*-
from odoo import models, api, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    #This sequence is created to allow the pos to have their own sequence number for the certification.
    l10n_ao_pos_sequence_id = fields.Many2one('ir.sequence')
    l10n_ao_pos_refund_sequence_id = fields.Many2one('ir.sequence')

    @api.model
    def post_install_create_sequence(self):
        for company in self.env['res.company'].search([]):
            if company.chart_template_id == self.env.ref('l10n_ao.ao_chart_template'):
                sequence_fields = ['l10n_ao_pos_sequence_id','l10n_ao_pos_refund_sequence_id']
                company._create_secure_sequence_pos(sequence_fields)


    @api.model
    def create(self, vals):
        company = super(ResCompany, self).create(vals)
        #when creating a new french company, create the securisation sequence as well
        if company.chart_template_id == self.env.ref('l10n_ao.ao_chart_template'):
            sequence_fields = ['l10n_ao_pos_sequence_id', 'l10n_ao_pos_refund_sequence_id']
            company._create_secure_sequence_pos(sequence_fields)
        return company


    def write(self, vals):
        res = super(ResCompany, self).write(vals)
        #if country changed to fr, create the securisation sequence
        for company in self:
            if not company.l10n_ao_pos_sequence_id and company.chart_template_id == self.env.ref('l10n_ao.ao_chart_template'):
                sequence_fields = ['l10n_ao_pos_sequence_id']
                company._create_secure_sequence_pos(sequence_fields)
            elif not company.l10n_ao_pos_refund_sequence_id and company.chart_template_id == self.env.ref('l10n_ao.ao_chart_template'):
                sequence_fields = ['l10n_ao_pos_refund_sequence_id']
                company._create_secure_sequence_pos(sequence_fields)

        return res

    def _create_secure_sequence_pos(self, sequence_fields):
        """This function creates a no_gap sequence on each companies in self that will ensure
        a unique number is given to all posted account.move in such a way that we can always
        find the previous move of a journal entry.
        """
        for company in self:
            vals_write = {}
            for seq_field in sequence_fields:
                if seq_field == "l10n_ao_pos_sequence_id":
                    if not company[seq_field] and company.chart_template_id == self.env.ref(
                            'l10n_ao.ao_chart_template'):
                        vals = {
                            'name': 'Angola POS Sequence - ' + company.name,
                            'code': 'l10n_ao_pos',
                            'implementation': 'no_gap',
                            'prefix': 'FR %(range_year)s/',
                            'suffix': '',
                            'padding': 0,
                            'use_date_range': True,
                            'company_id': company.id}
                        seq = self.env['ir.sequence'].create(vals)
                        vals_write[seq_field] = seq.id
                elif seq_field == "l10n_ao_pos_refund_sequence_id":
                    if not company[seq_field] and company.chart_template_id == self.env.ref(
                            'l10n_ao.ao_chart_template'):
                        vals = {
                            'name': 'Angola POS Sequence Refund- ' + company.name,
                            'code': 'l10n_ao_pos_refund',
                            'implementation': 'no_gap',
                            'prefix': 'NC POS%(range_year)s/',
                            'suffix': '',
                            'padding': 0,
                            'use_date_range': True,
                            'company_id': company.id}
                        seq = self.env['ir.sequence'].create(vals)
                        vals_write[seq_field] = seq.id

            if vals_write:
                company.write(vals_write)