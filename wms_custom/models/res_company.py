# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    gs1_company_prefix = fields.Char(
        string="Préfixe entreprise GS1",
        help="Préfixe attribué par GS1 à votre entreprise (6 à 10 chiffres).\n"
             "Il constitue le cœur du SSCC des palettes. Sans lui, aucun SSCC ne peut être "
             "généré : le SSCC ne serait pas unique au niveau mondial.",
    )
    sscc_extension_digit = fields.Char(
        string="Chiffre d'extension SSCC",
        size=1,
        default='0',
        help="Premier chiffre du SSCC. Librement choisi par l'entreprise (0 à 9), il sert "
             "à augmenter la capacité de numérotation. Laisser 0 si vous n'avez pas de "
             "besoin particulier.",
    )
