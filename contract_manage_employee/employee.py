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
from tools.translate import _
from osv import fields, osv, expression
from datetime import datetime, timedelta
from os.path import isfile, join
from os import listdir

_logger = logging.getLogger(__name__)

# python represent weekday starting from 0 = Monday
week_days = [
    ('mo', 'Monday'),  
    ('tu', 'Tuesday'),     
    ('we', 'Wednesday'),     
    ('th', 'Thursday'),     
    ('fr', 'Friday'),     
    ('sa', 'Saturday'),     
    ('su', 'Sunday'),
    ]

class account_analytic_journal(osv.osv):
    ''' Add extra function for refound journal
    '''
    _inherit = 'account.analytic.journal'
    
    # --------
    # Utility:
    # --------
    def get_refound_journal(self, cr, uid, context=None):
        ''' Get (and create the first time) refound journal
        '''
        refound_journal_ids = self.search(cr, uid, [
            ('code', '=', 'REF')], context=context)
            
        if refound_journal_ids:
            return refound_journal_ids[0]
            
        _logger.warning('Intervent refound (REF) journal not found created!')
        return self.create(cr, uid, {
            'name': _('Intervent refound'),
            'code': 'REF',
            'type': 'general',
            }, context=context)
account_analytic_journal()

class hr_analytic_timesheet(osv.osv):
    ''' Extra function for scheduled procedure (ex wizard)
    '''
    _inherit = 'hr.analytic.timesheet'
    
    # -------------------------------------------------------------------------
    #                                Utility:
    # -------------------------------------------------------------------------
    def load_one_cost(self, cr, uid, path, filename, separator,
            error=None, context=None):
        ''' Import one file 
        '''
        # Utility: function for procedure:
        def format_string(value, default=''):
            try:
                return value.strip() or default
            except:
                return default

        def format_date(value):
            return value

        def format_float(value):        
            # TODO manage . for thousand separator
            try:
                value = value.replace(',', '.')
                return float(value)
            except:
                return 0.0

        # Pool used:
        employee_pool = self.pool.get('hr.employee')            
        hc_pool = self.pool.get('hr.employee.hour.cost')

        tot_col = 3 # TODO change if file will be extended
        if error is None:
            error = []

        fullname = os.path.join(os.path.expanduser(path), filename)
        domain = []
        force_cost = {}
       
        # Load from file employee:
        item_ids = [] # employee list
        
        # Check file present (for wizard but used alse for sched.)?
        try: 
            f = open(os.path.expanduser(fullname), 'rb')
        except:
            error.append(_('No file found for import: %s') % fullname)
            _logger.error(error[-1])

        i = 0
        for line in f:
            try:
                i += 1                
                line = line.strip()
                if not line:
                    error.append(_('%s. Empty line (jumped)') % i)
                    _logger.warning(error[-1])
                    continue
                record = line.split(separator)
                col_len = len(record)
                if col_len < tot_col:
                    error.append(_(
                        '%s. Record different format: %s (col.: %s)') % (
                            i, tot_col, len(record)))
                    _logger.error(error[-1])
                    continue
               
                code = format_string(record[0], False)
                if col_len == 3:
                    name = format_string(record[1]).title()
                    # Calculated fields:
                    names = name.split(' ') # TODO not so awsome...
                    name = names[-1].title()
                    surname = names[0].title()
                    cost = format_float(record[2])
                    total = 0.0 # no total
                else: # 5 cols format:    
                    name = format_string(record[1]).title()
                    surname = format_string(record[2]).title()
                    cost = format_float(record[3])
                    total = format_float(record[4])

                if not cost:
                    error.append(_('%s. Error no hour cost: %s %s [%s]') % (
                        i, name, surname, code))
                    _logger.error(error[-1])
                    continue
                    
                # Search first for code
                # TODO search also in deactivated users?
                employee_ids = [] # TODO not necessary
                update_code = False
                if code:
                    employee_ids = employee_pool.search(cr, uid, [
                        ('identification_id', '=', code),
                        ], context=context)
                        
                if not employee_ids:
                    update_code = True
                    employee_ids = employee_pool.search(cr, uid, [
                        '|',
                        ('name', '=', "%s %s" % (name, surname)),
                        ('name', '=', "%s %s" % (surname, name)),
                        ], context=context)

                if len(employee_ids) == 1:
                    if update_code: # Save code for next use
                        employee_pool.write(cr, uid, employee_ids, {
                            'identification_id': code,
                            }, context=context)
                    employee_id = employee_ids[0]
                    if employee_id in item_ids:
                        error.append(
                            _('%s. Double in CSV file: %s %s [%s]') % (
                                i, surname, name, code))
                        _logger.error(error[-1])
                    else:
                        item_ids.append(employee_id)
                        force_cost[employee_id] = cost # save cost
                elif len(employee_ids) > 1:
                    error.append(_('%s. Fount more employee: %s %s [%s]') % (
                        i, surname, name, code))
                    _logger.error(error[-1])                   
                else:
                    error.append(_('%s. Employee not found: %s %s [%s]') % (
                        i, surname, name, code))
                    _logger.error(error[-1])

            except:
                error.append('%s' % (sys.exc_info(), ))
                _logger.error('%s. Generic error line:' % i)
                _logger.error(error[-1])

        f.close() # for rename
        domain.append(('id', 'in', item_ids))
                
        # Load in object for check:
        hc_pool.load_all_employee(
            cr, uid, domain, force_cost, context=context)
            
        return True
    
    def import_one_cost(self, cr, uid, name='', from_date=False, to_date=False,
            error=None, context=None):
        ''' Import previous loaded list of employee costs
            Generate a intervent for unload hour that will be recovered
            
            name: for log description
            from_date: from date update analytic line
            error: list of error that will be write in log record 
            context: parameters passed
        '''
        # Pools used:
        cost_pool = self.pool.get('hr.employee.hour.cost')
        product_pool = self.pool.get('product.product')
        employee_pool = self.pool.get('hr.employee')
        line_pool = self.pool.get('account.analytic.line')
        journal_pool = self.pool.get('account.analytic.journal')
        log_pool = self.pool.get('hr.employee.force.log')
        
        if error is None:
            error = []

        # -----------------------------
        # Journal operation operations:
        # -----------------------------
        # Timesheet (TS)
        timesheet_journal_ids = journal_pool.search(cr, uid, [
            ('code', '=', 'TS')], context=context)
        if not timesheet_journal_ids:
            _logger.error('Timesheet (TS) journal not found!')
            return False # NOTE: No auto creation!
        _logger.info('Get Timesheet (code TS) journal for filter')

        # Refound timesheet elements (REF)
        _logger.info('Get Intervent refound (code REF) journal for filter')
        refound_journal_id =journal_pool.get_refound_journal(
            cr, uid, context=context)

        # Create log (parent) operation (note: Logged before for get ID):
        # Note: Log operation before to get ID
        update_log_id = log_pool.log_operation(
            cr, uid, name, from_date, error, context=context)

        # ----------------------------------------------------
        # Load all elements previous stored in OpenERP object:
        # ----------------------------------------------------
        refound_db = {} # intervent status and reference record
        cost_ids = cost_pool.search(cr, uid, [], context=context)

        # Also the same part of domain (used also after):        
        date_range_domain = [('date', '>=', from_date)]
        if to_date: # for schedule update only
            date_range_domain.append(('date', '<', to_date))
            
        for cost in cost_pool.browse(cr, uid, cost_ids, context=context):
            try:               
                standard_price = cost.hour_cost_new # new standard price
                # ----------------------------------------------
                # Force product to employee (for new creations):
                # ----------------------------------------------
                # TODO optimize for create update only new product
                employee_pool.write(cr, uid, cost.employee_id.id, {
                    'product_id': cost.product_id.id,
                    }, context=context)

                # -----------------------------
                # Force new product hour costs:
                # -----------------------------        
                # test if the update date is greater than:
                current_date = cost.product_id.update_price_date
                if not current_date or from_date > current_date:                
                    product_pool.write(cr, uid, cost.product_id.id, {
                        'standard_price': standard_price,
                        'update_price_date': from_date, 
                        }, context=context)

                # ------------------------------------------------
                # Update analytic lines save log operation parent:
                # ------------------------------------------------
                # every time will be regenered:
                domain = [
                    ('journal_id', '=', timesheet_journal_ids[0]), # only
                    ('user_id', '=', cost.employee_id.user_id.id),
                    ]
                domain.extend(date_range_domain) # date filter added        
                line_ids = line_pool.search(cr, uid, domain, context=context)

                # loop for total calculation:
                for line in line_pool.browse(
                        cr, uid, line_ids, context=context):
                        
                    line_pool.write(cr, uid, line.id, {
                        'amount': -(standard_price * line.unit_amount),
                        'update_log_id': update_log_id,
                        'product_id': cost.product_id.id, 
                        }, context=context)

                    # Save value for refound pool:
                    try:                        
                        # Check if is a leave or vacation account
                        if line.account_id.not_working or line.account_id.is_recover:
                            continue # jump
                        
                        # Populate refound database (for after)
                        user_id = cost.employee_id.user_id.id
                        if user_id not in refound_db:
                            # only the first time
                            # Database = total h / account, browse line, cost
                            refound_db[user_id] = [{}, line, standard_price] 
                            
                        # Save unit amount (amount was the same coeff.)    
                        if line.account_id.id not in refound_db[user_id][0]:
                            refound_db[user_id][0][
                                line.account_id.id] = line.unit_amount
                        else:    
                            refound_db[user_id][0][
                                line.account_id.id] += line.unit_amount
                    except:
                        _logger.error('Generic error in refound DB :%' % (
                            sys.exc_info(),
                            ))
            except: # TODO log error on record?                
                _logger.error('Employee update: %s' % cost.employee_id.name)
                _logger.error(sys.exc_info(), )
                continue
                
        # ---------------------------------------------------------------------
        #                        REFOUND INTERVENT:
        # ---------------------------------------------------------------------
        # Delete user intervent in this period for regenerate:
        user_ids = refound_db.keys() # for readability
        
        domain = [
            ('user_id', 'in', user_ids),
            ('journal_id', '=', refound_journal_id), # only this timesheet
            ]
        domain.extend(date_range_domain)
        line_ids = line_pool.search(cr, uid, domain, context=context)
        if line_ids: 
            line_pool.unlink(cr, uid, line_ids, context=context)

        month = from_date[5:7]
        year = from_date[:4]
        calendar_database = self.get_calendar(cr, uid, {
            # use from date for get month and year (always refer to month)
            'month': month,
            'year': year,
            'user_ids': user_ids,
            }, origin='importation', context=context)

        error_count = 0    
        for key in refound_db: # key = user_id
            reference = refound_db[key][1] # browse of analytic line
            
            if not calendar_database[key][-1][0]: # contract hour:
                error.append('No contract set for hour for check, User: %s' % (                    
                    reference.user_id.name,
                    ))
                _logger.error(error[-1])
                error_count += 1
                continue
                
            # Create coefficient for split refound:                        
            refound_hours = (
                # Worked hour                 - Contract hour
                calendar_database[key][-1][1] - calendar_database[key][-1][0])
            # Not used element (has extra text)    

            if refound_hours <= 0.0: 
                continue # no extra hours so no splitting:
            
            # TODO splitted based on maked hours:
            split_coeff = refound_hours / calendar_database[key][-1][1] 
            
            for account_id in refound_db[key][0]:
                # TODO calculate (attention to new value of cost / hour)
                unit_amount = refound_db[key][0][account_id] * split_coeff
                amount = +(
                    unit_amount * 
                    refound_db[key][2] # hour cost
                    ) 
                
                line_pool.create(cr, uid, {
                    'update_log_id': update_log_id, # parent log
                    'amount': amount,
                    'user_id': reference.user_id.id,
                    'name': _('Period %s/%s refound user %s (H.: %6.2f/%s)') % (
                        month,
                        year,
                        reference.user_id.name, 
                        unit_amount,
                        refound_hours, # to split
                        ),
                    'unit_amount': unit_amount,
                    'date': '%s-01' % reference.date[:7],
                    'company_id': reference.company_id.id,
                    'account_id': account_id,
                    'general_account_id': reference.general_account_id.id,
                    'product_id': reference.product_id.id,
                    'product_uom_id': reference.product_uom_id.id,
                    'journal_id': refound_journal_id,
                    
                    # Unused or empty fields:
                    #'code': False,
                    #'currency_id': reference.company_id.id,,
                    #'ref': False,
                    #'to_invoice': reference.to_invoice,
                    #'move_id': ,
                    #'amount_currency': , ??
                    #'invoice_id': ,
                    #'extra_analytic_line_timesheet_id': ,
                    #'import_type': ,
                    #'activity_id': ,
                    #'mail_raccomanded': ,
                    #'location': ,
                    #'expense_id': ,
                    #'km_import_id': ,
                    }, context=context)

        # Re-write error for cover refound elements:
        if error_count:
            error_text = ''
            for value in error:
                error_text += "%s\n" % value

            # Write      
            log_pool.write(cr, uid, update_log_id, {
                'error': error_text}, context=context)
            
    # -------------------------------------------------------------------------
    #                               Schedule operations:
    # -------------------------------------------------------------------------
    # Master function for scheduled importation:
    def schedule_importation_cost(self, cr, uid, path='~/etl/employee', 
            bof='cost', separator=';', context=None):
        ''' Loop on cost folder searching file that start with bof
        '''
        path = os.path.expanduser(path)
        cost_file = [
            filename for filename in listdir(path) if 
                isfile(join(path, filename)) and filename.startswith(bof) 
                and len(filename) == (len(bof) + 8)] # YYAA.csv = 8 char

        cost_file.sort() # for have last price correct
        _logger.info("Start auto import of file cost")
        for filename in cost_file:        
            try:
                _logger.info("Load and import file %s" % filename)
                error = []                             
                # -------------------------------------------------------------
                #                    Load (old wizard procedure)
                # -------------------------------------------------------------
                self.load_one_cost(cr, uid, path=path, filename=filename, 
                    separator=separator, error=error, context=context)
                    
                # -------------------------------------------------------------
                #                            Import
                # -------------------------------------------------------------
                # Parse date:
                file_date = os.path.splitext(filename)[0][-4:]
                from_year = int(file_date[:2])
                from_month = int(file_date[2:])
                
                # Next value:
                if from_month == 12:
                    next_month = 1
                    next_year = from_year + 1
                else:    
                    next_month = from_month + 1
                    next_year = from_year

                from_date = '20%02d-%02d-01' % (from_year, from_month)
                to_date = '20%02d-%02d-01' % (next_year, next_month)

                name = _('Auto import [month: %s-%s]') % (
                    from_month, from_year)

                self.import_one_cost(cr, uid, name=name, from_date=from_date, 
                    to_date=to_date, error=error, context=context)
                
                # ------------------
                # History operation:
                # ------------------
                os.rename(
                    os.path.join(path, filename),
                    os.path.join(path, 'history', '%s.%s' % (
                        datetime.now().strftime('%Y%m%d.%H%M%S'),
                        filename, )),
                    )

            except:
                _logger.error('No correct file format: %s' % filename)
                _logger.error((sys.exc_info(), ))
        _logger.info("End auto import of file cost")
        return True

