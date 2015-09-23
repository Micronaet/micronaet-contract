# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP module
#    Copyright (C) 2010 Micronaet srl (<http://www.micronaet.it>) and the
#    Italian OpenERP Community (<http://www.openerp-italia.com>)
#
#    ########################################################################
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2008 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import os
import sys
import logging
from tools.translate import _
from osv import osv, fields
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class hr_employee_force_hour(osv.osv_memory):
    ''' Load elements and force hour cost in employee update analytic lines
    '''
    
    _name = 'hr.employee.force.hour.wizard'
    _description = 'Employee force hour cost'
    
    # --------------------
    # Schedule operations:
    # --------------------
    def schedule_importation_cost(self, cr, uid, path='~/etl/employee', 
            bof='cost', separator=';', context=None):
        ''' Loop on cost folder searching file that start with bof
        '''
        from os import listdir
        from os.path import isfile, join

        path = os.path.expanduser(path)
        cost_file = [
            filename for filename in listdir(path) if 
                    isfile(join(path, filename)) and filename.startswith(bof)]

        for filename in cost_file:
            try:
                # Load:
                self.load_one_cost(cr, uid, path, filename, separator, 
                    context=context)
                    
                # Import:
                # parse date
                filename. 
                file_date = os.path.splitext(filename)[-4:]
                from_month = file_date[:2]
                from_year = file_date[2:]
                # Next value
                if from_month = '12':
                    next_month = '01'
                    next_year = '%02d' % int(from_year) + 1
                else:    
                    next_month = '%02d' % int(from_month) + 1
                    next_year = from_year

                from_date = '01-%02d-%02d' % (from_month, from_year)
                to_date = '01-%02d-%02d' % (to_month, to_year)

                self.import_one_cost(cr, uid, from_date=from_date, 
                    to_date=to_date, context=context)
            except:
                #raise osv.except_osv(
                #    _('Error!'), _('No file found for import: %s' % fullname))
                _logger.error('No correct file format: %s' % filename)
        return True

    # --------
    # Utility:        
    # --------
    def load_one_cost(self, cr, uid, path, filename, separator, 
            from_wizard=False, context=None):
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
            try:
                value = value.replace(',', '.')
                return float(value)
            except:
                return 0.0

        tot_col = 5 # TODO change if file will be extended
        fullname = join(os.path.expanduser(path), filename)
        domain = []
        force_cost = {}
       
        # Load from file employee:
        employee_pool = self.pool.get('hr.employee')            
        item_ids = [] # employee list
        
        # Check file present (for wizard but used alse for sched.)?
        try: 
            f = open(os.path.expanduser(fullname), 'rb')
        except:
            raise osv.except_osv(
                _('Error!'), _('No file found for import: %s' % fullname))

        i = 0
        for line in f:
            i += 1
            line = line.strip()
            if not line:
                _logger.warning('Empty line (jumped): %s' % i)
                continue
            record = line.split(separator)
            if len(record) != tot_col:
                _logger.error('Record different format: %s (col.: %s)' % (
                    tot_col))
                continue
            
            code = format_string(record[0], False)
            name = format_string(record[1]).title()
            surname = format_string(record[2]).title()
            cost = format_float(record[3])
            total = format_float(record[4])
            
            # TODO search first for code
            employee_ids = employee_pool.search(cr, uid, [
                '|',
                ('name', '=', "%s %s" % (name, surname)),
                ('name', '=', "%s %s" % (surname, name)),
                ], context=context)

            # TODO update code if found only one    
            if len(employee_ids) == 1:
                employee_id = employee_ids[0]
                if employee_id in item_ids:
                    _logger.error('Double in CSV file: %s %s' % (
                        surname, name))
                else:
                    item_ids.append(employee_id)
                    force_cost[employee_id] = cost # save cost
            elif len(employee_ids) > 1:
                _logger.error('Fount more employee: %s %s' % (
                    surname, name))                   
            else:
                _logger.error('Employee not found: %s %s' % (
                    surname, name))
            
        domain.append(('id', 'in', item_ids))
                
        # Load in object for check:
        self.pool.get('hr.employee.hour.cost').load_all_employee(
            cr, uid, domain, force_cost, context=context)
            
        # Open view:    
        if from_wizard:
            return {
                'view_type': 'form',
                'view_mode': 'tree,form',
                'res_model': 'hr.employee.hour.cost', # object linked to the view
                #'views': [(view_id, 'form')],
                'view_id': False,
                'type': 'ir.actions.act_window',
                #'target': 'new',
                #'res_id': res_id, # ID selected
                }
        else:
            return True
    
    def import_one_cost(self, cr, uid, name='', from_date=False, to_date=False,
            from_wizard=False, context=None):
        ''' Import previous loaded list of employee costs
            name: for log description
            from_date: from date update analytic line
            from_wizard: for return operation 
        '''
        # Pools used:
        cost_pool = self.pool.get('hr.employee.hour.cost')
        product_pool = self.pool.get('product.product')
        employee_pool = self.pool.get('hr.employee')
        line_pool = self.pool.get('account.analytic.line')
        log_pool = self.pool.get('hr.employee.force.log')

        # ---------------
        # Log operations:
        # ---------------
        # Note: Logged before for get ID
        update_log_id = log_pool.log_operation(
            cr, uid, name, from_date, context=context)

        cost_ids = cost_pool.search(cr, uid, [], context=context)

        # TODO filter new = old?
        current_ids = cost_pool.search(cr, uid, [], context=context)
        for cost in cost_pool.browse(cr, uid, cost_ids, context=context):
            try:
                # ---------------------------------------------
                # Force product to employee (for new creations):
                # ---------------------------------------------
                # TODO optimize for create update only new product
                employee_pool.write(cr, uid, cost.employee_id.id, {
                    'product_id': cost.product_id.id,
                    }, context=context)            

                # -----------------------------
                # Force new product hour costs:
                # -----------------------------        
                product_pool.write(cr, uid, cost.product_id.id, {
                    'standard_price': cost.hour_cost_new
                    }, context=context)
                
                # ------------------------------------------------
                # Update analytic lines save log operation parent:
                # ------------------------------------------------
                #if abs(cost.hour_cost - cost.hour_cost_new) >= 0.01: # approx
                domain = [
                    ('user_id', '=', cost.employee_id.user_id.id),
                    ('date', '>=', from_date),
                    ]
                if to_date: # for schedule update only
                    domain.append(
                        ('date', '<', to_date),
                        )    
                line_ids = line_pool.search(cr, uid, domain, context=context)
                    
                # loop for total calculation:
                for line in line_pool.browse(
                        cr, uid, line_ids, context=context):    
                    line_pool.write(cr, uid, line.id, {
                        'amount': -(
                            cost.product_id.standard_price * line.unit_amount),
                        'update_log_id': update_log_id,
                        'product_id': cost.product_id.id, 
                        }, context=context)
            except:
                _logger.error('Employee update: %s' % cost.employee_id.name)
                _logger.error(sys.exc_info(), )
                # TODO log error for reinsert (not remove)
                #current_ids.remove(cost.id) # not update (remain)
                continue

        # -------------------------------------
        # Remove all record (update correctly):
        # -------------------------------------
        cost_pool.unlink(cr, uid, current_ids, context=context)
        if from_wizard:
            return {'type': 'ir.actions.act_window_close'}
        else:    
            return True

    # --------------
    # Button events:
    # --------------
    def load_button(self, cr, uid, ids, context=None):
        ''' Load all active employee and his product, create if not present
            After open view with the list
        '''
        # ----------------------
        # Import file parameters
        # ----------------------
        # TODO load parameter from scheduled importation
        path = '~/etl/servizi/employee/'
        separator = ';'
        bof = 'costi' # begin of file

        return self.load_one_cost(cr, uid, path, filename, separator, 
            from_wizard=True, context=context)

    def force_button(self, cr, uid, ids, context=None):
        ''' Force button update records
        ''' 
        wiz_proxy = self.browse(cr, uid, ids)[0]
        
        # NOTE: no to_date from wizard:
        return self.import_one_cost(cr, uid, wiz_proxy.name, 
            wiz_proxy.from_date, False, from_wizard=True, context=context)

    _columns = {
        'name': fields.char('Description', size=80),
        'from_date': fields.date('From date', 
            help='Choose the date, every intervent from that date take costs'),
        #'to_date': fields.date('To date', 
        #    help='Choose the date, every intervent from that date take costs'),
        'operation': fields.selection([
            ('load', 'Load current'),
            ('absence', 'Force update'),
            ], 'Operation', select=True, required=True),
        'department_id': fields.many2one('hr.department', 'Department'),
        'mode': fields.selection([
            ('file', 'From file'),
            ('employee', 'From employee list'),
            ], 'Mode'),
        }    
        
    _defaults = {
        'from_date': lambda *x: datetime.now().strftime('%Y-%m-%d'),
        #'to_date': lambda *x: datetime.now().strftime('%Y-%m-%d'),
        'operation': lambda *a: 'load',
        'mode': lambda *a: 'file',
        }
hr_employee_force_hour()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

