"""Versioned authenticated streaming backup encryption; never restore a partial output."""
import argparse
import base64
import os
import struct
import sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC=b'SGANCIA-BACKUP-1\n'
CHUNK=1024*1024


def read_exact(stream,n):
    data=bytearray()
    while len(data)<n:
        part=stream.read(n-len(data))
        if not part: raise ValueError('Backup incompleto')
        data.extend(part)
    return bytes(data)


def encrypt(source,target,key):
    cipher=AESGCM(key)
    prefix=os.urandom(8)
    target.write(MAGIC+prefix)
    counter=0
    while True:
        chunk=source.read(CHUNK)
        payload=(b'\x01'+chunk) if chunk else b'\x00'
        seq=counter.to_bytes(4,'big')
        encrypted=cipher.encrypt(prefix+seq,payload,MAGIC+prefix+seq)
        target.write(struct.pack('>I',len(encrypted))+encrypted)
        counter+=1
        if not chunk: break


def decrypt(source,target,key):
    if read_exact(source,len(MAGIC))!=MAGIC: raise ValueError('Formato backup non supportato')
    prefix=read_exact(source,8)
    cipher=AESGCM(key)
    counter=0
    while True:
        length=struct.unpack('>I',read_exact(source,4))[0]
        if not 17<=length<=CHUNK+17: raise ValueError('Record backup non valido')
        seq=counter.to_bytes(4,'big')
        payload=cipher.decrypt(prefix+seq,read_exact(source,length),MAGIC+prefix+seq)
        counter+=1
        if payload==b'\x00':
            if source.read(1): raise ValueError('Dati inattesi dopo la fine del backup')
            break
        if payload[:1]!=b'\x01' or len(payload)==1: raise ValueError('Record backup non valido')
        target.write(payload[1:])


def main():
    parser=argparse.ArgumentParser(description='Cifratura backup Sgancia')
    parser.add_argument('command',choices=['key','encrypt','decrypt'])
    args=parser.parse_args()
    if args.command=='key':
        print(base64.urlsafe_b64encode(os.urandom(32)).decode());return
    try:
        key=base64.b64decode(os.environ.get('SGANCIA_BACKUP_KEY',''),altchars=b'-_',validate=True)
        if len(key)!=32: raise ValueError('Chiave backup non configurata')
        (encrypt if args.command=='encrypt' else decrypt)(sys.stdin.buffer,sys.stdout.buffer,key)
    except Exception:
        print('Backup fallito: chiave errata, dati alterati/incompleti o errore di lettura/scrittura.',file=sys.stderr)
        raise SystemExit(1) from None


if __name__=='__main__':main()
