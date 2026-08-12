# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    gs1_company_prefix = fields.Char(
        related='company_id.gs1_company_prefix', readonly=False,
    )
    sscc_extension_digit = fields.Char(
        related='company_id.sscc_extension_digit', readonly=False,
    )
