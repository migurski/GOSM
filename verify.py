import os, sys
import tempfile
import optparse
import subprocess
import xml.etree.ElementTree

from urllib import urlopen
from Geohash import encode as geohash
from base64 import b64encode, b64decode
from bencode import bencode

def main(gpg_command, gpg_key, way_ids):
    """
    """
    for way_id in way_ids:
        signature, tag_names = way_signature(way_id, gpg_key)
        
        if signature:
            message = encode_way(way_id, tag_names)
            verified = verify_signature(gpg_command, message, signature)

            if verified:
                print >> sys.stderr, 'Signature OK on', way_id
            else:
                print >> sys.stderr, 'Signature FAIL on', way_id
        else:
            print >> sys.stderr, 'No signature on', way_id
    
    return 0

def way_signature(way_id, gpg_key):
    """ Given an OSM id for a way and a key id, return the signature and list of tag names if it exists.
    """
    url = 'http://api.openstreetmap.org/api/0.6/way/%d' % way_id
    
    tree = xml.etree.ElementTree.parse(urlopen(url))
    
    tag_name = 'gosm:sig:%s' % gpg_key
    
    for tag in tree.getroot().find('way').findall('tag'):
        if tag.attrib.get('k') == tag_name:
            tag_value = tag.attrib.get('v').split()
            tag_names, signature, date_time = tag_value[:-2], b64decode(tag_value[-2]), tag_value[-1]
            return signature, tag_names
    
    return None, []

def encode_way(way_id, tag_names):
    """ Given an OSM id for a way and a list of tag names, returns a signable encoding.
    """
    assert len([tag for tag in tag_names if ' ' in tag]) == 0, 'Expecting tag names with no white space'
    
    url = 'file:///Users/migurski/Sites/GOSM/way.xml'
    url = 'http://api.openstreetmap.org/api/0.6/way/%d' % way_id
    
    tree = xml.etree.ElementTree.parse(urlopen(url))
    
    tags = [(nd.attrib.get('k', None), nd.attrib.get('v', None))
            for nd in tree.getroot().find('way').findall('tag')]

    tags = dict(tags)
    tags = [(key, tags.get(key, '')) for key in tag_names]
    tags = dict(tags)

    node_ids = [nd.attrib.get('ref', False) for nd in tree.getroot().find('way').findall('nd')]
    url = 'file:///Users/migurski/Sites/GOSM/nodes.xml'
    url = 'http://api.openstreetmap.org/api/0.6/nodes?nodes=%s' % ','.join(node_ids)

    tree = xml.etree.ElementTree.parse(urlopen(url))
    
    nodes = ((nd.attrib.get('id', None), nd.attrib.get('lat', None), nd.attrib.get('lon', None))
             for nd in tree.getroot().findall('node'))

    nodes = [(node_id, geohash(float(lat), float(lon), 10)) for (node_id, lat, lon) in nodes]
    nodes = dict(nodes)
    nodes = [nodes[node_id] for node_id in node_ids]
    
    ## keep just the offsets which doesn't make much sense in this context
    #nodes = [(i == 0 and node or offset(nodes[i - 1], node)) for (i, node) in enumerate(nodes)]

    data = [tags, nodes]
    message = bencode(data)

    return message

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

parser = optparse.OptionParser(usage='%s [options] [list of way IDs]' % __file__)
parser.set_defaults(gpg='gpg')

parser.add_option('-g', '--gpg', dest='gpg', help='GPG command, may include additional options e.g.: "gpg --use-agent"')
parser.add_option('-k', '--key', dest='key', help='GPG key id')

if __name__ == '__main__':
    options, args = parser.parse_args()
    sys.exit(main(options.gpg, options.key, map(int, args[:])))
