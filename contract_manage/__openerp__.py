# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. 
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

{
    'name': 'Contract Manage',
    'version': '0.0.1',
    'category': 'Generic Modules/Customization',
    'description': """
        Manage contract using analitic account withour parent_id
        Use TS to create values in analitic line with extra 
        analytic lines added inserting hours
        """,
    'author': 'Micronaet s.r.l.',
    'website': 'http://www.micronaet.it',
    'depends': [
        'base',
        'hr',
        'analytic',
        'hr_timesheet',
        'hr_timesheet_invoice',                 
        'account',
        'account_analytic_analysis',
        'product',
        'knowledge',
        'l10n_it_base',
        'report_aeroo',
        'report_aeroo_ooo',
        'csv_base',
        'contract_load_distance',
        ],
    'init_xml': [], 
    'update_xml': [
        'security/contract_group.xml',
        'security/ir.model.access.csv',
        'contract_views.xml',
        'scheduler.xml',
        'wizard/intervent_views.xml',
        'wizard/group_superintervent_view.xml',
        'contract_dashboard.xml',
        'report/report_employee.xml',
        ],
    'demo_xml': [],
    'active': False, 
    'installable': True, 
    }
