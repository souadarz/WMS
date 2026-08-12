# -*- coding: utf-8 -*-
from odoo import models


class StockPicking(models.Model):
    """Placeholder : `models/__init__.py` importait déjà ce fichier alors qu'il n'existait
    pas, ce qui empêchait le module de se charger (ImportError au démarrage).

    Le fichier est créé vide de toute logique pour rétablir le chargement. Les
    personnalisations de transfert viendront ici.
    """
    _inherit = 'stock.picking'
