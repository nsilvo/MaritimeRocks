#!/usr/bin/env python3
import base64
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import scrypt  # PyCryptodome’s implementation

CRYPT_KEY = bytes([
    0x9c,0x93,0x5b,0x48,0x73,0x0a,0x55,0x4d,
    0x6b,0xfd,0x7c,0x63,0xc8,0x86,0xa9,0x2b,
    0xd3,0x90,0x19,0x8e,0xb8,0x12,0x8a,0xfb,
    0xf4,0xde,0x16,0x2b,0x8b,0x95,0xf6,0x38,
])

def unobsure(obs: str) -> bytes:
    data = base64.urlsafe_b64decode(obs + "==")
    iv, ct = data[:16], data[16:]
    cipher = AES.new(CRYPT_KEY, AES.MODE_CTR, nonce=b'', initial_value=iv)
    return cipher.decrypt(ct)

# ─── Edit these with your obscured values ─────────────────────────
obscured_password = "oGbM4viQ1px3t15_udUva-iWID0C3mFv-m-rEfSpDiig2jH9UcE"
obscured_salt     = "NmNs2016"
# ─────────────────────────────────────────────────────────────────

passphrase = unobsure(obscured_password)
salt       = unobsure(obscured_salt)

print("Passphrase:", passphrase.decode())
print("Salt      :", salt.decode())

# Use PyCryptodome’s scrypt to derive the same 32-byte key:
key = scrypt(
    passphrase,
    salt,
    key_len=32,
    N=262144,
    r=8,
    p=1
)

print("Encryption key (hex):", key.hex())
