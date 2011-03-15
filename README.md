
ABOUT
=====

wxConerStone is a WX template project that contains all the scripts and src
necessary to build a cross-platform wxPython GUI application that bundles all
the necessary runtime files into the distributed executable on that platform.

Dependencies
------------
easy_install wxpython
easy_install py2app

Author
------
Email: kevin@ksturner.com <Kevin Turner>
Twitter: @ksturner



BUILDING MAC APP
----------------

You'll need to make sure you have wxPython2.8 and py2app installed for your
2.X branch of python.

Then, assuming you have all that, run:

    > python cornerstone_setup.py py2app

Afterwards, you should see a CornerStone.app in the same directory.
