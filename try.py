import os, sys
import urllib
import base64
import bencode
import Geohash
import tempfile
import subprocess
import xml.etree.ElementTree

gpg_command = 'gpg --use-agent'

def offset(base, other):
    
    assert len(base) == len(other)
    
    while len(other) and base[0] == other[0]:
        base, other = base[1:], other[1:]

    return other

if __name__ == '__main__':
    
    url = 'file:///Users/migurski/Sites/GOSM/%s-%s.xml' % tuple(sys.argv[1:3])
    url = 'http://api.openstreetmap.org/api/0.6/%s/%s' % tuple(sys.argv[1:3])
    key = sys.argv[3]
    tag_names = sys.argv[4:]
    
    print url, key
    
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
    
    cmd = (gpg_command + ' --detach --sign --local-user ' + key).split() + [filename]
    print cmd
    gpg = subprocess.Popen(cmd, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
    gpg.wait()
    
    print filename + '.sig'
    
    signature = open(filename + '.sig', 'r').read()
    
    print base64.b64encode(signature)
    
    cmd = (gpg_command + ' --verify').split()+ [filename + '.sig']
    gpg = subprocess.Popen(cmd, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
    gpg.wait()

    os.unlink(filename)
    os.unlink(filename + '.sig')
