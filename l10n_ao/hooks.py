# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID

JOURNALS_SPEC = [
    # (code, name, type)
    ("VFA",  "V/Factura a prazo",                "sale"),
    ("VFR",  "V/Factura Recibo",                 "sale"),
    ("VVD",  "V/Venda-a-Dinheiro",               "sale"),
    ("VFG",  "V/Factura Global",                 "sale"),
    ("VGF",  "V/Factura Genérica",               "sale"),

    ("PFR",  "V/Factura Recibo (Compras)",       "purchase"),
    ("VND",  "V/Nota de Débito (Compras)",       "purchase"),
    ("VFM",  "V/Factura de Imobilizado (Compras)","purchase"),
    ("VFGP", "V/Factura Global (Compras)",       "purchase"),
    ("VFAP", "V/Factura (Compras)",              "purchase"),
    ("VVDP", "V/Venda-a-Dinheiro (Compras)",     "purchase"),
]

INTERNAL_TRANSFER_CODE = "TRFIN"   # escolha um code <= 5
INTERNAL_TRANSFER_NAME = "Transferência Interna"

def _ensure_journal(env, company, code, name, jtype, extra_vals=None):
    Journal = env["account.journal"].with_context(active_test=False).sudo()
    journal = Journal.search([("code", "=", code), ("company_id", "=", company.id)], limit=1)
    if journal:
        return journal
    vals = {
        "name": name,
        "code": code[:5],  # garante no máximo 5 chars
        "type": jtype,
        "company_id": company.id,
    }
    if extra_vals:
        vals.update(extra_vals)
    return Journal.create(vals)

def _ensure_all(env):
    Company = env["res.company"].sudo()
    companies = Company.search([])
    for company in companies:
        # 1) diário de transferência interna
        _ensure_journal(
            env,
            company,
            INTERNAL_TRANSFER_CODE,
            INTERNAL_TRANSFER_NAME,
            "general",
            # se precisar preencher campos extras aqui:
            # {"journal_ao_id": env.ref("l10n_ao.journal_ao_result_divs").id}  # só se existir SEMPRE
        )

        # 2) demais diários
        for code, name, jtype in JOURNALS_SPEC:
            _ensure_journal(env, company, code, name, jtype)

def pre_init_hook(cr):
    # Opcional: se você ainda mantém XML, garanta antes de ele rodar
    env = api.Environment(cr, SUPERUSER_ID, {})
    _ensure_all(env)

def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _ensure_all(env)
