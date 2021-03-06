"""
    GOSM (OpenStreetMap Genuine Advantage)
    Copyright (C) 2009 Michal Migurski <mike@stamen.com>

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along
    with this program; if not, write to the Free Software Foundation, Inc.,
    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""
import os, sys
import httplib
import tempfile
import datetime
import subprocess
import xml.dom.minidom
import xml.etree.ElementTree

from urllib import urlopen
from Geohash import encode as geohash
from base64 import b64encode, b64decode
from bencode import bencode

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
