from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA
import base64
import os
import tempfile

# This is the old method


def sign_content(content_data):
    dirname = os.path.dirname(__file__)
    print (dirname)
    with open(os.path.join(dirname, 'private.pem'), 'r') as reader:
        rsa_private_key = RSA.importKey(reader.read(), "CHAVEPRIVADA")
        signer = PKCS1_v1_5.new(rsa_private_key)
        digest = SHA.new()
        digest.update(content_data.encode('utf-8'))
        sign = signer.sign(digest)
        res = base64.b64encode(sign)
        res = str(res)
    return res[2:-1] + ';1'
