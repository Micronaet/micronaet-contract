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

import os
import sys
import logging
import netsvc
import csv
import decimal_precision as dp
from os import listdir
from osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from tools.translate import _
from os.path import isfile, join
from tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    )

_logger = logging.getLogger(__name__)

class account_analytic_expense_deprecation(osv.osv):
    ''' Add schedule method and override split method
    '''
    _name = 'account.analytic.expense.deprecation'
    _description = 'Deprecation data'
    
    # -------------------------------------------------------------------------
    #                          Utility function
    # -------------------------------------------------------------------------
    def create_analytic_line_deprecation(self, cr, uid, department_id, 
            total, general_account_id, period, error=None, 
            year_period_id, context=None):
        ''' Procedure for split cost passed
        '''
        # Init setup:
        error = error or []
        
        # Pool used:
        journal_pool = self.pool.get('account.analytic.journal')
        line_pool = self.pool.get('account.analytic.line')
        contract_pool = self.pool.get('account.analytic.account')
        account_pool = self.pool.get('account.account')

        # Purchase journal:
        journal_id = journal_pool.get_journal_purchase(
            cr, uid, context=context)
        # TODO 

        # Search contract
        contract_ids = contract_pool.search(cr, uid, [
            ('department_id', '=', department_id), # department filter
            ('state', 'in', ('cancel')), # status test
            # period from and to! 
            ], context=context)

        if len(contract_ids) > 1:
            error.append(_('No contract found for split data!'))
            _logger.error(error[-1])
            return
        
        total_contract = sum([
            contract.total for contract in contract_pool.browse(
                cr, uid, contract_ids, context=context)])
            
        if not total_contract:
            error.append(_('No total for contract so no split!'))
            _logger.error(error[-1])
            return
           
        rate = total / total_contract        
        for contract in contract_pool.browse(
                cr, uid, contract_ids, context=context):        
            line_pool.create(cr, uid, {
                'amount': -amount,
                'user_id': uid,
                'name': _('Deprecation period: %s') % period,
                'unit_amount': 1.0,
                'account_id': contract_ids[0],
                'general_account_id': general_account_id,
                'journal_id': journal_id, 
                'date': period_date,

                # Link to import record:
                'year_period_id': year_period_id,
                'csv_filename': filename, # key for deletion

                # Not used:
                #'company_id', 'code', 'currency_id', 'move_id',
                #'product_id', 'product_uom_id', 'amount_currency',
                #'ref', 'to_invoice', 'invoice_id', 
                # 'extra_analytic_line_timesheet_id', 'import_type',
                ##'activity_id', 'mail_raccomanded', 'location',
                }, context=context)
               
        return True

    # -------------------------------------------------------------------------
    #                          Schedule function
    # -------------------------------------------------------------------------
    def schedule_csv_accounting_deprecation_movement_import(
            self, cr, uid, general_code='410100', force=False, context=None):
        ''' Import function that read in:
            force: delete previous elements
            context: context for this function            
            Note: file period are coded in filename
        '''
        # TODO manage force!!
        # ---------------------------------------------------------------------
        # Read parameters for write analytic entry:
        # ---------------------------------------------------------------------
        # Code for entry (ledger) operation:
        general_id = account_pool.get_account_id(
            cr, uid, general_code, context=context)
        if not general_id:
            _logger.error(_('Cannot create analytic line, no ledge!'))
            return False

        # Check period to load:
        _logger.info('Load previous imported periods')
        period_mask = '%s-%02d'
        periods_all = []
        period_to_update = {}
        error = [] # from here log error
        
        year_ids = self.search(cr, uid, [], context=context)

        current_period = period_mask % (
            datetime.now().year, 
            datetime.now().month,
            )
            
        for year in self.browse(
                cr, uid, year_ids, context=context):
            # -----------------------------------------------------------------
            # Read total cost to split:
            # -----------------------------------------------------------------
            to_split = {} # list of period to split

            # Cost to split in period
            for cost in year.cost_ids:
                to_split[cost.department_id.id] = cost.total / 12.0 #month rate

            if not to_split:
                error.append('Create department cost to split!')
                _logger.error(error[-1])
                return True

            # Create database for period of the year
            for month in range(1, 13): # all previous month
                key = period_mask % (year.name, month)
                if key >= current_period:
                    continue # jump > current month
                periods_all.append(key)

            # Create period not present:
            for period in year.period_ids:
                key = '%s-%s' % (period.year_id.name, period.name)
                if key in periods_all: # create month if not present
                    continue # yet present
                
                # Create analytic line for department:
                for department_id in to_split:
                    # TODO create split function:
                    self.create_analytic_line_deprecation(
                        cr, uid, 
                        department_id, # department for contract selection
                        to_split[department_id], # total mont to split
                        general_id,
                        key, # for period
                        error,
                        period.id, # for link
                        context=context,
                        )
                department_id = period.department_id.id
                total = period.total
            
                code = csv_pool.decode_string(line[0]) # department:
                amount = csv_pool.decode_float(line[1])

                if not code:
                    error.append(_('%s. Contract code empty') % i)
                    _logger.error(error[-1])
                    continue
                    
                # TODO write error in file
                if error:
                    self.write(cr, uid, period.id, {
                        'error': '\n'.join(error)}, context=context)

        _logger.info('End auto import of file transport')
        return True

    _columns = {
        'name': fields.char('Year', size=4, required=True),        
        'force': fields.boolean('Force reload'),
        'error': fields.text('Error'), # TODO keep?
        'note': fields.text('Note'),
        }
