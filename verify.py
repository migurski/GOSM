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
import sys
import optparse
import GOSM

def main(gpg_command, gpg_key, way_ids):
    """
    """
    for way_id in way_ids:
        signature, tag_names = GOSM.way_signature(way_id, gpg_key)
        
        if signature:
            message = GOSM.encode_way(way_id, tag_names)
            verified = GOSM.verify_signature(gpg_command, message, signature)

            if verified:
                print >> sys.stderr, 'Signature OK on', way_id
            else:
                print >> sys.stderr, 'Signature FAIL on', way_id
        else:
            print >> sys.stderr, 'No signature on', way_id
    
    return 0

parser = optparse.OptionParser(usage='%s [options] [list of way IDs]' % __file__)
parser.set_defaults(gpg='gpg')

parser.add_option('-g', '--gpg', dest='gpg', help='GPG command, may include additional options e.g.: "gpg --use-agent"')
parser.add_option('-k', '--key', dest='key', help='GPG key id')

if __name__ == '__main__':
    options, args = parser.parse_args()
    sys.exit(main(options.gpg, options.key, map(int, args[:])))
