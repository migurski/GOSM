import os, sys
import tempfile
import optparse
import subprocess
import xml.etree.ElementTree

from urllib import urlopen
from Geohash import encode as geohash
from base64 import b64encode
from bencode import bencode 

def encode_way(way_id, tag_names):
    """
    """
    url = 'http://api.openstreetmap.org/api/0.6/way/%d' % way_id
    url = 'file:///Users/migurski/Sites/GOSM/way.xml'
    
    tree = xml.etree.ElementTree.parse(urlopen(url))
    
    tags = [(nd.attrib.get('k', None), nd.attrib.get('v', None))
            for nd in tree.getroot().find('way').findall('tag')]

    tags = dict(tags)
    tags = [(key, tags.get(key, '')) for key in tag_names]
    tags = dict(tags)

    node_ids = [nd.attrib.get('ref', '') for nd in tree.getroot().find('way').findall('nd')]
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
    
    message = encode_way(options.way, args[:])
    
    print message
    
    handle, filename = tempfile.mkstemp(dir='/tmp', prefix='osm-', suffix='.ben')
    
    os.write(handle, message)
    os.close(handle)
    
    cmd = (options.gpg + ' --detach --sign --local-user ' + options.key).split() + [filename]
    gpg = subprocess.Popen(cmd, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
    gpg.wait()
    
    signature = open(filename + '.sig', 'r').read()
    
    print b64encode(signature)
    
    cmd = (options.gpg + ' --verify').split()+ [filename + '.sig']
    gpg = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    gpg.wait()
    
    if gpg.returncode == 0:
        print 'Signature checks out'
    else:
        print 'Signature FAIL'

    os.unlink(filename)
    os.unlink(filename + '.sig')