hr_analytic_timesheet()    

class contract_employee_timesheet_tipology(osv.osv):
    ''' Contract tipology: contains a list of "day of a week" elements and the
        total amount of hour to be worked that day
    '''    
    _name = 'contract.employee.timesheet.tipology'
    _description = 'Timesheet tipology'
    
    _columns = {
        'name': fields.char('Description', size=64),
        }
contract_employee_timesheet_tipology()

class contract_employee_timesheet_tipology_line(osv.osv):
    ''' Sub element of contract tipology: contains dow and tot. hours
    '''    
    _name = 'contract.employee.timesheet.tipology.line'
    _description = 'Timesheet tipology line'
    
    _columns = {
        'name': fields.float('Tot. hours', required=True, digits=(4, 2)),
        'week_day':fields.selection(week_days,'Week day', select=True),
        'contract_tipology_id':fields.many2one(
            'contract.employee.timesheet.tipology', 'Contract tipology', 
            required=True, ondelete='cascade'),
        }
contract_employee_timesheet_tipology_line()

class contract_employee_timesheet_tipology(osv.osv):
    ''' Contract tipology: add relation 2many fields
    '''    
    _inherit = 'contract.employee.timesheet.tipology'

    _columns = {
        'line_ids': fields.one2many(
            'contract.employee.timesheet.tipology.line', 
            'contract_tipology_id', 'Lines'),
        }
