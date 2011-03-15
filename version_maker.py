#!/usr/bin/env python
import os, datetime

def writeVersionFile(vn_major, vn_minor, vn_ts=None):
	if vn_ts == None:
		n = datetime.datetime.now()
		d = int(n.strftime("%j"))
		if d < 10: 
			d = '00'+str(d)
		elif d < 100:
			d = '0'+str(d)
		else:
			d = str(d)
		vn_ts = str(n.year)[2:] + d

	v_filename = 'version.py'
	if os.path.exists(v_filename): os.remove(v_filename)
	f = open(v_filename,'w')
	f.write('version_str = "%s.%s"\n' % (str(vn_major), str(vn_minor)))
	f.write('version_build = "%s"\n' % (vn_ts,))
	f.close()
