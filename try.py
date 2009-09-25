import os, sys
import urllib
import base64
import bencode
import Geohash
import tempfile
import subprocess
import xml.etree.ElementTree

gpg_command = 'gpg --use-agent'

if __name__ == '__main__':
    
    url = 'http://api.openstreetmap.org/api/0.6/%s/%s' % tuple(sys.argv[1:3])
    key = sys.argv[3]
    
    print url, key
    
    handle, filename = tempfile.mkstemp(dir='/tmp', prefix='osm-', suffix='.xml')
    
    os.write(handle, urllib.urlopen(url).read())
    os.close(handle)
    
    print filename
    
    tree = xml.etree.ElementTree.parse(filename)
    node_ids = [nd.attrib.get('ref', '') for nd in tree.getroot().find('way').findall('nd')]
    url = 'http://api.openstreetmap.org/api/0.6/nodes?nodes=%s' % ','.join(node_ids)

    tree = xml.etree.ElementTree.fromstring(urllib.urlopen(url).read())
    print tree
    
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
