import os, sys
import tempfile
import optparse
import datetime
import subprocess
import xml.etree.ElementTree

from urllib import urlopen
from Geohash import encode as geohash
from base64 import b64encode
from bencode import bencode

def main(gpg_command, gpg_key, way_id, tag_names):
    """
    """
    message = encode_way(way_id, tag_names)
    signature = sign_message(gpg_command, gpg_key, message)
    verified = verify_signature(gpg_command, message, signature)

    if not verified:
        print >> sys.stderr, 'Signature FAIL'
        return 1

    print '%sT%s' % (str(datetime.datetime.utcnow())[:10], str(datetime.datetime.utcnow())[11:19]),
    print gpg_key, 'way', way_id,
    print b64encode(signature), ' '.join(tag_names)
    
    return 0

def encode_way(way_id, tag_names):
    """ Given an OSM id for a way and a list of tag names, returns a signable encoding.
    """
    assert len([tag for tag in tag_names if ' ' in tag]) == 0, 'Expecting tag names with no white space'
    
    url = 'http://api.openstreetmap.org/api/0.6/way/%d' % way_id
    url = 'file:///Users/migurski/Sites/GOSM/way.xml'
    
    tree = xml.etree.ElementTree.parse(urlopen(url))
    
    tags = [(nd.attrib.get('k', None), nd.attrib.get('v', None))
            for nd in tree.getroot().find('way').findall('tag')]

    tags = dict(tags)
    tags = [(key, tags.get(key, '')) for key in tag_names]
    tags = dict(tags)

    node_ids = [nd.attrib.get('ref', False) for nd in tree.getroot().find('way').findall('nd')]
    url = 'http://api.openstreetmap.org/api/0.6/nodes?nodes=%s' % ','.join(node_ids)
    url = 'file:///Users/migurski/Sites/GOSM/nodes.xml'

    tree = xml.etree.ElementTree.parse(urlopen(url))
    
    nodes = ((nd.attrib.get('id', None), nd.attrib.get('lat', None), nd.attrib.get('lon', None))
             for nd in tree.getroot().findall('node'))

    nodes = [(node_id, geohash(float(lat), float(lon), 10)) for (node_id, lat, lon) in nodes]
    nodes = dict(nodes)
    nodes = [nodes[node_id] for node_id in node_ids]
    
    #nodes = [(i == 0 and node or offset(nodes[i - 1], node)) for (i, node) in enumerate(nodes)]

    data = [tags, nodes]
    message = bencode(data)

    print >> sys.stderr, data

    return message

def sign_message(gpg_command, gpg_key, message):
    """ Given a GnuPG command, key id and signable message, return a raw binary signature.
    """
    print >> sys.stderr, message
    
    handle, filename = tempfile.mkstemp(prefix='osm-', suffix='.ben')
    
    os.write(handle, message)
    os.close(handle)
    
    cmd = (gpg_command + ' --detach --sign').split() + (gpg_key and ['--local-user', gpg_key] or []) + [filename]
    gpg = subprocess.Popen(cmd, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
    gpg.wait()
    
    if gpg.returncode != 0:
        raise Exception('Expecting a successful signing')
    
    signature = open(filename + '.sig', 'r').read()
    
    print >> sys.stderr, b64encode(signature)
    
    os.unlink(filename)
    os.unlink(filename + '.sig')
    
    return signature

def verify_signature(gpg_command, message, signature):
    """ Given a GnuPG command, message and signature, return boolean verification of signature.
    """
    handle, filename_enc = tempfile.mkstemp(prefix='osm-', suffix='.ben')
    os.write(handle, message)
    
    handle, filename_sig = tempfile.mkstemp(prefix='osm-', suffix='.sig')
    os.write(handle, signature)
    
    cmd = (gpg_command + ' --verify').split()+ [filename_sig, filename_enc]
    gpg = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    gpg.wait()

    os.unlink(filename_sig)
    os.unlink(filename_enc)
    
    return (gpg.returncode == 0)

def offset(base, other):
    
    assert len(base) == len(other)
    
    while len(other) and base[0] == other[0]:
        base, other = base[1:], other[1:]

    return other

parser = optparse.OptionParser()
parser.set_defaults(gpg='gpg')

parser.add_option('-g', '--gpg', dest='gpg')
parser.add_option('-w', '--way', dest='way', type='int')
parser.add_option('-k', '--key', dest='key')

if __name__ == '__main__':
    options, args = parser.parse_args()
    sys.exit(main(options.gpg, options.key, options.way, args[:]))
