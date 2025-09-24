from odoo import models, _, fields


class AccountStatementReportHandler(models.AbstractModel):
    _name = "account.statement.report.handler"
    _inherit = 'account.general.ledger.report.handler'

    def _get_query_amls(self, report, options, expanded_account_ids, offset=0, limit=None):
        full_query, all_params = super(AccountStatementReportHandler, self)._get_query_amls(report, options, expanded_account_ids, offset=offset, limit=limit)
        index = full_query.find('WHERE') - 1
        query = full_query[:index] + """ LEFT JOIN account_journal_ao journal_ao         ON journal_ao.id = account_move_line.journal_ao_id""" + full_query[index:]
        full_query = query.replace("(SELECT\n", """(SELECT
        account_move_line.sequence,
        move.sequence_journal_ao,
        move.iva_origin_account,
        move.id,
        journal_ao.name as journal_ao,
        """)

        return full_query, all_params
