# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import sys
import logging
import urllib
from osv import fields, osv
from datetime import datetime, timedelta


_logger = logging.getLogger(__name__)

class res_city(osv.osv):
    ''' Object relation for join analytic account with city
    '''
    _inherit = "res.city"

    _columns = {
        'trip_km': fields.float('Trip km (average)', digits=(16, 2),
            help="Km average for headquarter"),
        'tour_km': fields.float('Tour km (average)', digits=(16, 2),
            help="Km average for tour in the city"),
        }
    
    # -------------------------------------------------------------------------
    #                             Private function:
    # -------------------------------------------------------------------------
    def _prepare_element(self, cr, uid, street, zipcode, city, state='Italia',
            context=None):
        ''' Generate a string with all address parameter used for compute 
            distances
        '''
        value = "%s %s %s %s" % (street, zipcode, city, state)                
        return value.strip().replace(' ', '+').replace(',', '') 

    def _distance_query(self, origin, destination):
        ''' Generate query string for compute km from origin to destination
            element in string ask for return json object
        '''
        try:
            return '%sorigins=%s&destinations=%s&sensor=false' % (
                'http://maps.googleapis.com/maps/api/distancematrix/json?',
                origin, 
                destination,
                )
        except IOError:
            return None

    def update_distance_from_google(self, cr, uid, ids, context=None):
        ''' Master function that calculate distance between origin and 
            destination partner id
            NOTE: correct function evalute start and to elements 
        '''
        # ---------------------------------------------------------------------
        #                      Get company address:
        # ---------------------------------------------------------------------
        company_pool = self.pool.get('res.company')
        company_ids = company_pool.search(cr, uid, [], context=context)
        company_proxy = company_pool.browse(
            cr, uid, company_ids, context=context)[0]
        partner = company_proxy.partner_id.address[0] # TODO find default!!!
        origin = self._prepare_element(
            cr, uid, partner.street, partner.zip, partner.city, 
            partner.country_id.name, context=context),
        _logger.info('Origin query: %s' % origin)

        # ---------------------------------------------------------------------
        #                      Loop on city passed:
        # ---------------------------------------------------------------------
        city_pool = self.pool.get('res.city')
        for city in city_pool.browse(cr, uid, ids, context=context):
            destination = self._prepare_element(
                cr, uid, '', 
                city.zip, 
                '%s (%s)' % (
                    city.name, city.province_id.code), 
                'Italia', 
                context=context),        
            query = self._distance_query(origin, destination)        
            response = eval(urllib.urlopen(query).read())
            trip_km = 0.0
            try:
                status = response.get('status', False)
                if status == 'OK':                    
                    trip_km = response['rows'][0]['elements'][0][
                        'distance']['value'] / 1000.0  # km
                    _logger.info('Destination query: %s' % destination)
                    _logger.info('Google response: %s' % response)
            except:    
                pass
            if trip_km:
                city_pool.write(cr, uid, city.id, {
                    'trip_km': trip_km, }, context=context)
        return True            
    
    # Button update all partner:        
    def update_one_city_distance(self, cr, uid, ids, context=None):
        return self.update_distance_from_google(
            cr, uid, ids, context=context)

    def update_all_city_distance(self, cr, uid, ids, context=None):
        # Search city
        city_pool = self.pool.get('res.city')
        item_ids = city_pool.search(cr, uid, [], context=context)
        
        # Update all:
        return self.update_distance_from_google(
            cr, uid, item_ids, context=context)    
res_city()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
