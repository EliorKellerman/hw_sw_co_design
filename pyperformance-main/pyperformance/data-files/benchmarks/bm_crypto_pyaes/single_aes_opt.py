#!/usr/bin/env python
"""
Pure-Python Implementation of the AES block-cipher.

Benchmark AES in CTR mode using the pyaes module.
"""

import pyaes_opt as pyaes

# 23,000 bytes
CLEARTEXT = b"This is a test. What could possibly go wrong? " * 500

# 128-bit key (16 bytes)
KEY = b'\xa1\xf6%\x8c\x87}_\xcd\x89dHE8\xbf\xc9,'


def bench_pyaes(loops):
    aes = pyaes.AESModeOfOperationCTR(KEY)
    ciphertext = aes.encrypt(CLEARTEXT)

    # need to reset IV for decryption
    aes = pyaes.AESModeOfOperationCTR(KEY)
    plaintext = aes.decrypt(ciphertext)

    # explicitly destroy the pyaes object
    aes = None
    if plaintext != CLEARTEXT:
        raise Exception("decrypt error!")


if __name__ == "__main__":
    bench_pyaes(1)
