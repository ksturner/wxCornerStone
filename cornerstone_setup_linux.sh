#!/bin/bash
mkdir -p $1/freeze/cornerstone
cd $1/freeze/
python freeze.py -o cornerstone ../../main.py
cd cornerstone
make
#strip cornerstone 	# don't strip freeze.py executables - bad
cp cornerstone ../../../
cd ../
rm -rf cornerstone