contract_employee_timesheet_tipology()

class contract_employee_festivity(osv.osv):
    ''' Festivity manage: 
        manage static festivity (also with from-to period)
        manage dynamic list of festivity (ex. Easter monday)
    '''    
    _name = 'contract.employee.festivity'
    _description = 'Contract festivity'
    
    # TODO: function for compute festivity
    # TODO: function for validate: 
    #       static date (max day for day-month)
    #       from to period evaluation (no interference)
    #       no double comment in dynamic date 
    #          (2 Easter monday for ex. in the same year)
    
    def is_festivity(self, cr, uid, date, context=None):
        ''' Test if datetime element date is in festifity rules
        '''
        # Static festivity (periodic):
        date_ids = self.search(cr, uid, [
            ('static', '=', True), 
            ('periodic', '=', True), 
            ('day', '=', date.day),
            ('month', '=', date.month),
            ('periodic_from', '>=', date.year),
            ('periodic_to', '<=', date.year),
            ]) 
        if date_ids:
            return True

        # Static festivity not periodic:
        date_ids = self.search(cr, uid, [
            ('static', '=', True), 
            ('periodic', '=', False), 
            ('day', '=', date.day),
            ('month', '=', date.month),
            ]) 
        if date_ids:
            return True

        # Dinamic festivity:
        date_ids = self.search(cr, uid, [
            ('static', '=', False), 
            ('dynamic_date', '=', date.strftime("%Y-%m-%d")),
            ])
        if date_ids:
            return True
        return False
    
    _columns = {
        'name': fields.char('Description', size=64),

        # static festivity:
        'static': fields.boolean('Static festivity', 
            help="It means that every year this festivity is the same day (ex. Christmas = 25 of dec.), if not it's dynamic (ex. Easter monday)"),
        'day': fields.integer('Static day'),
        'month': fields.integer('Static month'),
        # static but periodic:
        'periodic': fields.boolean('Periodic festivity', 
            help="Festivity is only for a from-to period (ex.: Patronal festivity but for a period because of changing city)"),
        'periodic_from': fields.integer('From year'),
        'periodic_to': fields.integer('To year'),
        
        # dinamic festivity (no periodic is allowed):
        'dynamic_date': fields.date('Dynamic Date'),
        }

    _defaults = {
        'periodic_from': lambda *a: time.strftime('%Y'),
        'periodic_to': lambda *a: time.strftime('%Y'),
        }
