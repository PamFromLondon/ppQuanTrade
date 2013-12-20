#!/usr/bin/python
# encoding: utf-8
#
# Copyright 2013 Xavier Bruhiere
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from zipline.utils.factory import load_from_yahoo, load_bars_from_yahoo
from pandas.rpy.common import convert_to_r_matrix

import requests
from pandas.io.data import DataReader, get_quote_yahoo
import pandas as pd
import numpy as np
import json
from xml.dom import minidom, Node
import urllib2

import logbook
log = logbook.Logger('Remote')

from neuronquant.utils.decorators import (
    use_google_symbol, invert_dataframe_axis)
from neuronquant.utils import apply_mapping
from neuronquant.data.datafeed import DataFeed


finance_urls = {
    'yahoo_hist': 'http://ichart.yahoo.com/table.csv',
    'yahoo_infos': 'http://finance.yahoo/q/pr',
    'google_prices': 'http://www.google.com/finance/getprices',
    'snapshot_google_light': 'http://www.google.com/finance/info',
    'snapshot_google_heavy': 'http://www.google.com/ig/api'
}


#TODO A decorator for symbol harmonisation ?
class Remote(object):
    '''
    Entry point to remote access to data
    Mainly offer a simpler interface and a dataaccess harmonisation
    Plus symbol check and complete, timezone, currency conversion
    Plus reindexage ?
    '''
    def __init__(self, country_code=None):
        '''
        Parameters
            country_code: str
                This information is used to setup International object
                and get the right local conventions for lang,
                dates and currencies. None will stand for 'fr'
        '''
        #self.locatioon = world.International(country_code)
        self.datafeed = DataFeed()

    #NOTE with args and kwargs ?
    def fetch_equities_daily(self, equities, ohlc=False,
                             r_type=False, returns=False, **kwargs):
        if len(equities) == 0:
            return pd.DataFrame()
        if isinstance(equities, str):
            equities = equities.split(',')
        symbols = [self.datafeed.guess_name(equity) for equity in equities]

        if ohlc:
            data = load_bars_from_yahoo(stocks=symbols, **kwargs)
            data.items = equities
        else:
            data = load_from_yahoo(stocks=symbols, **kwargs)
            data.columns = equities

            #NOTE Would it work with a pandas panel ?
            if returns:
                data = ((data - data.shift(1)) / data).fillna(method='bfill')
            if r_type:
                data = convert_to_r_matrix(data)

        return data

    def fetch_equities_snapshot(self, *args, **kwargs):
        '''
        Use Yahoo and google finance service to fetch
        current infromations about given equitiy names
        ______________________________________________
        Parameters
            args: tuple
                company names to consider
            kwargs['level']: int
                Quantity of information level
        ______________________________________________
        Return
            snapshot: pandas.DataFrame
                with names as columns and informations as index
        '''
        equities = args
        if not equities:
            equities = kwargs.get('symbols', [])
        level = kwargs.get('level', 0)
        #TODO Symbols are usualy reused, cach them
        symbols = [self.datafeed.guess_name(equity) for equity in equities]

        if not level:
            # default level, the lightest
            snapshot = snapshot_yahoo_pandas(symbols)
        elif level == 1:
            snapshot = snapshot_google_light(symbols)
        elif level == 2:
            snapshot = snapshot_google_heavy(symbols)
        else:
            raise ValueError('Invalid level of information requested')

        # Give columns back equities names requested
        snapshot.columns = equities
        return snapshot

    def _localize_data(self, data):
        '''
        Inspect data and applie localisation
        on date and monnaie values
        '''
        assert isinstance(data, pd.Dataframe) or isinstance(data, dict)


#NOTE check zipline.utils.factory, use DataReader as well
def historical_pandas_yahoo(symbol, source='yahoo', start=None, end=None):
    '''
    Fetch from yahoo! finance historical quotes
    '''
    #NOTE Panel for multiple symbols ?
    #NOTE Adj Close column  name not cool (a space)
    return DataReader(symbol, source, start=start, end=end)


#NOTE From here every methods has the same signature:
#     pandas.DataFrame = fct(yahoo_symbol(s))
# Index symbol ex: ^fchi
@invert_dataframe_axis
def snapshot_yahoo_pandas(symbols):
    '''
    Get a simple snapshot from yahoo, return dataframe
    __________________________________________________
    Return
        pandas.DataFrame with symbols as index
        and columns = [change_pct, time, last, short_ratio, PE]
    '''
    if isinstance(symbols, str):
        symbols = [symbols]
    return get_quote_yahoo(symbols)


#NOTE Can use symbol with market: 'goog:nasdaq', any difference ?
@use_google_symbol
# Index symbol ex: PX1
def snapshot_google_light(symbols):
    payload = {'client': 'ig', 'q': ','.join(symbols)}
    response = requests.get(finance_urls['snapshot_google_light'],
                            params=payload)
    #TODO In utils.errors my first error module that handle errors codes
    #TODO check return code (200)
    #TODO remapping
    json_infos = json.loads(response.text[3:], encoding='utf-8')

    snapshot = {}
    for i, quote in enumerate(json_infos):
        snapshot[symbols[i]] = apply_mapping(quote, google_light_mapping)

    return pd.DataFrame(snapshot)


#TODO all values are string, make them floats (with a mapping)
@use_google_symbol
def snapshot_google_heavy(symbols):
    url = finance_urls['snapshot_google_heavy'] + '?stock=' + '&stock='.join(symbols)
    log.info('Retrieving heavy Snapshot from %s' % url)
    try:
        url_fd = urllib2.urlopen(url)
    except IOError:
        log.error('** Bad url: %s' % url)
        return pd.DataFrame()

    try:
        xml_doc = minidom.parse(url_fd)
        root_node = xml_doc.documentElement
    except:
        log.error('** Parsing xml google response')
        return pd.DataFrame()
    i = 0
    snapshot = {q: {} for q in symbols}
    for i, node in enumerate(root_node.childNodes):
        if (node.nodeName != 'finance'):
            continue
        for item_node in node.childNodes:
            if (item_node.nodeType != Node.ELEMENT_NODE):
                continue
            snapshot[symbols[i]][item_node.nodeName] = item_node.getAttribute('data')

    return pd.DataFrame(snapshot)


@property
def google_light_mapping():
    return {
        'change': (str, 'c'),
        'change_str': (str, 'ccol'),
        'change_perc': (float, 'cp'),
        'exchange': (str, 'e'),
        'id': (int, 'id'),
        'price': (str, 'l'),
        'last_price': (lambda x: x, 'l_cur'),
        'date': (str, 'lt'),
        'time': (str, 'ltt'),
        's': (int, 's'),
        'symbol': (str, 't'),
    }
