#!/usr/bin/env python
#
import subprocess
import time, wave, pyaudio

import wmi
c = wmi.WMI()

#
# Kill a process by id
#
"""
notepad = subprocess.Popen(["notepad.exe"])
time.sleep(1)
for process in c.Win32_Process(ProcessId=notepad.pid):
	process.Terminate()
"""
#
# Which process ids correspond to an .exe
#
myprog = r"recorder.exe"
wavfilename = r"myfile.wav"
subprocess.Popen([myprog,wavfilename])

time.sleep(3)
for process in c.Win32_Process(caption=myprog):
	print process.ProcessId
#
# _Some_ (but not all) of the information about each file
#
for process in c.Win32_Process(caption=myprog):
	print process
	if wavfilename in process.CommandLine:
		print "terminating..."
		process.Terminate()