contract_employee_festivity()

class hr_employee_extra(osv.osv):
    """ Employee extra fields for manage contract and working hours
        TODO: create a list of working hour contract (for history of elements)
    """    
    _inherit = 'hr.employee'
    
    def check_consistency_employee_user_department(
            self, cr, uid, context=None):
        ''' Procedure for xml-rpc call for check consistency of DB
            1. check if employee has user linked
            2. check if 
        '''
        #TODO finirla
        user_pool = self.pool.get("res.users")
        employee_proxy=self.browse(cr, uid, self.search(
            cr, uid, [], context=context))
        
        for employee in employee_proxy:
            if employee.user_id and employee.department_id:                
                update = user_pool.write(cr, uid, employee.user_id.id, {
                    'context_department_id': employee.department_id.id})
        return True
        
    _columns = {
        'contract_tipology_id':fields.many2one(
            'contract.employee.timesheet.tipology', 'Work time', 
            help="Working time for this employee, tipically a contract tipology, like: full time, part time etc. (for manage hour and presence)"),
        }
hr_employee_extra()

# -----------------------------------------------------------------------------
# Add importation hour cost for employee:
# -----------------------------------------------------------------------------
class product_product(osv.osv):
    """ Add extra info to manage product linked to employee:
    """    
    _inherit = 'product.product'

    _columns = {
        'product_employee_id': fields.many2one(
            'hr.employee', 'Employee linked', 
            help='Product as hour cost for selected employee'),
        'update_price_date': fields.date('Update price'),
        }
        
    _defaults = {
        'product_employee_id': lambda *x: False,
        }
