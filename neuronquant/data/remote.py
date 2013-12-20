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


import urllib2
import re
import pytz

from pandas import Index, Series, DataFrame
from pandas.io.data import DataReader
import pandas as pd

import numpy as np

from xml.dom import minidom, Node
import json

from logbook import Logger
log = Logger('Remote')

import neuronquant.utils.datautils as datautils
from neuronquant.utils.dates import epochToDate
import neuronquant.utils.utils as utils


class Alias (object):
    #TODO: Uniform Quote dict structure to implement (and fill in different methods)
    #tmp
    SYMBOL = 't'
    MARKET = 'e'
    VALUE = 'l'
    DATE = 'lt'
    VARIATION = 'c'
    VAR_PER_CENT = 'cp'


#TODO 1. Every fetcher should take an index object, construct mostly with date_range
#TODO Use requests module to fetch remote data, cleaner http://docs.python-requests.org/en/latest/
class Fetcher(object):
    ''' Web access to data '''
    def __init__(self, timezone=pytz.utc):
        self.tz = timezone

    def getMinutelyQuotes(self, symbol, market, index):
        days = abs((index[index.shape[0] - 1] - index[0]).days)
        freq = int(index.freqstr[0])
        if index.freqstr[1] == 'S':
            freq += 1
        elif index.freqstr[1] == 'T':
            freq *= 61
        elif index.freqstr[1] == 'H':
            freq *= 3601
        else:
            log.error('** No suitable time frequency: {}'.format(index.freqstr))
            return None
        url = 'http://www.google.com/finance/getprices?q=%s&x=%s&p=%sd&i=%s' \
                % (symbol, market, str(days), str(freq + 1))
        log.info('On %d days with a precision of %d secs' % (days, freq))
        try:
            page = urllib2.urlopen(url)
        except urllib2.HTTPError:
            log.error('** Unable to fetch data for stock: %s'.format(symbol))
            return None
        except urllib2.URLError:
            log.error('** URL error for stock: %s'.format(symbol))
            return None
        feed = ''
        data = []
        while (re.search('^a', feed) is None):
            feed = page.readline()
        while (feed != ''):
            data.append(np.array(map(float, feed[:-1].replace('a', '').split(','))))
            feed = page.readline()
        dates, open, close, high, low, volume = zip(*data)
        adj_close = np.empty(len(close))
        adj_close.fill(np.NaN)
        data = {
                'open'      : open,
                'close'     : close,
                'high'      : high,
                'low'       : low,
                'volume'    : volume,
                'adj_close' : adj_close  # for compatibility with Fields.QUOTES
        }
        #NOTE use here index ?
        dates = Index(epochToDate(d) for d in dates)
        return DataFrame(data, index=dates.tz_localize(self.tz))

    def getHistoricalQuotes(self, symbol, index, market=None):
        assert (isinstance(index, pd.Index))
        source = 'yahoo'
        try:
            quotes = DataReader(symbol, source, index[0], index[-1])
        except:
            log.error('** Could not get {} quotes'.format(symbol))
            return pd.DataFrame()
        if index.freq != pd.datetools.BDay() or index.freq != pd.datetools.Day():
            #NOTE reIndexDF has a column arg but here not provided
            quotes = utils.reIndexDF(quotes, delta=index.freq, reset_hour=False)
        if not quotes.index.tzinfo:
            quotes.index = quotes.index.tz_localize(self.tz)
        quotes.columns = utils.Fields.QUOTES
        return quotes

    def get_stock_snapshot(self, symbols, markets=None, light=True):
        # Removing yahoo code for exchange market at th end of the symbol, google doesn't need it
        #FIXME As no market is specified, there are mistakes, like with Schneider
        backup_symbols = list(symbols)
        snapshot = dict()
        for i, s in enumerate(symbols):
            if s.find('.pa') > 0:
                symbols[i] = s[:-3]
        if isinstance(symbols, str):
            #snapshot = {symbols: dict()}
            symbols = [symbols]
        #elif isinstance(symbols, list):
            #snapshot = {q: dict() for q in symbols}
        if light:
            assert markets
            data = self._lightSummary(symbols, markets)
        else:
            data = self._heavySummary(symbols)
        if not data:
            log.error('** No stock informations')
            return None
        for i, item in enumerate(backup_symbols):
            snapshot[item] = data[i]
        return snapshot

    def _lightSummary(self, symbols, markets):
        #TODO map dict keys and understand every field
        url = 'http://finance.google.com/finance/info?client=ig&q=%s:%s' \
                % (symbols[0], markets[0])
        for i in range(1, len(symbols)):
            url = url + ',%s:%s' % (symbols[i], markets[i])
        log.info('Retrieving light Snapshot from %s' % url)
        return json.loads(urllib2.urlopen(url).read()[3:], encoding='latin-1')

    def _heavySummary(self, symbols):
        url = 'http://www.google.com/ig/api?stock=' + '&stock='.join(symbols)
        log.info('Retrieving heavy Snapshot from %s' % url)
        try:
            url_fd = urllib2.urlopen(url)
        except IOError:
            log.error('** Bad url: %s' % url)
            return None
        try:
            xml_doc = minidom.parse(url_fd)
            root_node = xml_doc.documentElement
        except:
            log.error('** Parsing xml google response')
            return None
        i = 0
        #snapshot = {q : dict() for q in symbols}
        snapshot = list()
        ticker_data = dict()
        for node in root_node.childNodes:
            if (node.nodeName != 'finance'):
                continue
            ticker_data.clear()
            for item_node in node.childNodes:
                if (item_node.nodeType != Node.ELEMENT_NODE):
                    continue
                ticker_data[item_node.nodeName] = item_node.getAttribute('data')
            i += 1
            snapshot.append(ticker_data)
        return snapshot

    #TODO: a separate class with functions per categories of data
    #NOTE: The YQL can fetch this data (http://www.yqlblog.net/blog/2009/06/02/getting-stock-information-with-%60yql%60-and-open-data-tables/)
    def getStockInfo(self, symbols, fields):
        for f in fields:
            #NOTE could just remove field and continue
            if f not in datautils.yahooCode:
                log.error('** Invalid stock information request.')
                #return None
                fields.pop(f)
                if len(fields) == 0:
                    return DataFrame()
        #TODO: remove " from results
        #TODO A wrapper interface to have this document through ticker names
        #symbols, markets = self.db.getTickersCodes(index, quotes)
        fields.append('error')
        url = 'http://finance.yahoo.com/d/quotes.csv?s='
        url = url + '+'.join(symbols) + '&f='
        url += ''.join([datautils.yahooCode[item.lower()] for item in fields])
        data = urllib2.urlopen(url)
        df = dict()
        for item in symbols:
            #FIXME: ask size return different length arrays !
            df[item] = Series(data.readline().strip().strip('"').split(','), index=fields)
        return DataFrame(df)
