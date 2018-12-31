#!/usr/bin/env python3
# coding: utf-8

import certifi
import os
import sys
import argparse
import hmac
import json
import locale
import pycurl
import random
import yaml
from base64 import b64encode
from datetime import datetime
from io import BytesIO
from hashlib import sha1
from urllib.parse import urlencode, quote, parse_qs

posts_ep = '/wp/v2/posts'
categories_ep = '/wp/v2/categories'
tags_ep = '/wp/v2/tags'
comments_ep = '/wp/v2/comments'
media_ep = '/wp/v2/media'
users_ep = '/wp/v2/users'

def generate_nonce(length=8):
    """Generate pseudorandom number."""
    return ''.join([str(random.randint(0, 9)) for i in range(length)])

class OAuth10aNoTokenException(Exception):
    pass

class OAuth10a:
    
    def __init__(self, consumerKey, consumerSecret, oauthToken = None, oauthTokenSecret = None):
        self._consumerKey = consumerKey
        self._consumerSecret = consumerSecret
        self._oauthToken = oauthToken
        self._oauthTokenSecret = oauthTokenSecret
    
    def updateOAuthToken(self, token, secret):
        self._oauthToken = token
        self._oauthTokenSecret = secret
    
    def _getOAuthParams(self):
        params = {
            'oauth_consumer_key':     self._consumerKey,
            'oauth_signature_method': 'HMAC-SHA1',
            'oauth_version':          '1.0',
            'oauth_timestamp':        str(int(datetime.now().timestamp())),
            'oauth_nonce':            generate_nonce(8),
        }
        if (self._oauthToken is not None):
            params['oauth_token'] = self._oauthToken
            
        return params
    
    @staticmethod
    def _sortOAuthParams(oauth_params_list):
        return sorted(oauth_params_list, key=lambda x: x[0] + x[1])
    
    @staticmethod
    def _OAuthParamsToHeader(oauth_params):
        
        parts = []
        parts += ['{0:s}="{1:s}"'.format(quote(k, safe='-._~'), quote(v, safe='-._~')) for k, v in OAuth10a._sortOAuthParams(list(oauth_params.items()))]
        return 'Authorization: OAuth ' + ', '.join(parts)
    
    def getOAuthHeader(self, method, url, query_post_params, additional_oauth_params = {}):
    
        oauth_params = self._getOAuthParams()
        oauth_params.update(additional_oauth_params)
        if ('oauth_signature' in oauth_params):
            del oauth_params['oauth_signature']
        terms = list(oauth_params.items()) + list(query_post_params.items())
        terms = OAuth10a._sortOAuthParams(terms)
        
        text = method + '&' + quote(url, safe='') + '&' + quote('&').join([quote(k) + quote('=') + quote(v) for k, v in terms])
        key = quote(self._consumerSecret) + '&'
        if (self._oauthTokenSecret is not None):
            key += quote(self._oauthTokenSecret)
        hashed = hmac.new(key.encode('utf-8'), text.encode('utf-8'), sha1)
        
        oauth_params['oauth_signature'] = b64encode(hashed.digest()).decode('utf-8')
        
        return OAuth10a._OAuthParamsToHeader(oauth_params)

def fn_register(oauth, config):

    if ('oauthCallback' not in config or config['oauthCallback'] != 'oob'):
        print('oauthCallback missing from config or not \'oob\'...')
        return -1

    site = config['url']
    oauth1_request_url   = site + '/oauth1/request'
    oauth1_authorize_url = site + '/oauth1/authorize'
    oauth1_access_url    = site + '/oauth1/access'
    
    
    c = pycurl.Curl()
    c.setopt(c.CAINFO, certifi.where())
    #c.setopt(c.VERBOSE, True)
    
    buffer = BytesIO()
    post_params = {}
    c.setopt(c.POST, True)
    c.setopt(c.URL, oauth1_request_url)
    c.setopt(c.WRITEDATA, buffer)
    c.setopt(c.HTTPHEADER, [oauth.getOAuthHeader('POST', oauth1_request_url, post_params, {'oauth_callback': config['oauthCallback']})])
    c.setopt(c.POSTFIELDS, '')
    c.perform()
    
    status = c.getinfo(c.RESPONSE_CODE)
    if (status != 200):
        print('Requesting Authorization failed...')
        return -1
    
    response = buffer.getvalue().decode('utf-8')
    params = parse_qs(response)
    if (not(all(e in params for e in ['oauth_token', 'oauth_token_secret']))):
        print('Authorization Response did not contain required token and secret.')
        return -2
    
    print('Please visit the following URL:\n'
          '\n' + 
          oauth1_authorize_url + '?' + response
          );
    
    oauthVerifier = input('Please insert verifier (or nothing to cancel):')
    
    if (oauthVerifier == ''):
        print('Authorization aborted...')
        return -3
    
    print('Verifier: ' + oauthVerifier)
    
    oauth.updateOAuthToken(params['oauth_token'][-1], params['oauth_token_secret'][-1])
    
    post_params = {}
    add_oauth_param = {
        'oauth_verifier': oauthVerifier,
        'oauth_callback': config['oauthCallback']
    }
    
    buffer = BytesIO()
    c.setopt(c.POST, True)
    c.setopt(c.URL, oauth1_access_url)
    c.setopt(c.WRITEDATA, buffer)
    c.setopt(c.HTTPHEADER, [oauth.getOAuthHeader('POST', oauth1_access_url, post_params, add_oauth_param)])
    c.setopt(c.POSTFIELDS, '')
    c.perform()
    
    status = c.getinfo(c.RESPONSE_CODE)
    if (status != 200):
        print('Accessing OAuth 1.0a failed...')
        return -4
    
    response = buffer.getvalue().decode('utf-8')
    params = parse_qs(response)
    if (not(all(e in params for e in ['oauth_token', 'oauth_token_secret']))):
        print('Authorization Response did not contain required token and secret.')
        return -5
    
    config['oauthToken'] = params['oauth_token'][-1]
    config['oauthTokenSecret'] = params['oauth_token_secret'][-1]
    
    print('Updated Config:')
    print('-' * 72)
    print(yaml.dump(config, default_flow_style=False))
    print('-' * 72)

    return 0