product_product()        

class hr_employee_hour_cost(osv.osv):
    """ Temporary zone for create a list of employee, set product and force 
        update of product on OpenERP and analytic line value
    """    
    _name = 'hr.employee.hour.cost'
    _description = 'Employee load hour cost'
    _rec_name = 'product_id'

    
    def load_all_employee(self, cr, uid, domain=None, force_cost=None,
            context=None):
        ''' Load all active employee, during operazion create if not present
            Reference product (or linked) without associate, after a wizard do
            the magic
            domain = filter for hr.emploee
            force_cost: dict with key = employee ID, value = new price
        '''
        # Remove current list:
        if domain is None: # domain passed (file list or wizard list)
            domain = []

        if force_cost is None: # list of user pre-passed (file)
            force_cost = {}

        # Remove all previous elements:
        current_ids = self.search(cr, uid, [], context=context)
        self.unlink(cr, uid, current_ids, context=context)

        # ---------------------------------------------------------------------
        # Load new list:
        # ---------------------------------------------------------------------
        if not force_cost: # for wizard load only (file admitted):
            domain.append(('active', '=', True))

        # Load before all product employee list (to know if need do be created)    
        employee_pool = self.pool.get('hr.employee')
        product_pool = self.pool.get('product.product')
            
        # Create dict from personal product-employee
        products = {} # ID product for employee 
        costs = {} # standard price for employee

        # Pre-load cost and products:
        employee_ids = employee_pool.search(cr, uid, domain, context=None)
        product_ids = product_pool.search(cr, uid, [
            ('product_employee_id', '!=', False)], context=None)
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):    
            # Save id and price:
            products[product.product_employee_id.id] = product.id
            costs[product.product_employee_id.id] = product.standard_price 

        # Loop on selected employee:
        for employee in employee_pool.browse(
                cr, uid, employee_ids, context=context):
            hour_id = 4 # TODO
            categ_id = 1 # TODO
            cost_old = employee.product_id.standard_price or 0.0
            data = {
                'name': _('Hour cost: %s') % employee.name,
                'type': 'service',
                'procure_method': 'make_to_stock',
                'supply_method': 'buy',
                'uom_id': hour_id,
                'uom_po_id': hour_id,
                'cost_method': 'standard',
                'standard_price': cost_old,
                'uos_coeff': 1.0,
                'mes_type': 'fixed',
                'categ_id': categ_id,
                'product_employee_id': employee.id,
                'sale_ok': True,
                'purchase_ok': True,
                'is_hour_cost': True,
                }
            
            if employee.id in products: # employee has yet a product:
                new = False
                product_pool.write( # TODO remove?
                    cr, uid, products[employee.id], data, context=context)
            else:
                new = True                
                # Create product element (not associate)
                costs[employee.id] = cost_old
                products[employee.id] = product_pool.create(
                    cr, uid, data, context=context)

            cost_new = (force_cost.get(employee.id, False) or 
                costs[employee.id] or 
                0.0) # 0 not a sort of default value!

            # Pre-load list:
            data = {
                'employee_id': employee.id,
                'product_id': products[employee.id],
                'current_product_id': employee.product_id.id,
                'new': new,
                'hour_cost': cost_old,
                'hour_cost_new': cost_new,
                }   
            self.create(cr, uid, data, context=context)        
        return {}
        
    _columns = {
        'employee_id': fields.many2one('hr.employee', 'Employee'),
        'current_product_id': fields.many2one('product.product', 
            'Current product'),
        'product_id': fields.many2one('product.product', 'Product'),
        'new': fields.boolean('New product'),
        'hour_cost': fields.float('Current hour cost', digits=(16, 2)),
        'hour_cost_new': fields.float('New hour cost', digits=(16, 2)),
        }
