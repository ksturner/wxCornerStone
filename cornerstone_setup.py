#!/usr/bin/env python
from distutils.core import setup
import sys, os, version_maker 

v = [ 0, 8 ]
version_maker.writeVersionFile(v[0],v[1])


if sys.platform == 'darwin':
	import py2app
	setup(
		name="CornerStone",
		app=['main.py'],
		options=dict(py2app=dict(argv_emulation=0,optimize=2,iconfile='i/logo01.icns',)),
	)
	os.system('bash cornerstone_setup_darwin.sh')	

elif sys.platform.startswith('linux'):
	pyinstaller_dir = "/home/kevin/src/python/3rd-python/pyinstaller-1.3"
	pyinstaller_shellscript = "/cornerstone.sh"
	pyinstaller_specdir = "/cornerstone"
	pyinstaller_specfile = "/cornerstone.spec"

	shellscript_path = pyinstaller_dir + pyinstaller_shellscript
	specdir_path = pyinstaller_dir + pyinstaller_specdir 
	specfile_path = specdir_path + pyinstaller_specfile

	shellscript_lines = [ 
		'#!/bin/bash',
		'python %s/Configure.py' % (pyinstaller_dir,),
		'#python %s/Makespec.py -F "%s/cornerstone.py"' % (pyinstaller_dir, os.getcwd(),),
		'python %s/Build.py %s' % (pyinstaller_dir, specfile_path,),
		'cp %s/cornerstone %s/.' % (specdir_path, os.getcwd()),
	]
	spec_lines = [
		"""a = Analysis([os.path.join(HOMEPATH,'support/_mountzlib.py'), os.path.join(HOMEPATH,'support/useUnicode.py'), '%s/cornerstone.py'],""" % (os.getcwd()),
		"""pathex=['%s'])""" % (pyinstaller_dir,),
		"""pyz = PYZ(a.pure)""",
		"""exe = EXE( pyz,""",
		"""a.scripts,""",
		"""a.binaries,""",
		"""name='cornerstone',""",
		"""debug=False,""",
		"""strip=True,""",
		"""upx=True,""",
		"""console=1 )""",
	]

	if os.path.exists(pyinstaller_dir):
		# Write the shell script
		print "Writing the shell script...",
		if os.path.exists(shellscript_path): os.remove(shellscript_path)
		f = open(shellscript_path, 'w')
		f.write('\n'.join(shellscript_lines))
		f.close()
		print "done."

		# Create the folder for the spec file
		print "Creating the spec folder...",
		if not os.path.exists(specdir_path): os.mkdir(specdir_path)
		print "done."

		# Write the spec file
		print "Creating the spec file...",
		if os.path.exists(specfile_path): os.remove(specfile_path)
		f = open(specfile_path, 'w')
		f.write('\n'.join(spec_lines))
		f.close()
		print "done."

		# Run the shell script
		print "Executing the PyInstaller CornerStone shell script...",
		os.system('bash ' + shellscript_path)
		print "done."
	else:
		print "%s doesn't exist." % (pyinstaller_dir)

	# write the pyinstaller spec file
	f = open(pyinstaller_dir + pyinstaller_specdir + pyinstaller_specfile, 'w')
	f.close()
	
elif sys.platform.startswith('win'):
	import py2exe 
	manifest = """
	<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
	<assembly xmlns="urn:schemas-microsoft-com:asm.v1"
	manifestVersion="1.0">
	<assemblyIdentity
		version="0.64.1.0"
		processorArchitecture="x86"
		name="CornerStone"
		type="win32"
	/>
	<description>CornerStone</description>
	<dependency>
		<dependentAssembly>
			<assemblyIdentity
				type="win32"
				name="Microsoft.Windows.Common-Controls"
				version="6.0.0.0"
				processorArchitecture="X86"
				publicKeyToken="6595b64144ccf1df"
				language="*"
			/>
		</dependentAssembly>
	</dependency>
	</assembly>
	""" 

	setup(
			name = "CornerStone", 
			options = {'py2exe': {
					'bundle_files': 1, 
					'optimize': 2, 
					'dist_dir': 'dist/cornerstone',
					}},
			windows = [{
					'script': 'cornerstone.py',
					'icon_resources': [(0,"i/logo01.ico")],
					'other_resources': [(24,1,manifest)],
					}],
			zipfile = None,
	)	
	os.system("cp dist/cornerstone/* .")

