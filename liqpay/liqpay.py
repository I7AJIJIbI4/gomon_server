# liqpay.py — LiqPay API core
# Python 3.6 compatible (no f-strings with complex expressions, no walrus)

import hashlib
import base64
import json
import hmac

try:
    from urllib.request import urlopen, Request
    from urllib.parse import urlencode
except ImportError:
    from urllib2 import urlopen, Request
    from urllib import urlencode

CHECKOUT_URL = 'https://www.liqpay.ua/api/3/checkout'
API_URL      = 'https://www.liqpay.ua/api/request'


class LiqPay(object):

    def __init__(self, public_key, private_key):
        self.public_key  = public_key
        self.private_key = private_key

    def _encode(self, params):
        return base64.b64encode(
            json.dumps(params).encode('utf-8')
        ).decode('utf-8')

    def _signature(self, data):
        raw = self.private_key + data + self.private_key
        sha1 = hashlib.sha1(raw.encode('utf-8')).digest()
        return base64.b64encode(sha1).decode('utf-8')

    def verify_signature(self, data, signature):
        expected = self._signature(data)
        return hmac.compare_digest(str(expected), str(signature))

    def decode_data(self, data):
        return json.loads(base64.b64decode(data).decode('utf-8'))

    def create_payment_url(self, order_id, amount, description,
                           server_url='', result_url='', currency='UAH', language='uk'):
        params = {
            'action':      'pay',
            'version':     3,
            'public_key':  self.public_key,
            'amount':      amount,
            'currency':    currency,
            'description': description,
            'order_id':    order_id,
            'language':    language,
        }
        if server_url:
            params['server_url'] = server_url
        if result_url:
            params['result_url'] = result_url

        data = self._encode(params)
        sig  = self._signature(data)
        return '{}?data={}&signature={}'.format(CHECKOUT_URL, data, sig)

    def api_request(self, params):
        params['public_key'] = self.public_key
        data = self._encode(params)
        sig  = self._signature(data)

        body = urlencode({'data': data, 'signature': sig}).encode('utf-8')
        req  = Request(API_URL, body)
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        resp = urlopen(req, timeout=30)
        return json.loads(resp.read().decode('utf-8'))

    def get_status(self, order_id):
        return self.api_request({'action': 'status', 'version': 3, 'order_id': order_id})

    def refund(self, order_id, amount=None):
        params = {'action': 'refund', 'version': 3, 'order_id': order_id}
        if amount is not None:
            params['amount'] = amount
        return self.api_request(params)
