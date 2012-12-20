#!/usr/bin/python

from Crypto.Cipher import ARC4
import collections
import md5
import string, subprocess, time
import struct
import types
from optparse import OptionParser

class NoEncryptionError(Exception):
  pass

class PDFCracker:
  padding_string = "\x28\xBF\x4E\x5E\x4E\x75\x8A\x41" \
		   "\x64\x00\x4E\x56\xFF\xFA\x01\x08" \
		   "\x2E\x2E\x00\xB6\xD0\x68\x3E\x80" \
		   "\x2F\x0C\xA9\xFE\x64\x53\x69\x7A"

  def prep_password(self, password):
    if len(password) < 32:
      return password + self.padding_string[:32-len(password)]
    else:
      return password[:32]

  def trunc_to_keylen(self, digest):
    if self.R == 2:
      return digest[:5]
    else: # R == 3
      return digest[:(self.Length/8)]

  def repeat_md5(self, digest):
    for i in xrange(50):
      digest = md5.new(digest).digest()
    return digest

  def compute_encryption_key(self, password):
    m = md5.new()
    m.update(self.prep_password(password))
    m.update(self.O)
    m.update(struct.pack("<i",self.P)) 
    m.update(self.FileID) 
    digest = m.digest()
    if self.R == 3:
      digest = self.repeat_md5(digest)		
    return self.trunc_to_keylen(digest)

  def rc4_encrypt(self, enc, key):
    if self.R == 3:
      times = 20
    else:
      times = 1

    for i in xrange(times):
      new_key = "".join([chr(c) for c in map(lambda byte: ord(byte) ^ i, key)])
      assert len(new_key) == len(key)
      enc = ARC4.new(new_key).encrypt(enc)
    return enc

  def rc4_decrypt(self, enc, key):
    if self.R == 3:
      times = 20
    else:
      times = 1

    for i in xrange(times):
      new_key = "".join([chr(c) for c in map(lambda byte: ord(byte) ^ (times - 1 - i), key)])
      enc = ARC4.new(new_key).encrypt(enc)
    return enc		

  def compute_O_key(self, upass, opass):
    m = md5.new()
    if opass == "":
      m.update(self.prep_password(upass))
    else:
      m.update(self.prep_password(opass))
    digest = m.digest()

    if self.R == 3:
      digest = self.repeat_md5(digest)

    return self.trunc_to_keylen(digest)

  def compute_O(self, upass, opass):
    key = self.compute_O_key(upass, opass) 
    enc = self.rc4_encrypt(self.prep_password(upass), key)
    return enc

  def compute_U(self, password):
    key = self.compute_encryption_key(password)
    if self.R == 2:
      return rc4.encrypt(self.padding_string, key)

    m = md5.new()
    m.update(self.padding_string)
    m.update(self.FileID)

    enc = self.rc4_encrypt(m.digest(), key)

    # This padding is actually arbitrary
    enc = enc + self.padding_string[:16]
    return enc

  def auth_user(self, password):
    maybe_U = self.compute_U(password)	

    if self.R == 3:
      return maybe_U[:16] == self.U[:16]
    else:
      return maybe_U == self.U

  def auth_owner(self, password):
    assert len(password) > 0
    key = self.compute_O_key("", password)
    maybe_upass = self.rc4_decrypt(self.O, key)
    return self.auth_user(maybe_upass)
 
  def __init__(self, filename):
    def parse_int(line):
      return int(line[string.find(line, ":")+2:].strip())

    def parse_hex_string(line):
      return line[string.find(line, ":")+2:].strip().decode("hex")

    p = subprocess.Popen(["pdfcrack", filename, "--minpw=2", "--maxpw=1"],
                	 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    warning_line = p.stdout.readline()
    try:
      version_line = p.stdout.readline()
      handler_line = p.stdout.readline()
      self.V = parse_int(p.stdout.readline())
      self.R = parse_int(p.stdout.readline())
      self.P = parse_int(p.stdout.readline())
      self.Length = parse_int(p.stdout.readline())
      enc_meta_line = p.stdout.readline()
      self.FileID = parse_hex_string(p.stdout.readline())
      self.U = parse_hex_string(p.stdout.readline())
      self.O = parse_hex_string(p.stdout.readline())
      p.kill()
    except:
      print warning_line
      raise NoEncryptionError

if __name__ == "__main__":
  parser = OptionParser()
  parser.add_option("-i", "--input", dest="input_filename", default="file.pdf")
  parser.add_option("-u", "--user-password", dest="upass", default="")
  parser.add_option("-o", "--owner-password", dest="opass", default="")
  (options, args) = parser.parse_args()

  try:
    c = PDFCracker(options.input_filename)
  except NoEncryptionError:
    exit(-1)

  if c.auth_user(options.upass):
    print "User pass is: " + options.upass
  if c.auth_owner(options.opass):
    print "Owner pass is: " + options.opass

