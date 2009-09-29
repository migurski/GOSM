import os, sys
import csv
import httplib
import tempfile
import optparse
import datetime
import subprocess
import xml.etree.ElementTree
import xml.dom.minidom

from urllib import urlopen
from Geohash import encode as geohash
from base64 import b64encode
from bencode import bencode

def main(osm_user, osm_pass, gpg_command, gpg_key, way_ids, tag_names):
    """
    """
    out = csv.writer(sys.stdout, 'excel-tab')
    changeset = open_changeset(osm_user, osm_pass)
    
    for way_id in way_ids:
        message = encode_way(way_id, tag_names)
        signature = sign_message(gpg_command, gpg_key, message)
        verified = verify_signature(gpg_command, message, signature)

        if not verified:
            print >> sys.stderr, 'Signature FAIL'
    
        row = ['%sT%sZ' % (str(datetime.datetime.utcnow())[:10], str(datetime.datetime.utcnow())[11:19])]
        row += [gpg_key, 'way', way_id]
        row += [b64encode(signature), ' '.join(tag_names)]
        out.writerow(row)
    
        sign_way(osm_user, osm_pass, changeset, gpg_key, way_id, tag_names, signature)

    close_changeset(osm_user, osm_pass, changeset)
    
    return 0

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

def open_changeset(osm_user, osm_pass):
    """
    """
    doc = xml.dom.minidom.Document()

    changeset = xml.dom.minidom.Element('changeset')

    tag = xml.dom.minidom.Element('tag')
    tag.setAttribute('k', 'created_by')
    tag.setAttribute('v', 'GOSM')
    changeset.appendChild(tag)

    tag = xml.dom.minidom.Element('tag')
    tag.setAttribute('k', 'comment')
    tag.setAttribute('v', 'Putting a signature on a way')
    changeset.appendChild(tag)
    
    osm = xml.dom.minidom.Element('osm')
    osm.appendChild(changeset)
    doc.appendChild(osm)
    
    conn = httplib.HTTPConnection('api.openstreetmap.org', 80)
    conn.request('PUT', '/api/0.6/changeset/create', doc.toxml(), {'Authorization': 'Basic %s' % b64encode('%s:%s' % (osm_user, osm_pass))})
    res = conn.getresponse()
    
    if res.status != 200:
        raise Exception('%d: %s' % (res.status, res.read()))
    
    return res.read().strip()

def close_changeset(osm_user, osm_pass, changeset):
    """
    """
    conn = httplib.HTTPConnection('api.openstreetmap.org', 80)
    conn.request('PUT', '/api/0.6/changeset/%s/close' % changeset, '', {'Authorization': 'Basic %s' % b64encode('%s:%s' % (osm_user, osm_pass))})
    res = conn.getresponse()
    
    if res.status != 200:
        raise Exception('%d: %s' % (res.status, res.read()))

def sign_way(osm_user, osm_pass, changeset, gpg_key, way_id, tag_names, signature):
    """
    """
    url = 'http://api.openstreetmap.org/api/0.6/way/%d' % way_id
    doc = xml.dom.minidom.parse(urlopen(url))
    
    assert len(doc.getElementsByTagName('way')) == 1
    
    way = doc.getElementsByTagName('way')[0]
    way.setAttribute('changeset', changeset)
    
    tag_name = 'gosm:sig:%s' % gpg_key
    
    # remove existing signature
    for tag in way.getElementsByTagName('tag'):
        if tag.getAttribute('k') == tag_name:
            tag.parentNode.removeChild(tag)

    now = str(datetime.datetime.utcnow())
    tag = xml.dom.minidom.Element('tag')
    tag.setAttribute('k', tag_name)
    tag.setAttribute('v', '%s %s %sT%sZ' % (' '.join(tag_names), b64encode(signature), now[:10], now[11:19]))
    way.appendChild(tag)

    conn = httplib.HTTPConnection('api.openstreetmap.org', 80)
    conn.request('PUT', '/api/0.6/way/%d' % way_id, doc.toxml(), {'Authorization': 'Basic %s' % b64encode('%s:%s' % (osm_user, osm_pass))})
    res = conn.getresponse()
    
    if res.status != 200:
        raise Exception('%d: %s' % (res.status, res.read()))

    return True

def offset(base, other):
    
    assert len(base) == len(other)
    
    while len(other) and base[0] == other[0]:
        base, other = base[1:], other[1:]

    return other

parser = optparse.OptionParser(usage='%s [options] [list of way IDs]' % __file__)
parser.set_defaults(gpg='gpg')

parser.add_option('-g', '--gpg', dest='gpg', help='GPG command, may include additional options e.g.: "gpg --use-agent"')
parser.add_option('-k', '--key', dest='key', help='GPG key id')
parser.add_option('-t', '--tag-names', dest='tag_names', help='Comma-delimited list of tag names')
parser.add_option('-u', '--username', dest='username', help='OpenStreetMap account username')
parser.add_option('-p', '--password', dest='password', help='OpenStreetMap account password')

if __name__ == '__main__':
    options, args = parser.parse_args()
    sys.exit(main(options.username, options.password, options.gpg, options.key, map(int, args[:]), options.tag_names.split(',')))