hr_employee_hour_cost()

class hr_employee_force_log(osv.osv):
    """ Object that log all force operations
    """
    _name = 'hr.employee.force.log'
    _description = 'Employee force log'

    def log_operation(self, cr, uid, name, from_date, error=None, 
            context=None):    
        ''' Create new record with log of new price se for employee and date
            of intervent update (in analytic lines)
            dict for error (key = lines)
            Return line (to save in analytic modification)            
        '''
        if error is None:
            error = []

        cost_pool = self.pool.get('hr.employee.hour.cost')
        cost_ids = cost_pool.search(cr, uid, [], context=context)
        note = ''
        error_text = ''
        for value in error:
            error_text += "%s\n" % value
            
        for cost in cost_pool.browse(cr, uid, cost_ids, context=context):
            note += _('%s hour cost %s >> %s\n') % (
                cost.employee_id.name,
                cost.hour_cost,
                cost.hour_cost_new,
                )
        return self.create(cr, uid, {
            #date
            'name': name or _(
                'Forced costs from date: %s') % from_date,
            'from_date': from_date,
            'note': note,
            'error': error_text or False, # for view
            }, context=context)        
        
    _columns = {
        'name': fields.char('Description', size=80),
        'date': fields.datetime('Date operation'),
        'from_date': fields.date('From date',
            help='All intervent from this date will use new value'),
        'note': fields.text('Note'),
        'error': fields.text('Error'),
        }

    _defaults = {
        'date': lambda *x: datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'from_date': lambda *x: datetime.now().strftime('%Y-%m-%d'),
        }
hr_employee_force_log()

class account_analytic_line(osv.osv):
    """ Auto update record (save element for get list)
    """
    _inherit = 'account.analytic.line'

    _columns = {
        'update_log_id': fields.many2one(
            'hr.employee.force.log', 'Auto update', ondelete='set null'),        
        }
account_analytic_line()

class hr_employee_force_log(osv.osv):
    """ Update log with *many relation fileds
    """
    _inherit = 'hr.employee.force.log'
    
    _columns = {
        'line_ids': fields.one2many('account.analytic.line', 'update_log_id',
            'Line update from this log'),
        }
hr_employee_force_log()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
