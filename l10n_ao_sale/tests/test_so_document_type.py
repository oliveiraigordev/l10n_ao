from odoo.tests.common import TransactionCase
from odoo.addons.l10n_ao_sale.models.ir_sequence import DEFAULT_SEQUENCE


class TestDocumentTypeSequence(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.doc_type = cls.env["sale.order.document.type"]
        
    def test_check_default_sequence_with_county_ao_code(self):
        companies = self.env["res.company"].search([("country_code", "=", "AO")])
        sequence = self.env["ir.sequence"]
        if companies:
            for company in companies:
                domain = [("company_id", "=", company.id), ("code", "in", ["PP", "OU", "OR"])]
                record = sequence.search(domain)
                if record:
                    self.assertEqual(len(record), 3)
                else:
                    sequence.create_sequence_when_ao()
                    record = sequence.search(domain)
                    self.assertEqual(len(record), 0)

