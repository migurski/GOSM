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
import csv
import datetime
import optparse
import GOSM

from base64 import b64encode

def main(osm_user, osm_pass, gpg_command, gpg_key, way_ids, tag_names):
    """
    """
    out = csv.writer(sys.stdout, 'excel-tab')
    changeset = GOSM.open_changeset(osm_user, osm_pass)
    
    for way_id in way_ids:
        message = GOSM.encode_way(way_id, tag_names)
        signature = GOSM.sign_message(gpg_command, gpg_key, message)
        verified = GOSM.verify_signature(gpg_command, message, signature)

        if not verified:
            print >> sys.stderr, 'Signature FAIL'
    
        row = ['%sT%sZ' % (str(datetime.datetime.utcnow())[:10], str(datetime.datetime.utcnow())[11:19])]
        row += [gpg_key, 'way', way_id]
        row += [b64encode(signature), ' '.join(tag_names)]
        out.writerow(row)
    
        GOSM.sign_way(osm_user, osm_pass, changeset, gpg_key, way_id, tag_names, signature)

    GOSM.close_changeset(osm_user, osm_pass, changeset)
    
    return 0

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
