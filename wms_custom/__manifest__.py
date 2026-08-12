# -*- coding: utf-8 -*-
{
    'name': 'WMS Custom',
    'version': '18.0.1.1.0',
    'summary': 'Personnalisations WMS pour notre entrepôt',
    'description': """
Module custom qui étend le module stock natif d'Odoo pour ajouter des besoins spécifiques
à notre WMS.

Étiquette palette SSCC
======================

Chaque charge palettisée reçoit un SSCC (GS1, 18 chiffres), unique et jamais réutilisé.
L'étiquette imprimée porte un DataMatrix GS1, un Code128 et un QR code.

Ce qui est imprimé — et seulement cela — ce sont les faits **immuables** : SSCC, GTIN,
lot, DLC, quantité à l'emballage.

Ce qui n'est **pas** imprimé : la quantité courante et l'historique des mouvements. Ils
changent à chaque prélèvement de commande ; une étiquette papier ne peut pas les suivre.
Ils sont lus en base au moment du scan, le SSCC servant de clé.

Deux façons de consulter :

* **Douchette** — le Code128 du SSCC ouvre la fiche dans Odoo.
* **Téléphone** — le QR ouvre une page web mobile, sans installer d'application.

Les deux passent par la même méthode Python, donc affichent toujours la même chose.
    """,
    'category': 'Inventory/Inventory',
    'author': 'Souadarz',
    'license': 'LGPL-3',

    'depends': [
        'stock',
        # Fournit la nomenclature GS1 et les règles d'identifiants (00, 01, 02, 10, 17…)
        # sur lesquelles s'appuient la génération du DataMatrix et la lecture des scans.
        'barcodes_gs1_nomenclature',
    ],

    # L'ordre compte : les vues référencent l'action de rapport, qui doit donc être
    # chargée avant elles.
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'report/pallet_label_templates.xml',
        'report/pallet_label_report.xml',
        'views/res_config_settings_views.xml',
        'views/stock_quant_package_views.xml',
        'views/wms_pallet_portal_templates.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}