def fn_test(oauth, config):

    site = config['url']
    site_root = site + '/wp-json{0:s}'
    
    c = pycurl.Curl()
    buffer = BytesIO()
    url = site_root.format(categories_ep)
    c.setopt(c.URL, url)
    
    post_params = {}
    c.setopt(c.CAINFO, certifi.where())
    c.setopt(c.WRITEDATA, buffer)
    c.setopt(c.HTTPHEADER, [oauth.getOAuthHeader('GET', url, post_params)])
    c.perform()
 
    # HTTP response code, e.g. 200.
    status = c.getinfo(c.RESPONSE_CODE)
    if (status == 200):
        print('Erfolg!!!')
    print('Status: %d' % c.getinfo(c.RESPONSE_CODE))
    # Elapsed time for the transfer.
    print('Status: %f' % c.getinfo(c.TOTAL_TIME))
    
    print('-'*72)
    print(buffer.getvalue().decode('UTF-8'))
    print('-'*72)
    
    return 0
    
    print('-'*72)
    print('Creating Category \'Derp\'...')
    print('-'*72)
    
    json_data = {
        'name': 'Derp',
    }
    post_params = {}
    update_oauth_params(oauth_params)
    if ('oauth_signature' in oauth_params):
        del oauth_params['oauth_signature']
    oauth_params['oauth_signature'] = get_oauth_signature('POST', url, oauth_params, post_params, oauth_token_secret)
    buffer = BytesIO()
    c.setopt(c.URL, url)
    c.setopt(pycurl.VERBOSE, 1)
    c.setopt(c.WRITEDATA, buffer)
    c.setopt(c.HTTPHEADER, [get_oauth_header(oauth_params), 'Content-Type: application/json'])
    c.setopt(c.POSTFIELDS, json.dumps(json_data))
    c.perform()

    # HTTP response code, e.g. 200.
    status = c.getinfo(c.RESPONSE_CODE)
    if (status == 200):
        print('Erfolg!!!')
    print('Status: %d' % c.getinfo(c.RESPONSE_CODE))
    # Elapsed time for the transfer.
    print('Status: %f' % c.getinfo(c.TOTAL_TIME))
    
    print('-'*72)
    print(buffer.getvalue().decode('UTF-8'))
    print('-'*72)
    
    c.close()

def checkConfig(config):
    
    return all([k in config for k in ['url', 'consumerKey', 'consumerSecret']])
        
def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.yml')
    subparsers = parser.add_subparsers(title='command', dest='subcommand', help='sub-command')
    parser_register = subparsers.add_parser('register')
    parser_test = subparsers.add_parser('test')
    
    args = parser.parse_args()
    
    try:
        with open(args.config, 'r') as f:
            config = yaml.load(f)
    except Exception as e:
        print('Could not load configuration \'{0:s}\'...'.format(args.config))
        return -1
    
    if (not(checkConfig(config))):
        print('Configuration file invalid.')
        return -1

    oauth = OAuth10a(config['consumerKey'],
                     config['consumerSecret'],
                     config.get('oauthToken', None),
                     config.get('oauthTokenSecret', None)
                    )
    
    if (args.subcommand == 'register'):
        return fn_register(oauth, config)
    elif ( args.subcommand == 'test'):
        return fn_test(oauth, config)
    else:
        print('Unknown command \'{0:s}\'...'.format(args.subcommand))
        return -2
    
    return 0
    
if __name__ == '__main__':
    sys.exit(main())