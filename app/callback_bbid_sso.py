import calendar
import json
import os
import time
import urllib
import hashlib
from datetime import datetime
from datetime import timedelta
from urllib2 import urlopen

import jose
import requests
from flask import redirect
from flask import render_template
from flask import request
from jose import jws
from jose import jwt
from requests.auth import HTTPBasicAuth

from app import app



allowed_issuers = []
# NOTE: We should consider having LRU/MRU config here
# OR!
# http://pythonhosted.org/cachetools/#memoizing-decorators
public_key_cache = {}

config = None
bbid_config = None
with open('.okta.config.json') as config_file:
    config_json = json.load(config_file)
    config = config_json['okta']
    bbid_config = config_json['bbid']

# Get allowed issuer from the OKTA_ALLOWED_ISSUER environment variable,
# use the 'oktaUrl' from our config file if that doesn't exist
allowed_issuer = os.getenv('OKTA_ALLOWED_ISSUER', config['oidc']['oktaUrl'])
allowed_issuers.append(allowed_issuer)


def fetch_jwk_for(id_token=None):
    if id_token is None:
        raise NameError('id_token is required')

    # FIXME: Make sure TLS layer is configured
    # START FIXME
    #     The generator should support auto-discovery
    # clean_iss = None
    # dirty_iss = jwt.get_unverified_claims(id_token).get('iss')
    # if dirty_iss in allowed_issuers:
    #     clean_iss = dirty_iss
    # oidc_discovery_url = "{}/.well-known/openid-configuration".format(
    #     clean_iss)
    # r = requests.get(oidc_discovery_url)
    # openid_configuration = r.json()
    # if 'jwks_uri' in openid_configuration:
    #     jwks_uri = openid_configuration['jwks_uri']
    jwks_uri = "{}/oauth2/v1/keys".format(config['oidc']['oktaUrl'])
    # END FIXME

    unverified_header = jws.get_unverified_header(id_token)
    key_id = None
    if 'kid' in unverified_header:
        key_id = unverified_header['kid']
    else:
        raise ValueError('The id_token header must contain a "kid"')
    if key_id in public_key_cache:
        return public_key_cache[key_id]

    # FIXME: Make sure that we rate-limit outbound requests
    # (Karl used bucket rate limiting here "leaky bucket")
    r = requests.get(jwks_uri)
    jwks = r.json()
    for key in jwks['keys']:
        jwk_id = key['kid']
        public_key_cache[jwk_id] = key

    if key_id in public_key_cache:
        return public_key_cache[key_id]
    else:
        raise RuntimeError("Unable to fetch public key from jwks_uri")


@app.route("/")
def login():
    return render_template('index.html', config=config)


@app.route("/authorization-code/callback")
def callback():
    nonce = None
    state = None

    cookies = request.cookies
    if (('okta-oauth-nonce' in cookies) and ('okta-oauth-state' in cookies)):
        nonce = cookies['okta-oauth-nonce']
        state = cookies['okta-oauth-state']
        print('nonce: {}'.format(nonce))
        print('state: {}'.format(state))
    else:
        return "invalid nonce or state", 401

    if (request.args.get('state') != state):
        err = "'{}' != '{}'".format(
            request.args.get('state'),
            state)
        return "invalid state: {}".format(err), 401

    if 'code' not in request.args:
        return "no code in request arguments", 401

    auth = HTTPBasicAuth(config['oidc']['clientId'],
                         config['oidc']['clientSecret'])
    querystring = {
        'grant_type': 'authorization_code',
        'code': request.args.get('code'),
        'redirect_uri': config['oidc']['redirectUri']
    }
    qs = "grant_type=authorization_code&code={}&redirect_uri={}".format(
        urllib.quote_plus(querystring['code']),
        urllib.quote_plus(querystring['redirect_uri'])
    )
    url = "{}/oauth2/v1/token?{}".format(config['oidc']['oktaUrl'], qs)

    headers = {
        'User-Agent': None,
        'Connection': 'close',
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    r = requests.post(url,
                      # params=querystring,
                      stream=False,
                      auth=auth,
                      headers=headers)
    return_value = r.json()

    if 'id_token' not in return_value:
        return "no id_token in response from /token endpoint", 401
    id_token = return_value['id_token']

    # FIXME: This code should be factored out
    #        so it can be shared across bearer flow and OAuth flows.
    five_minutes_in_seconds = 300
    leeway = five_minutes_in_seconds
    jwt_kwargs = {
        # FIXME: This should be whitelisted?
        # Fixme: However, if we add whitelist,
        #        consider that algos could be swapped
        #        and HMAC'ed with the public key (WOW!)
        'algorithms': 'RS256',
        'options': {
            # FIXME: Remove when mock server returns valid access_tokens
            'verify_at_hash': False,
            # Used for leeway on the "exp" claim
            'leeway': leeway
        },
        'issuer': config['oidc']['oktaUrl'],
        'audience': config['oidc']['clientId']
    }
    if 'access_token' in return_value:
        jwt_kwargs['access_token'] = return_value['access_token']
    try:
        jwks_with_public_key = fetch_jwk_for(id_token)
        claims = jwt.decode(
            id_token,
            jwks_with_public_key,
            **jwt_kwargs)
    # FIXME: Do what Karl does: https://git.io/v1D8S
    # 401/403 per spec
    # Only when bearer token is used: https://tools.ietf.org/html/rfc6750
    # NOTE: For production systems,
    #       these errors should be opaque and logged rather than returned.
    except (jose.exceptions.JWTClaimsError,
            jose.exceptions.JWTError,
            jose.exceptions.JWSError,
            jose.exceptions.ExpiredSignatureError,
            NameError,
            ValueError), err:
        return str(err), 401

    if nonce != claims['nonce']:
        return "invalid nonce", 401

    # Validate 'iat' claim
    # FIXME: Open PR for moving this code here: https://git.io/v1D8M
    time_now_with_leeway = datetime.utcnow() + timedelta(seconds=leeway)
    acceptable_iat = calendar.timegm((time_now_with_leeway).timetuple())
    if 'iat' in claims and claims['iat'] > acceptable_iat:
        return "invalid iat claim", 401

    username = claims['preferred_username']

    my_ip = urlopen('http://ip.42.pl/raw').read()

    BBID_SHARED_KEY = bbid_config['sharedKey']
    clock_skew = 0
    if bbid_config['clockSkew']:
        clock_skew = int(bbid_config['clockSkew'])
    current_epoch = '{}'.format(int(time.time()) + clock_skew)


    hashString = BBID_SHARED_KEY + username + current_epoch
    print('hashString = {}'.format(hashString))

    m = hashlib.md5()
    m.update(hashString)
    mvalue = m.hexdigest()

    page = 'https://community.elca.org/page.aspx?pid=226'
    url = '{}&u={}&t={}&m={}'.format(page, username, current_epoch, mvalue)
    print('url = {}'.format(url))

    return redirect(url)


