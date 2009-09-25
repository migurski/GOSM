import os, sys
import urllib
import base64
import tempfile
import subprocess

gpg_command = 'gpg --use-agent'

if __name__ == '__main__':
    
    url = 'http://api.openstreetmap.org/api/0.6/%s/%s' % tuple(sys.argv[1:3])
    
    print url
    
    handle, filename = tempfile.mkstemp(dir='/tmp', prefix='osm-', suffix='.xml')
    
    os.write(handle, urllib.urlopen(url).read())
    os.close(handle)
    
    print filename
    
    cmd = (gpg_command + ' --detach --sign').split()+ [filename]
    gpg = subprocess.Popen(cmd, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
    
    gpg.wait()
    
    print filename + '.sig'
    
    signature = open(filename + '.sig', 'r').read()
    
    print base64.b64encode(signature)
    
    os.unlink(filename)
    os.unlink(filename + '.sig')