account_analytic_expense_deprecation()


class account_analytic_expense_deprecation_cost(osv.osv):
    ''' Add schedule method and override split method
    '''
    _name = 'account.analytic.expense.deprecation.cost'
    _description = 'Year deprecation cost'
    _rec_name = 'department_id'
    _order = 'department_id'

    _columns = {
        'year_id': fields.many2one(
            'account.analytic.expense.deprecation', 'Year'),        
        'department_id': fields.many2one(
            'hr.department', 'Department', required=True), 
        'total': fields.float('Total for year', digits=(16, 2), required=True), 
        }
account_analytic_expense_deprecation_cost()

class account_analytic_expense_deprecation_period(osv.osv):
    ''' Add schedule method and override split method
    '''
    _name = 'account.analytic.expense.deprecation.period'
    _description = 'Monthly deprecation split'

    _columns = {
        'name': fields.char('MM', size=2, required=True), 
        'datetime': fields.datetime('Import date'),
        'year_id': fields.many2one(
            'account.analytic.expense.deprecation', 'Year'), 
        'error': fields.text('Error'),
        }
            
    _defaults = {
        'datetime': lambda *x: datetime.now().strftime(
            DEFAULT_SERVER_DATETIME_FORMAT),
        }        
account_analytic_expense_deprecation_period()

class account_analytic_line(osv.osv):
    ''' Extra fields for analytic line
    '''
    _inherit = 'account.analytic.line'
    
    _columns = {
        'year_period_id': fields.many2one(
            'account.analytic.expense.deprecation.period', 
            'Link for split period', ondelete='cascade'),
        }
account_analytic_line()

class account_analytic_expense_deprecation_period(osv.osv):
    ''' Add schedule method and override split method
    '''
    _inherit = 'account.analytic.expense.deprecation.period'

    _columns = {
        'line_ids': fields.one2many(
            'account.analytic.line', 'deprecation_import_id', 'Analytic line'),
        }
account_analytic_expense_deprecation_period()

class account_analytic_expense_deprecation(osv.osv):
    ''' Add schedule method and override split method
    '''
    _inherit = 'account.analytic.expense.deprecation'

    _columns = {
        'period_ids': fields.one2many(
            'account.analytic.expense.deprecation.period', 
            'year_id', 'Period'),
        'cost_ids': fields.one2many(
            'account.analytic.expense.deprecation.cost', 
            'year_id', 'Period'),
        }
account_analytic_expense_deprecation()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: