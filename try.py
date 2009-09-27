import os, sys
import urllib
import base64
import bencode
import Geohash
import tempfile
import optparse
import subprocess
import xml.etree.ElementTree

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
    
    url = 'http://api.openstreetmap.org/api/0.6/way/%d' % options.way
    tag_names = args[:]
    
    print url, options.key, tag_names
    
    tree = xml.etree.ElementTree.parse(urllib.urlopen(url))
    
    tags = ((nd.attrib.get('k', None), nd.attrib.get('v', None))
            for nd in tree.getroot().find('way').findall('tag'))

    tags = ((key, value) for (key, value) in tags if key in tag_names)
    tags = dict(list(tags))

    node_ids = [nd.attrib.get('ref', '') for nd in tree.getroot().find('way').findall('nd')]
    url = 'http://api.openstreetmap.org/api/0.6/nodes?nodes=%s' % ','.join(node_ids)

    tree = xml.etree.ElementTree.parse(urllib.urlopen(url))
    
    nodes = ((nd.attrib.get('id', None), nd.attrib.get('lat', None), nd.attrib.get('lon', None))
             for nd in tree.getroot().findall('node'))

    nodes = ((node_id, Geohash.encode(float(lat), float(lon), 10)) for (node_id, lat, lon) in nodes)
    nodes = dict(list(nodes))
    nodes = [nodes[node_id] for node_id in node_ids]
    
    #nodes = [(i == 0 and node or offset(nodes[i - 1], node)) for (i, node) in enumerate(nodes)]

    data = [tags, nodes]
    message = bencode.bencode(data)

    print data
    print message
    
    handle, filename = tempfile.mkstemp(dir='/tmp', prefix='osm-', suffix='.ben')
    
    os.write(handle, message)
    os.close(handle)
    
    print filename
    
    cmd = (options.gpg + ' --detach --sign --local-user ' + options.key).split() + [filename]
    print cmd
    gpg = subprocess.Popen(cmd, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
    gpg.wait()
    
    print filename + '.sig'
    
    signature = open(filename + '.sig', 'r').read()
    
    print base64.b64encode(signature)
    
    cmd = (options.gpg + ' --verify').split()+ [filename + '.sig']
    gpg = subprocess.Popen(cmd, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
    gpg.wait()

    os.unlink(filename)
    os.unlink(filename + '.sig')
