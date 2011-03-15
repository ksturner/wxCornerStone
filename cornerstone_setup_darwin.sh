#!/bin/bash
rm -f runtime.zip
bash package_darwin.sh
mv runtime.zip "dist/CornerStone.app/Contents/Resources/."
cd "dist/CornerStone.app/Contents/Resources/"
unzip runtime.zip
rm -f runtime.zip
cd ../../../
tar -cf cornerstone.tar "CornerStone.app"
mv cornerstone.tar  ../.
cd ../
rm -rf dist
rm -rf build
rm -rf "CornerStone.app"
tar -xf cornerstone.tar
rm -f cornerstone.tar
