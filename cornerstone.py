#!/usr/bin/env python
import os, sys, re, datetime, time, subprocess, random
import wave, struct
import threading
from hashlib import md5
import sqlite3
import wx
import wx.lib.dialogs 
import wx.richtext as rt
import wx.lib.colourselect as csel
import wx.lib.mixins.listctrl as listmix
import wx.lib.scrolledpanel as scrolled
from wx.lib.wordwrap import wordwrap
import difflib, webbrowser

if sys.platform.startswith('win'):
    import wmi 

import images
import version

website_url = 'http://www.collectivelabs.com/'

#-------------------------------------------------------------------------------
class CornerStoneApp(wx.App):
    def __init__(self, redirect=True, filename=None):
        if not filename is None: filename = self.getHomeDir() + filename
        wx.App.__init__(self, redirect, filename)
    def OnInit(self):
        version_str = version.version_str

        dt = datetime.datetime.now() 
        sd = str(dt.year)+','+str(dt.month)+','+str(dt.day)+','+str(dt.hour)+','+str(dt.minute)
        self.prefs = {
            'windim':                '-1,-1,400,500',
            'prepdialog_windim':    '-1,-1,410,550',
            'managegrades_windim':    '-1,-1,640,480',
            'resultdialog_windim':    '-1,-1,350,450',
            'entrydialog_windim':    '-1,-1,350,450',
            'help_windim':            '-1,-1,350,450',
            'startdate':            sd,
            'quiz_text_color':        '#000000',
            'context_text_color':    '#969696',
            'normal_text_color':    '#000000',
            'added_text_color':        '#FF0000',
            'missing_text_color':    '#A0D2FF',
            'speech_font_size':        '12',
            'learn_ahead_rate':        '3',
            'recognize_speech':        'True',
            'online_dictionary':    'False',
            'recording_volume':        '50',
            'show_missing':            'True',
        }
        self.frame = CornerStoneFrame(version_str, self.getHomeDir(), self.prefs)
        self.frame.Show()
        self.SetExitOnFrameDelete(True) # False and OnExit isn't called on Frame close
        self.SetTopWindow(self.frame)
        return True
    def getHomeDir(self):
        """ Get a user-writable directory for storing application settings. """
        homedir = os.path.expanduser('~')
        if sys.platform.startswith('win'):
            homedir = os.environ['APPDATA'] + os.sep
            homedir += "CornerStone" + os.sep
            if not os.path.exists(homedir):
                os.mkdir(homedir)
        else:
            homedir = os.path.expanduser('~')
            if not homedir.endswith(os.sep):
                homedir += os.sep
            homedir += ".cornerstone" + os.sep
            if not os.path.exists(homedir):
                os.mkdir(homedir)
        return homedir

    def OnExit(self):
        pass

#-------------------------------------------------------------------------------
class CornerStoneFrame(wx.Frame):
    def __init__(self, version_str, datadir, prefs, parent=None):
        self.title = "CornerStone"
        self.datadir = datadir
        self.datafile = self.datadir + "mydb.db"
        self.version_str = version_str
        self.prefs = prefs
        self._loadAllPreferences(self.prefs)
        windim = self._loadWindowDimensions()
        wx.Frame.__init__(self, None, -1, self.title, size=(windim[2],windim[3]))
        if windim[0] > -1 and windim[1] > -1:
            self.SetPosition(wx.Point(windim[0],windim[1]))
        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        self.panel = wx.Panel(self)
        self.thread_queue = []
        self.exit_timer = None
        self.grades = [    "0 - Remembered nothing at all",
                        "1 - Remembered a tiny fraction", 
                        "2 - Remembered some of it",
                        "3 - Remembered most of it",
                        "4 - Remembered all of it, but slowly",
                        "5 - Remembered perfectly" ]
        self._createLayout()
        
        if sys.platform.startswith('win') or sys.platform.startswith('darwin'):
            # for some strange reason, it needs this to trigger an event to redraw sizers
            self.SetSize((windim[2]+1,windim[3]+1))
            self.SetSize((windim[2]-1,windim[3]-1))

        # set window icon
        if sys.platform.startswith('win'):
            icon = wx.Icon('cornerstone.exe', wx.BITMAP_TYPE_ICO)
            self.SetIcon(icon)

    def OnExit(self, event):
        self.Close()

    def OnCloseWindow(self, event):
        # Wait on any threads before proceeding to exit...
        # We could just use Thread.join() to wait for them, but unfortunately
        # we need this main thread to process their termination and there is a
        # race condition that is created within the gui. So, we just set a
        # timer to call the Exit() process repeatedly (every second) until all
        # threads are gone at which point the application can truly exit.
        self._saveWindowDimensions(self)
        wx.Exit()

    def UpdateToolbarItem(self, event):
        """Update menu items based on current status and context."""
        id = event.GetId()
        event.Enable(True)
        if id == self.deltext_tbb.GetId():
            if self.listpanel.list.SelectedItemCount <= 0:
                event.Enable(False)
        elif id == self.edittext_tbb.GetId():
            if self.listpanel.list.SelectedItemCount <= 0:
                event.Enable(False)

    def UpdateMenuItem(self, event):
        """Update menu items based on current status and context."""
        id = event.GetId()
        event.Enable(True)
        if id == self.deltext_mitem.GetId():
            if self.listpanel.list.SelectedItemCount <= 0:
                event.Enable(False)
        elif id == self.edittext_mitem.GetId():
            if self.listpanel.list.SelectedItemCount <= 0:
                event.Enable(False)
        elif id == self.grades_mitem.GetId():
            if self.listpanel.list.SelectedItemCount <= 0:
                event.Enable(False)

    def OnNewButton(self, event):
        d = EntryDialog(self)
        if d.ShowModal() == wx.ID_OK:
            if len(d.memname_text.GetValue().strip())>0 and len(d.memtext_text.GetValue().strip())>0:
                mem_id = self._setMemText(-1, d.memname_text.GetValue(), d.memtext_text.GetValue())
                index = self.listpanel.list.InsertStringItem(sys.maxint,d.memname_text.GetValue())
                
                wordcount = len(d.memtext_text.GetValue().upper().split())
                self.listpanel.list.SetStringItem(index, 1, str(wordcount))
                self.listpanel.list.SetStringItem(index, 2, datetime.datetime.now().strftime("%d %b %Y"))
                self.listpanel.list.SetItemData(index, mem_id)
                self.listpanel.list.CheckItem(index, True)
            else:
                self.DisplayError(self,"Entry wasn't saved because either the name or text was empty.")
    def OnDeleteButton(self, event):
        sel_item = self.listpanel.list.GetFirstSelected()
        if sel_item > -1:
            d = wx.MessageDialog(self,"Sure you want to delete?","Confirm Delete",wx.YES_NO|wx.ICON_QUESTION)
            if d.ShowModal() == wx.ID_YES:
                mem_id = self.listpanel.list.GetItemData(sel_item)
                if self.listpanel.list.DeleteItem(sel_item):
                    self._delMemText(mem_id)
                else:
                    self.DisplayError(self,"Couldn't perform delete!")
    def OnEditButton(self, event):
        d = EntryDialog(self)
        sel_item = self.listpanel.list.GetFirstSelected()
        memname = None
        while sel_item > -1:
            memname = self.listpanel.list.GetItemText(sel_item)
            mem_id = self.listpanel.list.GetItemData(sel_item)
            break
        if memname == None: return     # really bad.. it happened once when I was clicking like a mad man
        d.memname_text.SetValue(memname)
        d.memtext_text.SetValue(self._getMemText(mem_id))
        if d.ShowModal() == wx.ID_OK:
            self._setMemText(mem_id, d.memname_text.GetValue(), d.memtext_text.GetValue())
            self.listpanel.list.SetItemText(sel_item, d.memname_text.GetValue())
            wordcount = len(d.memtext_text.GetValue().upper().split())
            self.listpanel.list.SetStringItem(sel_item, 1, str(wordcount))

    def OnPrefs(self, event):
        d = PrefsDialog(self, self.prefs)
        if d.ShowModal() == wx.ID_OK:
            self.savePrefsFromDialog(d, self.prefs)
    def savePrefsFromDialog(self, d, prefs):
        """ Save all the preferences values from the dialog back into the database. """
        conn = sqlite3.connect(self.datafile)    
        c = conn.cursor()
        for prefname, prefvalue in prefs.iteritems():
            newvalue = d.getPrefValue(prefname)
            if not newvalue is None:
                if str(newvalue) != str(self.prefs[prefname]):
                    # value has changed, so update that preference
                    sql = "SELECT * FROM tbl_prefs WHERE varname=?"
                    c.execute(sql,(prefname,))
                    row = None
                    if not row in c:
                        sql = """INSERT INTO tbl_prefs (varname, varvalue) VALUES (?, ?)"""
                        c.execute(sql, (prefname,str(newvalue),))
                    else:
                        sql = "UPDATE tbl_prefs SET varvalue=? WHERE varname=?" 
                        c.execute(sql, (str(newvalue),prefname))
                    conn.commit()
                    prefs[prefname] = newvalue
        c.close()
    def OnManual(self, event):
        global website_url
        webbrowser.open(website_url + 'manual.html',new=2)
        
    def OnAbout(self, event):
        info = wx.AboutDialogInfo()
        info.Name = "CornerStone"
        info.Version = self.version_str
        info.Copyright = "(C) %s Kevin Turner" % (datetime.datetime.now().year,) + "\nBuild: " + version.version_build
        info.Description = wordwrap(
            " CornerStone is a unique program for helping you memorize large amounts "
            "of text using a special algorithm to determine what portions need the "
            "most practice and how often to test to most effeciently memorize the "
            "text.\n\n You can memorize any text that you can cut/paste or type into "
            "the program.",
            350, wx.ClientDC(self))
        info.WebSite = ("http://www.collectivelabs.com", "www.CollectiveLabs.com")
        info.Developers = [ "Kevin Turner", ]
        info.SetIcon(wx.Icon('i/logo01_96x96.png', wx.BITMAP_TYPE_PNG))
        licenseText = """You have the right to use this software as long as you don't resell it, and promise not to sue me."""
        info.License = wordwrap(licenseText, 500, wx.ClientDC(self))
        wx.AboutBox(info)

    def OnGrades(self, event):
        sel_item = self.listpanel.list.GetFirstSelected()
        if sel_item > -1:
            mem_id = self.listpanel.list.GetItemData(sel_item)
            mgf = ManageGradesDialog(self, mem_id, self.datafile, self.grades)
            if mgf.ShowModal() == wx.ID_OK:
                conn = sqlite3.connect(self.datafile)    
                c = conn.cursor()
                for item_order,grade in mgf.item_grades.iteritems():
                    sql = """UPDATE tbl_mem_items SET grade=? WHERE mem_id=? AND item_order=?"""
                    c.execute(sql, (grade,mem_id,item_order,))
                    conn.commit()
                c.close()

    def _getNOffFromItem(self, n0, noff, mem_id, grade_range):
        """ Find the highest number of consecutive items that are part of a set of accepted grades,
        and include the original item, that has the n0 order. """
        item_list = []

        for start_n in range(n0-noff, n0+1):
            temp_list = []
            started_series = False
            end_n = start_n + noff+1
            for n in range(start_n, end_n):
                item = None
                if item:
                    if item.grade in grade_range:
                        temp_list.append(item)
                        started_series = True
                    elif started_series:
                        # Save the temporary list if it contains more items that previously found.
                        if len(temp_list) > len(item_list):
                            # The temp list has more items, but test to see if it includes n0
                            grade_list = [ item.order for item in temp_list ] 
                            if n0 in grade_list:
                                item_list = temp_list[:]     # good list, save it
                        break     # Consecutive items ended, so abort this start_n value's series.
                elif started_series:
                    # Save the temporary list if it contains more items that previously found.
                    if len(temp_list) > len(item_list):
                        # The temp list has more items, but test to see if it includes n0
                        grade_list = [ item.order for item in temp_list ] 
                        if n0 in grade_list:  
                            item_list = temp_list[:]    # good list, save it
                    break     # Consecutive items ended, so abort this start_n value's series.
            if started_series and len(item_list) < len(temp_list):
                grade_list = [ item.order for item in temp_list ] 
                if n0 in grade_list:  
                    item_list = temp_list[:]    # good list, save it
                
        if len(item_list)==0:
            print "ERROR: item_list in %s was empty!" % (__name__)
            grade_list = [ item.order for item in temp_list ] 
            print "\ttemp_list =", temp_list
            print "\ttemp_grade_list =", grade_list
            print "\tn0 =", n0
            print "\tnoff =", noff
            print "\tmem_id =", mem_id
            print "\tgrade_range =", grade_range
            print "\tstarted_series =", started_series
            assert(len(item_list)>0)    # will fail..
        return item_list
    
    def OnQuizButton(self, event):
        d = wx.MessageDialog(self,"No additional memorization is required for today.","No Memorization Needed",wx.OK|wx.ICON_INFORMATION)
        d.CenterOnParent()
        d.ShowModal()

    def StartRecordingProcess(self, revision_item, item_list, recognize_speech):
        """ 
        Pass in the revision item, which is an item from tbl_mem_items, and
        is a portion of the greater body of text to be memorized which is
        referenced from tbl_mem, and displayed to the user in the list box. 
        """
        mem_id = revision_item.cat.mem_id 
        # Now, we only really care about the text that we have to record for. 

        counter = 0
        outstanding_threads = True
        # default fileprefix; use thread one if found
        fileprefix = 'mi' + self._getIDAsHex(revision_item.item_id)    

        d = RecordDialog(self, fileprefix)
        d.CenterOnParent()
        record_result = d.ShowModal()

    def _getIDAsHex(self, mem_id):
        return str(hex(mem_id)[2:].upper())     # mem_id in uppercase hexidecimal
    def DisplayError(self, parent, msg):
        d = wx.MessageDialog(parent,msg,"Error!", wx.OK|wx.ICON_ERROR)
        return (d.ShowModal() == wx.OK)

    def OnMemoryListCheckbox(self, mem_id, index, checked):
        """ Whenever a memory item in the main list box is [un]checked, this
        routine is called and we find the category object associated with this
        and set the active flag accordingly for it. """

        # Update the database as well.
        conn = sqlite3.connect(self.datafile)
        c = conn.cursor()
        sql = """UPDATE tbl_mem SET active=? WHERE id=?""" 
        c.execute(sql, (checked, mem_id))
        conn.commit()
        c.close

    def UpdateControls(self):
        """ This function loops over all controls and if their conditions are
        met, enables/disables them. """
        pass
    
    def _saveWindowDimensions(self, calling_window, varname='windim'):
        self._createDatabaseIfNecessary(self.datafile)
        conn = sqlite3.connect(self.datafile)
        c = conn.cursor()
        windim = ','.join(map(str,calling_window.GetPositionTuple())) + "," + ','.join(map(str,calling_window.GetSizeTuple()))
        sql = """SELECT * FROM tbl_prefs WHERE varname=?"""
        c.execute(sql, (varname,))
        foundone = False
        for row in c:
            foundone = True
            break
        if not foundone:
            sql = """INSERT INTO tbl_prefs (varname, varvalue) VALUES (?, ?)"""
            c.execute(sql,(varname, windim,))
            conn.commit()
            if self.prefs.has_key(varname):
                self.prefs[varname] = windim
        else:
            sql = """UPDATE tbl_prefs SET varvalue=? WHERE varname=?"""
            c.execute(sql,(windim,varname,))
            conn.commit()
            if self.prefs.has_key(varname):
                self.prefs[varname] = windim
        c.close()

    def _loadAllPreferences(self, prefs): 
        if not self._createDatabaseIfNecessary(self.datafile):
            conn = sqlite3.connect(self.datafile)
            c = conn.cursor()
            sql = "SELECT varname, varvalue FROM tbl_prefs"
            c.execute(sql)
            for row in c:
                prefname = row[0]
                prefvalue = row[1]
                if prefs.has_key(prefname):
                    prefs[prefname] = prefvalue
            c.close()

    def _loadWindowDimensions(self,varname='windim',defaultsize=(640,480)): 
        """ 
        Looks in the database for the variable name and returns the value,
        which is presumed to be related to window dimensions. 
        """
        # default position and size 
        windim = [-1,-1,defaultsize[0],defaultsize[1]] 
        self._createDatabaseIfNecessary(self.datafile)
        conn = sqlite3.connect(self.datafile)
        c = conn.cursor()
        c.execute("SELECT id,varname,varvalue FROM tbl_prefs WHERE varname=?",(varname,))
        for (id,varname,varvalue) in c:
            windim = map(int,varvalue.split(","))
            break
        c.close()
        return windim
    def _createLayout(self):
        self._create_menus()
        self._create_toolbar()

        self.mainsizer = wx.BoxSizer(wx.VERTICAL)
        listdata = self._getListDataDictionary()
        self.listpanel = MemoryListCtrlPanel(self.panel,listdata,self.UpdateControls, self.OnMemoryListCheckbox)
        self.mainsizer.Add(self.listpanel, 1, wx.EXPAND)

        self.panel.SetSizer(self.mainsizer)
        self.listpanel.list.SetFocus()
    def _create_toolbar(self):
        def doBind(item, handler, updateUI=None):
            self.Bind(wx.EVT_TOOL, handler, item)
            if updateUI is not None:
                self.Bind(wx.EVT_UPDATE_UI, updateUI, item)
            return item
        tbflags = wx.TB_HORIZONTAL | wx.NO_BORDER | wx.TB_FLAT
        self.tb = self.CreateToolBar(tbflags)
        tsize = (22,22)
        self.tb.SetToolBitmapSize(tsize)

        new_bmp = wx.Image('i/list-add.png', wx.BITMAP_TYPE_PNG).ConvertToBitmap() 
        del_bmp = wx.Image('i/list-remove.png', wx.BITMAP_TYPE_PNG).ConvertToBitmap() 
        edit_bmp = wx.Image('i/edit-select-all.png', wx.BITMAP_TYPE_PNG).ConvertToBitmap() 
        quiz_bmp = wx.Image('i/audio-input-microphone.png', wx.BITMAP_TYPE_PNG).ConvertToBitmap() 
        self.newtext_tbb = self.tb.AddLabelTool(-1,"New", new_bmp, shortHelp="New", longHelp="Long help")
        self.deltext_tbb = self.tb.AddLabelTool(-1,"Delete", del_bmp, shortHelp="Delete", longHelp="Long help")
        self.edittext_tbb = self.tb.AddLabelTool(-1,"Edit", edit_bmp, shortHelp="Edit", longHelp="Long help")
        self.tb.AddSeparator()
        self.quiz_tbb = self.tb.AddLabelTool(-1,"Quiz", quiz_bmp, shortHelp="Quiz", longHelp="Long help")

        doBind(self.newtext_tbb, self.OnNewButton, None)
        doBind(self.deltext_tbb, self.OnDeleteButton, self.UpdateToolbarItem)
        doBind(self.edittext_tbb, self.OnEditButton, self.UpdateToolbarItem)
        doBind(self.quiz_tbb, self.OnQuizButton, None)

        self.tb.Realize()


    def _create_menus(self):
        def doBind(item, menu, handler, updateUI=None, bitmap=None):
            self.Bind(wx.EVT_MENU, handler, item)
            if updateUI is not None:
                self.Bind(wx.EVT_UPDATE_UI, updateUI, item)
            if bitmap is not None:
                item.SetBitmap(bitmap)
            menu.AppendItem(item)
            return item
        menubar = wx.MenuBar()
        self.CreateStatusBar()

        new_bmp = wx.Bitmap('i/list-add.png', wx.BITMAP_TYPE_PNG)
        del_bmp = wx.Bitmap('i/list-remove.png', wx.BITMAP_TYPE_PNG)
        edit_bmp = wx.Bitmap('i/edit-select-all.png', wx.BITMAP_TYPE_PNG)
        quiz_bmp = wx.Bitmap('i/audio-input-microphone.png', wx.BITMAP_TYPE_PNG)
        man_bmp = wx.Bitmap('i/address-book-new.png', wx.BITMAP_TYPE_PNG)
        prefs_bmp = wx.Bitmap('i/preferences-system.png', wx.BITMAP_TYPE_PNG)

        # Create the File menu...
        menu = wx.Menu()
        self.newtext_mitem = doBind(wx.MenuItem(menu,-1,"&New Text\tCtrl+N", 
            "Create a new entry to memorize text."),
            menu, self.OnNewButton, self.UpdateMenuItem,
            new_bmp)    
        self.deltext_mitem = doBind(wx.MenuItem(menu,-1,"&Delete Text\tDel", 
            "Deletes a text entry."), menu,
            self.OnDeleteButton, self.UpdateMenuItem, 
            del_bmp)
        self.edittext_mitem = doBind(wx.MenuItem(menu, -1,"&Edit Text\tCtrl+E", 
            "Edit an entry for memorizing text."),
            menu, self.OnEditButton, self.UpdateMenuItem,
            edit_bmp)    
        menu.AppendSeparator()
        self.quiz_mitem = doBind(wx.MenuItem(menu,-1,"&Test...\tCtrl+T", 
            "Review text items for memorization."), menu,
            self.OnQuizButton, self.UpdateMenuItem,
            quiz_bmp)
        menu.AppendSeparator()
        self.exit_mitem = doBind(wx.MenuItem(menu,-1, 
            "E&xit\tCtrl+Q", "Exit the program"),
            menu, self.OnExit, self.UpdateMenuItem)
        menubar.Append(menu, "&File")

        # Create the Edit menu...
        menu2 = wx.Menu()
        self.grades_mitem = doBind(wx.MenuItem(menu2,-1, 
            "&Manage Grades\tCtrl+M", 
            "Show grades for all partitions of a text."),
            menu2, self.OnGrades, self.UpdateMenuItem,
            man_bmp)
        self.prefs_mitem = doBind(wx.MenuItem(menu2,-1, 
            "&Preferences...\tShift+P", 
            "Set various preferences related to the application"), 
            menu2, self.OnPrefs, self.UpdateMenuItem, prefs_bmp)
        menubar.Append(menu2, "&Edit")

        # Create Help menu
        helpmenu = wx.Menu()
        self.manual_mitem = doBind(wx.MenuItem(helpmenu, -1, "&Manual", 
                                "The complete CornerStone manual"),
                                helpmenu, self.OnManual)
        self.about_mitem = doBind(wx.MenuItem(helpmenu, -1, "&About", 
                                "About speech memorization application"),
                                helpmenu, self.OnAbout)
        menubar.Append(helpmenu,"&Help")

        # Set the application's menu bar.
        self.SetMenuBar(menubar)

    def _createDatabaseIfNecessary(self, datafilepath):
        didcreate = False
        if not os.path.exists(datafilepath):
            conn = sqlite3.connect(datafilepath)    
            c = conn.cursor()
            self._createTables(c)
            conn.commit()
            c.close()
            didcreate = True
        return didcreate

    def _adapt_timestamp(self, ts):
        return "%i:%i:%i:%i:%i" % (ts.Y,ts.M,ts.D,ts.h,ts.m)

    def _convert_timestamp(self, s):
        Y,M,D,h,m = map(int, s.split(":"))
        return Timestamp(Y,M,D,h,m)

    def _createTables(self, c):
        """ 
        This method creates all the necessary tables for our mini-database of
        speech info. 
        """
        sqlite3.register_adapter(Timestamp, self._adapt_timestamp)
        sqlite3.register_converter("Timestamp", self._convert_timestamp)
        commands =  [
            """CREATE TABLE tbl_mem ( id INTEGER PRIMARY KEY AUTOINCREMENT,
                memname TEXT NULL, memtext TEXT NULL, md5_cleanedtext TEXT NULL,
                md5_originaltext TEXT NULL, active BOOL) """,
            """CREATE TABLE tbl_mem_items ( id INTEGER PRIMARY KEY
                AUTOINCREMENT, mem_id INTEGER, mem_item_text TEXT, grade
                INTEGER, easy FLOAT, areps INTEGER, rreps INTEGER, 
                lapses INTEGER, areps_since_lapse INTEGER, rreps_since_lapse
                INTEGER, last_rep INTEGER, next_rep INTEGER, item_order INTEGER
                ) """, 
            """CREATE TABLE tbl_prefs ( id INTEGER PRIMARY KEY AUTOINCREMENT, 
                varname TEXT, varvalue TEXT ) """, 
                    ]
        # Append the preference creation sql commands
        for prefname, prefvalue in self.prefs.iteritems():
            sql = "INSERT INTO tbl_prefs (varname, varvalue) VALUES ('%s','%s')" % (prefname,prefvalue)
            commands.append(sql)
        # Execute all the sql commands to set up the database.
        for cmd in commands:
            c.execute(cmd)
            print cmd
    def _delMemText(self, mem_id):
        conn = sqlite3.connect(self.datafile)    
        c = conn.cursor()
        c.execute("DELETE FROM tbl_mem WHERE id=?", (mem_id,))
        conn.commit()
        c.close()
    def _getMemTextMD5(self, mem_id):
        """ Returns tuple of md5 sums for text. """
        mt_o = ''
        mt_c = ''
        conn = sqlite3.connect(self.datafile)    
        c = conn.cursor()
        c.execute("SELECT md5_originaltext, md5_cleanedtext FROM tbl_mem WHERE id=?", (mem_id,))
        for (md5_originaltext, md5_cleanedtext) in c:
            mt_o = md5_originaltext
            mt_c = md5_cleanedtext
            break    
        c.close()
        return (mt_o, mt_c)
    def _getMemOriginalTextMD5(self, mem_id):
        return self._getMemTextMD5(mem_id)[0]
    def _getMemCleanedTextMD5(self, mem_id):
        return self._getMemTextMD5(mem_id)[1]
    def _getMemText(self, mem_id):
        mt = ''
        conn = sqlite3.connect(self.datafile)    
        c = conn.cursor()
        c.execute("SELECT memtext FROM tbl_mem WHERE id=?", (mem_id,))
        for row in c:
            mt = row[0]
            break    
        c.close()
        return mt
    def _setMemText(self, mem_id, memname, memtext):
        conn = sqlite3.connect(self.datafile)    
        conn.row_factory = sqlite3.Row    
        c = conn.cursor()
        memtext = memtext.encode('utf8') 
        md5_cleanedtext = memtext 
        md5_originaltext = md5(memtext).hexdigest()

        needs_item_update = (md5_originaltext != self._getMemOriginalTextMD5(mem_id))

        # First, update the master text category. 
        if mem_id > -1:
            # update existing entry
            sql = """UPDATE tbl_mem SET memname=?, memtext=?, 
                    md5_cleanedtext=?, md5_originaltext=? WHERE id=?""" 
            c.execute(sql, (memname, memtext, md5_cleanedtext, md5_originaltext, mem_id,))
            id = mem_id
            conn.commit()
        else:
            # create new entry
            sql = """INSERT INTO tbl_mem (memname, memtext, 
                    md5_cleanedtext, md5_originaltext, active) 
                    VALUES (?,?,?,?,?)""" 
            c.execute(sql, (memname, memtext, md5_cleanedtext, md5_originaltext,True))
            sql = """SELECT MAX(id) FROM tbl_mem """
            c.execute(sql)
            #print "Looking for maximum tbl_mem.id"
            for row in c:
                mem_id = row[0]
                #print "max(tbl_mem.id) =", mem_id
                needs_item_update = True     # likely already true b/c of md5sum
                break
            conn.commit()

        # Second, update the items if the text has been changed in some way.
        if needs_item_update:
            #print "We needed to update tbl_mem_items..."
            seen_items = []
            itemtext = ''
            itemorder = 0
            lines = memtext.split("\n")
            print "number of lines in partitioned text =", len(lines)
            for line in lines:
                if len(line.strip()) == 0 or line == lines[-1]:
                    # blank line; save existing itemtext if not empty.
                    if line == lines[-1] and len(line.strip()) != 0:
                        itemtext += line.strip()
                    sql = """SELECT id, mem_id, mem_item_text, 
                                grade, easy, areps, rreps, 
                                lapses, areps_since_lapse, 
                                rreps_since_lapse, last_rep, next_rep, 
                                item_order 
                            FROM tbl_mem_items 
                            WHERE mem_item_text = ? AND mem_id = ?"""
                    if len(seen_items) > 0:
                        sql += 'AND id NOT IN (' + ','.join(seen_items) + ') '

                    c.execute(sql,(itemtext,mem_id,))
                    hadrow = False
                    for row in c:
                        hadrow = True
                        if row['item_order'] != itemorder:
                            sql = "UPDATE tbl_mem_items SET item_order=? WHERE id=?" 
                            c.execute(sql,(itemorder,row['id'],))
                            conn.commit()
                        else:
                            # The item exists with the same text and order number, so nothing
                            # needs to be updated.
                            pass
                        seen_items.append(str(row['id']))
                        break
                    if not hadrow:
                        sql = """INSERT INTO tbl_mem_items (mem_id, mem_item_text, grade, 
                            easy, areps, rreps, lapses, areps_since_lapse, 
                            rreps_since_lapse, last_rep, next_rep, item_order) 
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""" 
                        #print "Inserting new item, ", itemtext
                        I = None
                        #c.execute(sql,(mem_id, itemtext, I.grade, I.easy, \
                        #    I.areps, I.rreps, I.lapses, I.areps_since_lapse, \
                        #    I.rreps_since_lapse, I.last_rep, I.next_rep, itemorder))
                        conn.commit()
                        sql = """SELECT MAX(id) FROM tbl_mem_items """
                        c.execute(sql)
                        for row in c:
                            #print "newly inserted item had id=", str(row[0])
                            item_id = row[0]
                            seen_items.append(str(item_id))
                            break
                        conn.commit()
                    # reset item text, and bump item order counter
                    itemorder += 1
                    itemtext = ''
                else:
                    # item text.
                    itemtext += line + os.linesep
            # Now we need to delete any other items that were previously associated with this 
            # master text, but are now not. 
            sql = "DELETE FROM tbl_mem_items WHERE id NOT IN (" + ','.join(seen_items) + ") " + \
                    "AND mem_id=? "
            print "deleting unused tbl_mem_items"
            print "sql=", sql
            c.execute(sql, (mem_id,))
            conn.commit()
            
        c.close()
        return mem_id

    def _getListDataDictionary(self):
        d = {} 
        conn = sqlite3.connect(self.datafile)    
        c = conn.cursor()
        c.execute("""     SELECT tbl_mem.id, tbl_mem.memname, tbl_mem.memtext,
                        MAX(tbl_mem_items.last_rep) AS last_rep,
                        tbl_mem.active
                        FROM tbl_mem 
                        LEFT JOIN tbl_mem_items ON tbl_mem.id = tbl_mem_items.mem_id 
                        GROUP BY tbl_mem.id
                        """)
        c.close()
        return d

    def _getRGBColor(self, hex_color):
        """ Pass in hex color of format 'FFFFFF', and get a 3-element tuple for RGB """
        if hex_color[0] == '#':
            hex_color = hex_color[1:]
        r = int(hex_color[0:2],16)
        g = int(hex_color[2:4],16)
        b = int(hex_color[4:6],16)
        return (r,g,b)

    def _getHTMLColor(self, rgb_color):
        """ Pass in RGB color tuple and get HTML color code. """
        htmlcolor = '#'
        for i in range(0,3):
            color_component = str(hex(rgb_color[i]))[2:]
            if len(color_component) == 1: color_component = '0' + color_component
            htmlcolor += color_component.upper()
        return htmlcolor

    def tf(self, x): 
        """ Take a 'True' or 'False' or '1' or '0' string and convert to
            boolean. """
        if type(x) == type(u'') or type(x) == type(str('')):
            if x.lower().strip() == 'true': 
                return True
            else:
                return False
        elif type(x) == type(True):
            return x
        else:
            return False

#------------------------------------------------------------------------------    
class CreateSphinxFilesThread(threading.Thread):
    """ 
    This thread will create a pruned dictionary file for the mem_id_hex entry. 
    """
    def __init__(self, datadir, fileprefix, revision_item, memtext, finishedFunction):
        threading.Thread.__init__(self)
        self.fileprefix = fileprefix
        self.item_id = revision_item.item_id
        self.timeToQuit = threading.Event()
        self.timeToQuit.clear()
        self.finishedFunction = finishedFunction
        self.memtext = memtext
        self.datadir = datadir

    def stop(self):
        self.timeToQuit.set()

    def run(self):
        self.timeToQuit.set()
        wx.CallAfter(self.finishedFunction, self)

#-------------------------------------------------------------------------------    
class RecordingThread(threading.Thread):
    def __init__(self,threadnum,window,fileprefix=None):
        threading.Thread.__init__(self)
        self.threadnum = threadnum
        self.window = window
        self.timeToQuit = threading.Event()
        self.timeToQuit.clear()

        self.chunk = 1024 
        self.FORMAT = 8     #pyaudio.paInt16
        self.CHANNELS = 1 
        self.RATE = 16000
        self.RECORD_SECONDS = 60*1            # how many seconds to record for..
        self.WAVE_OUTPUT_FILENAME = "output.wav"
        if fileprefix:
            self.WAVE_OUTPUT_FILENAME = fileprefix+'.wav'
        #print "recording thread is recording to file =", self.WAVE_OUTPUT_FILENAME
    def getGuageRange(self):
        return self.RECORD_SECONDS
    def stop(self):
        self.timeToQuit.set()
    def run(self):
        msg = "here"     # is this necessary???
        """
        all = []

        data = ''
        p = pyaudio.PyAudio()
        if p == None:
            print "We didn't get a proper audio object initialized."
        stream = p.open(format=self.FORMAT, 
                        channels=self.CHANNELS,
                        rate=self.RATE,
                        input=True,
                        frames_per_buffer=self.chunk)

        stream.start_stream()
        for i in range(0, self.RATE / self.chunk * self.RECORD_SECONDS):
            if not self.timeToQuit.isSet():
                time.sleep(0.001)
                try:
                    data = stream.read(self.chunk)
                except IOError, e:
                    if e[1] == pyaudio.paInputOverflowed:
                        # I don't know that there is anything I can do about an overflow error
                        # except try to read again. Apparently this can happen.
                        self.chunk = self.chunk/2
                        if self.chunk < 2: 
                            self.chunk = 2
                        print "IOError; adjusting chunk to:", self.chunk
                    else:
                        pass
                else:
                    all.append(data)
            else:
                break
        stream.stop_stream()
        stream.close()
        p.terminate()

        # write the data we just recorded to a data file
        data = ''.join(all)
        wf = wave.open(self.WAVE_OUTPUT_FILENAME,'wb')
        wf.setnchannels(self.CHANNELS)
        try:
            wf.setsampwidth(p.get_sample_size(self.FORMAT))
        except ValueError, e:
            if e[1] == pyaudio.paSampleFormatNotSupported:
                print "ValueError; setting sample size bytes manually to 2"
                wf.setsampwidth(2)     # because we know pyaudio.paInt16 is 2 bytes 
        wf.setframerate(self.RATE)
        wf.writeframes(data)
        wf.close()
        wx.CallAfter(self.window.ThreadFinished, msg)
        """

#-------------------------------------------------------------------------------    
class TestListCtrl(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin, listmix.CheckListCtrlMixin):
    def __init__(self, parent, ID, cbhandler=None, pos=wx.DefaultPosition,
                 size=wx.DefaultSize, style=0):
        wx.ListCtrl.__init__(self, parent, ID, pos, size, style)
        listmix.ListCtrlAutoWidthMixin.__init__(self)
        listmix.CheckListCtrlMixin.__init__(self)
        self.checkbox_handler = cbhandler
    def OnCheckItem(self, index, checked):
        mem_id = self.GetItemData(index)
        #print "item mem_id =", i, checked
        if self.checkbox_handler:
            self.checkbox_handler(mem_id, index, checked)

class MemoryListCtrlPanel(wx.Panel, listmix.ColumnSorterMixin):
    def __init__(self, parent, listdata, update_f, cb_f):
        wx.Panel.__init__(self, parent, -1, style=wx.WANTS_CHARS)

        self.update_f = update_f     # function to call whenever we think we need an update
        tID = wx.NewId()
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        if wx.Platform == "__WXMAC__" and \
               hasattr(wx.GetApp().GetTopWindow(), "LoadDemo"):
            self.useNative = wx.CheckBox(self, -1, "Use native listctrl")
            self.useNative.SetValue( 
                not wx.SystemOptions.GetOptionInt("mac.listctrl.always_use_generic") )
            self.Bind(wx.EVT_CHECKBOX, self.OnUseNative, self.useNative)
            sizer.Add(self.useNative, 0, wx.ALL | wx.ALIGN_RIGHT, 4)
            

        self.list = TestListCtrl(self, tID, cbhandler=cb_f,
                                 style=wx.LC_REPORT 
                                 #| wx.BORDER_SUNKEN
                                 | wx.BORDER_NONE
                                 #| wx.LC_EDIT_LABELS
                                 | wx.LC_SORT_ASCENDING
                                 #| wx.LC_NO_HEADER
                                 #| wx.LC_VRULES
                                 #| wx.LC_HRULES
                                 | wx.LC_SINGLE_SEL
                                 )
        #self.il = wx.ImageList(16, 16)
        self.il = self.list.GetImageList(wx.IMAGE_LIST_SMALL)
        self.sm_up = self.il.Add(images.SmallUpArrow.GetBitmap())
        self.sm_dn = self.il.Add(images.SmallDnArrow.GetBitmap())
        #self.list.SetImageList(self.il, wx.IMAGE_LIST_SMALL)
        sizer.Add(self.list, 1, wx.EXPAND)

        self.PopulateList(listdata)

        # Now that the list exists we can init the other base class,
        # see wx/lib/mixins/listctrl.py
        self.itemDataMap = listdata
        listmix.ColumnSorterMixin.__init__(self, 2)
        #self.SortListItems(0, True)

        self.SetSizer(sizer)
        self.SetAutoLayout(True)

        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected, self.list)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnItemDeselected, self.list)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated, self.list)
        self.Bind(wx.EVT_LIST_DELETE_ITEM, self.OnItemDelete, self.list)
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColClick, self.list)
        self.Bind(wx.EVT_LIST_COL_RIGHT_CLICK, self.OnColRightClick, self.list)
        self.Bind(wx.EVT_LIST_COL_BEGIN_DRAG, self.OnColBeginDrag, self.list)
        self.Bind(wx.EVT_LIST_COL_DRAGGING, self.OnColDragging, self.list)
        self.Bind(wx.EVT_LIST_COL_END_DRAG, self.OnColEndDrag, self.list)
        self.Bind(wx.EVT_LIST_BEGIN_LABEL_EDIT, self.OnBeginEdit, self.list)

        self.list.Bind(wx.EVT_LEFT_DCLICK, self.OnDoubleClick)
        self.list.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)

        # for wxMSW
        self.list.Bind(wx.EVT_COMMAND_RIGHT_CLICK, self.OnRightClick)
        # for wxGTK
        self.list.Bind(wx.EVT_RIGHT_UP, self.OnRightClick)
    def OnUseNative(self, event):
        wx.SystemOptions.SetOptionInt("mac.listctrl.always_use_generic", not event.IsChecked())
        wx.GetApp().GetTopWindow().LoadDemo("ListCtrl")

    def PopulateList(self, listdata):
        # but since we want images on the column header we have to do it the hard way:
        info = wx.ListItem()
        info.m_mask = wx.LIST_MASK_TEXT | wx.LIST_MASK_IMAGE | wx.LIST_MASK_FORMAT
        info.m_image = -1
        info.m_format = wx.LIST_FORMAT_LEFT
        info.m_text = "Name"
        self.list.InsertColumnInfo(0, info)

        info.m_text = "Words"
        info.m_format = wx.LIST_FORMAT_CENTER
        self.list.InsertColumnInfo(1, info)

        info.m_format = wx.LIST_FORMAT_RIGHT
        info.m_text = "Last Quizzed"
        self.list.InsertColumnInfo(2, info)

        items = listdata.items()
        for key, data in items:
            index = self.list.InsertStringItem(sys.maxint, data[0])
            wordcount = str(data[3])
            self.list.SetStringItem(index, 1, wordcount)
            self.list.SetStringItem(index, 2, data[1])
            self.list.SetItemData(index, key)
            checked = data[2]     
            self.list.CheckItem(index, bool(checked))

        self.list.SetColumnWidth(0, 150)
        self.list.SetColumnWidth(1, 100)
        self.list.SetColumnWidth(2, wx.LIST_AUTOSIZE)

        # show how to select an item
        if len(items)>0: 
            self.list.SetItemState(0, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED)

        # show how to change the colour of a couple items
        #item = self.list.GetItem(1)
        #item.SetTextColour(wx.BLUE)
        #self.list.SetItem(item)
        #item = self.list.GetItem(4)
        #item.SetTextColour(wx.RED)
        #self.list.SetItem(item)
        self.currentItem = 0

    # Used by the ColumnSorterMixin, see wx/lib/mixins/listctrl.py
    def GetListCtrl(self):
        return self.list

    # Used by the ColumnSorterMixin, see wx/lib/mixins/listctrl.py
    def GetSortImages(self):
        return (self.sm_dn, self.sm_up)

    def OnRightDown(self, event):
        x = event.GetX()
        y = event.GetY()
        item, flags = self.list.HitTest((x, y))

        if item != wx.NOT_FOUND and flags & wx.LIST_HITTEST_ONITEM:
            self.list.Select(item)
        event.Skip()

    def getColumnText(self, index, col):
        item = self.list.GetItem(index, col)
        return item.GetText()

    def OnItemSelected(self, event):
        self.currentItem = event.m_itemIndex
        #event.Skip()
        self.update_f()

    def OnItemDeselected(self, evt):
        item = evt.GetItem()
        #if evt.m_itemIndex == 11:
        #    wx.CallAfter(self.list.SetItemState, 11, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED)
        self.update_f()

    def OnItemActivated(self, event):
        self.currentItem = event.m_itemIndex
        self.update_f()

    def OnBeginEdit(self, event):
        event.Allow()

    def OnItemDelete(self, event):
        pass

    def OnColClick(self, event):
        event.Skip()

    def OnColRightClick(self, event):
        item = self.list.GetColumn(event.GetColumn())

    def OnColBeginDrag(self, event):
        pass

    def OnColDragging(self, event):
        pass

    def OnColEndDrag(self, event):
        pass

    def OnDoubleClick(self, event):
        gparent = self.GetGrandParent()
        if type(gparent) == CornerStoneFrame:
            gparent.OnEditButton(None)

    def OnRightClick(self, event):
        return     # do nothing for this right now
        # only do this part the first time so the events are only bound once
        if not hasattr(self, "popupID1"):
            self.popupID1 = wx.NewId()
            self.popupID2 = wx.NewId()
            self.popupID3 = wx.NewId()
            self.popupID4 = wx.NewId()
            self.popupID5 = wx.NewId()
            self.popupID6 = wx.NewId()

            self.Bind(wx.EVT_MENU, self.OnPopupOne, id=self.popupID1)
            self.Bind(wx.EVT_MENU, self.OnPopupTwo, id=self.popupID2)
            self.Bind(wx.EVT_MENU, self.OnPopupThree, id=self.popupID3)
            self.Bind(wx.EVT_MENU, self.OnPopupFour, id=self.popupID4)
            self.Bind(wx.EVT_MENU, self.OnPopupFive, id=self.popupID5)
            self.Bind(wx.EVT_MENU, self.OnPopupSix, id=self.popupID6)

        # make a menu
        menu = wx.Menu()
        # add some items
        menu.Append(self.popupID1, "FindItem tests")
        menu.Append(self.popupID2, "Iterate Selected")
        menu.Append(self.popupID3, "ClearAll and repopulate")
        menu.Append(self.popupID4, "DeleteAllItems")
        menu.Append(self.popupID5, "GetItem")
        menu.Append(self.popupID6, "Edit")

        # Popup the menu.  If an item is selected then its handler
        # will be called before PopupMenu returns.
        self.PopupMenu(menu)
        menu.Destroy()


    def OnPopupOne(self, event):
        print "FindItem:", self.list.FindItem(-1, "Roxette")
        print "FindItemData:", self.list.FindItemData(-1, 11)

    def OnPopupTwo(self, event):
        index = self.list.GetFirstSelected()

        while index != -1:
            index = self.list.GetNextSelected(index)

    def OnPopupThree(self, event):
        self.list.ClearAll()
        wx.CallAfter(self.PopulateList)

    def OnPopupFour(self, event):
        self.list.DeleteAllItems()

    def OnPopupFive(self, event):
        item = self.list.GetItem(self.currentItem)
        print item.m_text, item.m_itemId, self.list.GetItemData(self.currentItem)

    def OnPopupSix(self, event):
        #self.list.EditLabel(self.currentItem)
        pass    

#-------------------------------------------------------------------------------    
class WaitDialog(wx.Dialog):
    def __init__(self, parent, msg, exit_function):
        self.parent = parent
        self.exit_function = exit_function
        wx.Dialog.__init__(self, parent, -1, "Please wait...")
        vsizer = wx.BoxSizer(wx.VERTICAL)
        st = wx.StaticText(self,-1,msg)
        vsizer.Add(st,0,wx.ALL,7)
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.progressbar = wx.Gauge(self,-1,10)
        hsizer.Add(self.progressbar,1,wx.EXPAND|wx.ALL,7)
        vsizer.Add(hsizer)
        self.SetSizer(vsizer)
        self.Fit()

        pushCursor(self, wx.CURSOR_WAIT)

        self.poll_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnPollTimer, self.poll_timer)
        self.poll_timer.Start(500)

        self.prog_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnProgressTimer, self.prog_timer)
        self.prog_timer.Start(100)

    def OnProgressTimer(self, event):
        self.progressbar.Pulse()
    def OnPollTimer(self, event):
        """ Check the thread queue to see if important threads are finished. """
        if self.exit_function():
            popCursor(self)
            self.Close()

#-------------------------------------------------------------------------------    
class ResultDialog(wx.Dialog):
    def __init__(self, parent, memtext, text, segs, wavefilename, revision_item, item_list, grades, prefs):
        self.parent = parent
        self.windim_varname = 'resultdialog_windim'
        self.prefs = prefs
        mystyle = wx.DEFAULT_DIALOG_STYLE | wx.TAB_TRAVERSAL | wx.RESIZE_BORDER
        windim = parent._loadWindowDimensions(self.windim_varname,(350,450))
        wx.Dialog.__init__(self, parent, -1, "Results of Quiz", size=(windim[2],windim[3]),style=mystyle)
        if windim[0] > -1 and windim[1] > -1:
            self.SetPosition(wx.Point(windim[0],windim[1]))
        if segs:
            self.segs = [ s for s in segs if s != '<sil>' and s != '</sil>' and s != '' ]
        self.text = text
        self.grades = grades
        if segs:
            self.memtext = memtext
        else:
            self.memtext = memtext
        self.wavefilename = wavefilename
        self.errors = []
        self.sound = None
        self.sound_timer = None
        self.normal_color = self.prefs['normal_text_color']
        self.error_add_color = self.prefs['added_text_color']
        self.error_sub_color = self.prefs['missing_text_color']
        self.show_missing = self.parent.tf(self.prefs['show_missing'])
        self.revision_item = revision_item
        self.item_list = item_list
        self.new_grades = {}

        self.mainsizer = wx.BoxSizer(wx.VERTICAL)
        self.spokentrans_sizer = wx.BoxSizer(wx.VERTICAL)
        self.mastertrans_sizer = wx.BoxSizer(wx.VERTICAL)
        self.actionsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.buttonsizer = wx.BoxSizer(wx.HORIZONTAL)

        self.notebook = wx.Notebook(self, -1, style=wx.BK_DEFAULT)
        self.spokentrans_tab = wx.Panel(self.notebook,-1)
        self.mastertrans_tab = wx.Panel(self.notebook,-1)
        if segs:
            self.notebook.AddPage(self.spokentrans_tab, "Spoken Transcript:")
        self.notebook.AddPage(self.mastertrans_tab, "Master Transcript:")

        self.said = None
        if segs:
            self.said = rt.RichTextCtrl(self.spokentrans_tab, -1, style=wx.TE_MULTILINE)
        self.original_txt = rt.RichTextCtrl(self.mastertrans_tab, -1, style=wx.TE_MULTILINE|rt.RE_READONLY)
        self.okbutton = wx.Button(self, wx.ID_OK,"Done")
        self.Bind(wx.EVT_BUTTON, self.OnOK, self.okbutton)

        self.playall_button = wx.Button(self, -1, "Play Audio")
        self.playall_button.SetToolTipString("Play the all the audio as it was recorded.")
        self.Bind(wx.EVT_BUTTON, self.OnPlayAllButton, self.playall_button)
        if segs:
            self.add_colorsel = csel.ColourSelect(self, -1,"Added",self.parent._getRGBColor(self.error_add_color))
            self.Bind(csel.EVT_COLOURSELECT, self.OnSelectAddColor,self.add_colorsel)
            if self.show_missing:
                self.sub_colorsel = csel.ColourSelect(self, -1,"Missing",self.parent._getRGBColor(self.error_sub_color))
                self.Bind(csel.EVT_COLOURSELECT, self.OnSelectSubColor,self.sub_colorsel)

        self.okbutton.SetDefault()
        self._displayTextTranscripts(revision_item, item_list)

        self.buttonsizer.AddStretchSpacer(2)
        self.buttonsizer.Add(self.okbutton)

        self.mastertrans_sizer.Add(self.original_txt,1,wx.EXPAND|wx.ALL,2)
        if segs:
            self.spokentrans_sizer.Add(self.said,1,wx.EXPAND|wx.ALL,2)
        self.actionsizer.Add(self.playall_button,0,wx.ALIGN_CENTER)
        if segs:
            self.actionsizer.Add(self.add_colorsel,0)
            if self.show_missing:
                self.actionsizer.Add(self.sub_colorsel,0)
        self.mainsizer.Add(self.notebook,1,wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP,5)
        self.mainsizer.Add(self.actionsizer,0,wx.EXPAND|wx.ALL,5)
        self.mainsizer.Add(self.buttonsizer,0,wx.EXPAND|wx.ALL,5)
        if segs:
            self.spokentrans_tab.SetSizer(self.spokentrans_sizer)
        self.mastertrans_tab.SetSizer(self.mastertrans_sizer)
        self.mainsizer.SetMinSize((350,450))
        self.SetSizer(self.mainsizer)
        #self.Fit()
    def OnOK(self, event):
        self.parent._saveWindowDimensions(self, self.windim_varname)
        self.EndModal(wx.ID_OK)
        
    def UpdateControls(self):
        """ This function loops over all controls and if their conditions are met, 
        enables/disables them. """
        enable = (self.list.GetSelectedItemCount > 0)
        #self.playbutton.Enable(enable)
    def _initLatestError(self, latesterror, difftoken):
        """ Initializes the latest error dictionary object that holds information we
        use in displaying the error in the spoken transcript. """
        latesterror['startframe'] = 0
        latesterror['endframe'] = 0
        if difftoken[0] == '-':    
            latesterror['minuscount'] = 1
            latesterror['pluscount'] = 0
            d = difftoken.replace('- ','')
        elif difftoken[0] == '+':    
            latesterror['pluscount'] = 1
            latesterror['minuscount'] = 0
            d = difftoken.replace('+ ','')
        else:
            latesterror['pluscount'] = 0
            latesterror['minuscount'] = 0
        latesterror['difftokens'] = []
        latesterror['difftokens'].append(difftoken)
        latesterror['text'] = d + ' '
    def _appendLatestErrorInfo(self, latesterror, difftoken):
        """ Takes latest error token and applies it to the pre-existing dictionary object
        responsible for tracking the unrecognized speech for the spoken transcript. """
        if difftoken[0] == '-':    
            latesterror['minuscount'] += 1
            d = difftoken.replace('- ','')
        elif difftoken[0] == '+':    
            latesterror['pluscount'] += 1
            d = difftoken.replace('+ ','')
        latesterror['difftokens'].append(difftoken)
        latesterror['text'] += d + ' '

    def addError(self,e):
        """ Whether the error is a additional word error. """
        return e['minuscount'] < e['pluscount']
    def subError(self,e):
        """ Whether the error is a subtracted word error. """
        return not self.addError(e)

    def _generateErrorDisplayString(self, latesterror):
        """ Comes up with whatever string will be used to display the unrecognized 
        portion of the spoken transcript. """
        last_symbol = ''    
        new_error = None
        chars = latesterror['startchar'] 

        for d in latesterror['difftokens']:
            if d[0] != last_symbol:
                if last_symbol != '':
                    # If we were in progress of displaying an error, close it first.
                    self.said.EndTextColour()
                    new_error['endchar'] = chars
                    self.errors.append(new_error)
                    new_error = None
                new_error = {}
                self._initLatestError(new_error, d)
                new_error['startchar'] = chars
                color_code = self.error_add_color
                if d[0] == '-':
                    color_code = self.error_sub_color
                if (self.show_missing and d[0] == '-') or d[0] != '-':
                    self.said.BeginTextColour(self.parent._getRGBColor(color_code))
                    self.said.WriteText(d.replace(d[0]+' ', '')+' ')
                    chars += len(d.replace(d[0]+' ', '')+' ')
                    last_symbol = d[0]
            else: 
                # While the errors are of the same type, just keep outputting them.
                self.said.WriteText(d.replace(d[0]+' ', '')+' ')
                chars += len(d.replace(d[0]+' ', '')+' ')
                self._appendLatestErrorInfo(new_error, d)
        if last_symbol != '':
            # After looping over the errors, if we have one left open, close it.
            self.said.EndTextColour()
            new_error['endchar'] = chars
            self.errors.append(new_error)
            new_error = None

    def OnOriginalURL(self, event):
        self.OnURL(self.original_txt, event)

    def OnSaidURL(self, event):
        self.OnURL(self.said, event)

    def OnURL(self, edit_control, event):
        (item_id, grade) = map(int, event.GetString().split(":"))
        #print "item_id=%s grade=%s" % (item_id, grade)
        self.clicked_item_id = item_id
        self.clicked_item_grade = grade
        self.clicked_text_control = edit_control

        if not hasattr(self, "popupID1"):
            self.popupID0 = wx.NewId()
            self.popupID1 = wx.NewId()
            self.popupID2 = wx.NewId()
            self.popupID3 = wx.NewId()
            self.popupID4 = wx.NewId()
            self.popupID5 = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnPopupZero,     id=self.popupID0)
            self.Bind(wx.EVT_MENU, self.OnPopupOne,     id=self.popupID1)
            self.Bind(wx.EVT_MENU, self.OnPopupTwo,     id=self.popupID2)
            self.Bind(wx.EVT_MENU, self.OnPopupThree,     id=self.popupID3)
            self.Bind(wx.EVT_MENU, self.OnPopupFour,     id=self.popupID4)
            self.Bind(wx.EVT_MENU, self.OnPopupFive,     id=self.popupID5)

        checked = [ wx.ITEM_NORMAL for i in range(0,6) ] 
        checked[grade] = wx.ITEM_CHECK
        menu = wx.Menu()
        menu.Append(self.popupID0, self.grades[0], "", checked[0])
        menu.Append(self.popupID1, self.grades[1], "", checked[1])
        menu.Append(self.popupID2, self.grades[2], "",checked[2])
        menu.Append(self.popupID3, self.grades[3], "", checked[3])
        menu.Append(self.popupID4, self.grades[4], "", checked[4])
        menu.Append(self.popupID5, self.grades[5], "", checked[5])
        if grade==0:
            id = self.popupID0 
        elif grade==1:
            id = self.popupID1 
        elif grade==2:
            id = self.popupID2 
        elif grade==3:
            id = self.popupID3 
        elif grade==4:
            id = self.popupID4 
        elif grade==5:
            id = self.popupID5 
        menu.Check(id, True)
        self.PopupMenu(menu)
        menu.Destroy()

    def updateItemList(self, item_id, new_grade):
        for item in self.item_list:
            if item.item_id == item_id:
                item.grade = new_grade

    def OnPopupZero(self, event):
        self.new_grades[self.clicked_item_id] = 0
        self.updateItemList(self.clicked_item_id, self.new_grades[self.clicked_item_id])
        self.rewriteGradeUrl(self.clicked_item_id, self.new_grades[self.clicked_item_id])
    def OnPopupOne(self, event):
        self.new_grades[self.clicked_item_id] = 1
        self.updateItemList(self.clicked_item_id, self.new_grades[self.clicked_item_id])
        self.rewriteGradeUrl(self.clicked_item_id, self.new_grades[self.clicked_item_id])
    def OnPopupTwo(self, event):
        self.new_grades[self.clicked_item_id] = 2
        self.updateItemList(self.clicked_item_id, self.new_grades[self.clicked_item_id])
        self.rewriteGradeUrl(self.clicked_item_id, self.new_grades[self.clicked_item_id])
    def OnPopupThree(self, event):
        self.new_grades[self.clicked_item_id] = 3
        self.updateItemList(self.clicked_item_id, self.new_grades[self.clicked_item_id])
        self.rewriteGradeUrl(self.clicked_item_id, self.new_grades[self.clicked_item_id])
    def OnPopupFour(self, event):
        self.new_grades[self.clicked_item_id] = 4
        self.updateItemList(self.clicked_item_id, self.new_grades[self.clicked_item_id])
        self.rewriteGradeUrl(self.clicked_item_id, self.new_grades[self.clicked_item_id])
    def OnPopupFive(self, event):
        self.new_grades[self.clicked_item_id] = 5
        self.updateItemList(self.clicked_item_id, self.new_grades[self.clicked_item_id])
        self.rewriteGradeUrl(self.clicked_item_id, self.new_grades[self.clicked_item_id])

    def writeGradeUrl(self, text_control, item_id, grade):
        urlStyle = rt.TextAttrEx()
        urlStyle.SetTextColour(wx.BLUE)
        urlStyle.SetFontUnderlined(True)

        text_control.BeginStyle(urlStyle)
        text_control.BeginURL(str(item_id)+":"+str(grade))
        text_control.WriteText("("+str(grade)+")")
        text_control.EndURL()
        text_control.EndStyle()
        text_control.WriteText(" ")
        self.new_grades[item_id] = grade
        return 4    # return the number of characters written 
    
    def rewriteGradeUrl(self, item_id, grade):
        text_control = self.clicked_text_control
        self.clicked_text_control = None

        text_control.SetEditable(True)
        text_control.MoveToLineStart()
        text_control.Remove(text_control.GetInsertionPoint(),text_control.GetInsertionPoint()+4)
        text_control.MoveToLineStart()
        self.writeGradeUrl(text_control, item_id, grade)
        text_control.MoveToLineStart()
        text_control.SetEditable(False)

        if text_control == self.said:
            # rewrite the original text control
            # !! we recreate the rich text field because we can't programatically change the
            # URL text/target reliably. Every trick was tried, but there aren't enough hooks
            # in the wxPython api to manipulate the underlying structure.
            self.mastertrans_sizer.Clear(True)
            self.original_txt = rt.RichTextCtrl(self.mastertrans_tab, -1, style=wx.TE_MULTILINE)
            self.displayOriginalPartitionedText(self.item_list)
            self.mastertrans_sizer.Add(self.original_txt,1,wx.EXPAND|wx.ALL,2)
            self.mastertrans_sizer.Layout()
        else:
            if self.said:
                # rewrite the said text control
                # !! we recreate the rich text field because we can't programatically change the
                # URL text/target reliably. Every trick was tried, but there aren't enough hooks
                # in the wxPython api to manipulate the underlying structure.
                self.spokentrans_sizer.Clear(True)
                self.said = rt.RichTextCtrl(self.spokentrans_tab, -1, style=wx.TE_MULTILINE)
                self.displaySaidPartitionedText(self.item_list)
                self.spokentrans_sizer.Add(self.said,1,wx.EXPAND|wx.ALL,2)
                self.spokentrans_sizer.Layout()

    def displayOriginalPartitionedText(self, item_list):
        """ Write the item list text partitions to the original text control. """
        self.original_txt.BeginFontSize(int(self.prefs['speech_font_size']))
        self.original_txt.Bind(wx.EVT_TEXT_URL, self.OnOriginalURL)
        for item in item_list:
            self.writeGradeUrl(self.original_txt, item.item_id, item.grade)
            self.original_txt.WriteText(item.a)
            self.original_txt.Newline()
        self.original_txt.EndFontSize()

    def displaySaidPartitionedText(self, item_list):
        """ Write the item text partitions to the recognized speech, rich text control. """
        original_word_lines = os.linesep.join(re.split('\s',self.memtext))
        spoken_word_lines = os.linesep.join(re.split('\s',self.text))
        self.said.Bind(wx.EVT_TEXT_URL, self.OnSaidURL)

        # Perform the diff here.
        odiff = difflib.ndiff(original_word_lines.splitlines(1), spoken_word_lines.splitlines(1))

        # Format of a seg list item is such:
        # Word, Start frame, End frame, AScore?, LMScore?
        # ('WHO', 3239, 3252, -142614, -23133)
        self.errors = []     # probably already initialized, but just be safe
        latest_error = None
        open_error = 0
        chars = 0
        seg_index = -1 

        # Consolidate bogus -+ of the same word back to back when the word was really said, is
        # correct, and should never have been flagged with both + and -. I don't know why difflib
        # behaves this way.
        #!!!! I have no idea why this list comprehension wouldn't work; it kept returning an empty
        # list
        #diff = [ di.strip() for di in odiff ]    # del ?-mark diff tokens; we don't need them
        diff = []
        for d in odiff:
            if d[0] != '?':
                diff.append(d.strip())

        deletion_stack = []
        difflen = len(diff)
        for i in range(1,difflen):
            c1 = diff[i-1][0]
            c2 = diff[i][0]
            if (c1 == '-' and c2 == '+') or (c1 == '+' and c2 == '-'): 
                if diff[i-1][2:] == diff[i][2:]:
                    diff[i-1] = diff[i][2:]        # set the first token without the -/+
                    deletion_stack.insert(0,i)    # queue the second token for deletion after this loop
        # delete, from highest index to lowest, all duplicate diff tokens
        for i in deletion_stack:
            del diff[i]

        current_item_index = 0
        current_item_tokens = []

        self.said.BeginFontSize(int(self.prefs['speech_font_size']))
        for d in diff:
            # Here we eat up tokens for each partition/chunk so that when we get to the end
            # we know when to write out a new URL header for another chunk.
            w = d.strip()
            if d.startswith('-') or d.startswith('+'):
                w = d[2:]     # get the word 
            # for some reason, my logic is flawed, because I try to index current_item_index past len
            if len(current_item_tokens) == 0 and current_item_index < len(item_list):
                current_item = item_list[current_item_index]
                current_item_tokens = current_item.a.upper().split()
                self.said.Newline()
                chars += 1
                chars += self.writeGradeUrl(self.said, current_item.item_id, current_item.grade)
                self.new_grades[current_item.item_id] = current_item.grade
                current_item_index += 1
            if len(current_item_tokens) > 0:
                if w.strip() == current_item_tokens[0].strip():
                    del current_item_tokens[0]

            # Now, if we find an error, start tracking chars so we can color it appropriately.
            if d.startswith('-') or d.startswith('+'):
                # We encountered an error diff token.
                if open_error == 0: 
                    latest_error = {}
                    self._initLatestError(latest_error, d)
                    latest_error['startchar'] = len(self.said.GetValue()) 
                    if seg_index > -1:
                        latest_error['startframe'] = self.segs[seg_index][1] # start of last good frame
                    open_error = 1
                else:
                    self._appendLatestErrorInfo(latest_error, d)
                chars += len(d)+1
            elif d.startswith('?'):
                pass
            else:
                # We encountered a normal, non-error diff token.
                seg_index = self._findNextSeg(seg_index, d)
                if open_error == 1:
                    open_error = 0
                    latest_error['endchar'] = latest_error['startchar'] + len(latest_error['text'])
                    latest_error['endframe'] = latest_error['startframe']
                    if seg_index > -1:
                        latest_error['endframe'] = self.segs[seg_index][2]     # end of first good one
                    self._generateErrorDisplayString(latest_error)
                    latest_error = None
                self.said.WriteText(d+' ') # Output the first non-error diff token
                chars += len(d) + 1
        if open_error==1 and latest_error:
            latest_error['endchar'] = len(self.memtext)*2
            latest_error['endframe'] = self.segs[-1][2]     # end of last known seg
            self._generateErrorDisplayString(latest_error)
            latest_error = None

        self.said.EndFontSize()
        self.said.SetEditable(False)    # make the control read-only
        
    def _displayTextTranscripts(self, revision_item, item_list):
        self.text = self.text.replace('<sil>','')
        self.text = self.text.replace('</sil>','')

        self.displayOriginalPartitionedText(item_list)

        # If the text control for the spoken text exists, fill it.
        if self.said:
            self.displaySaidPartitionedText(item_list)
        
    def RebuildSpokenTranscript(self):
        """ This routine loops over the mistake list items and rebuilds the text
        in the spoken transcript to reflect whether any of those list items have
        been approved or rejected. Red if they are still incorrect, or black if 
        they are okay."""
        add_attr = rt.TextAttrEx()
        add_attr.SetTextColour(self.parent._getRGBColor(self.error_add_color))

        sub_attr = rt.TextAttrEx()
        sub_attr.SetTextColour(self.parent._getRGBColor(self.error_sub_color))

        for e in self.errors:
            self.said.SetSelection(e['startchar'], e['endchar'])
            selrange = self.said.GetSelectionRange()
            a = None
            if e['minuscount'] > e['pluscount']:
                a = sub_attr
            elif e['minuscount'] < e['pluscount']:
                a = add_attr
            if a: self.said.SetStyle(selrange, a)
        self.said.SelectNone()

    def _findNextSeg(self, seg_index, text):
        """ Look in self.segs for the next occurance of text; return that index. """
        # In theory this will likely just go forward by one, but the for-loop
        # is more forgiving of wrong assumptions.
        seg_index += 1
        seg_index2 = seg_index
        for si in self.segs[seg_index:]:
            if si[0].strip().lower() == text.strip().lower():
                return seg_index2
            seg_index2 += 1
        return -1
    
    def PlaySomeSound(self,filename):
        """ Play a file using more platform-dependent python code. """
        """ !! this code didn't work for me. """
        if sys.platform.startswith('win'):
           from winsound import PlaySound, SND_FILENAME, SND_ASYNC
           PlaySound(filename, SND_FILENAME|SND_ASYNC)
        elif sys.platform.find('linux')>-1:
           from wave import open as waveOpen
           from ossaudiodev import open as ossOpen
           s = waveOpen(filename,'rb')
           (nc,sw,fr,nf,comptype, compname) = s.getparams( )
           dsp = ossOpen('/dev/dsp','w')
           try:
             from ossaudiodev import AFMT_S16_NE
           except ImportError:
             if byteorder == "little":
               AFMT_S16_NE = ossaudiodev.AFMT_S16_LE
             else:
               AFMT_S16_NE = ossaudiodev.AFMT_S16_BE
           dsp.setparameters(AFMT_S16_NE, nc, fr)
           data = s.readframes(nf)
           s.close()
           dsp.write(data)
           dsp.close()    

    def OnPlayAllButton(self, event):
        if self.sound:
            self.sound.Stop()
            self.sound = None
            self.playall_button.SetLabel("Play All")
            if self.sound_timer:
                self.sound_timer.Stop()
                self.sound_timer = None
        else:
            self.sound = wx.Sound(self.wavefilename)

            # To increase the volume of the file:
            # sox -t wav -s -w -v 4.0 mi27.wav test4.wav 

            self.sound.Play(wx.SOUND_ASYNC)
            #self.PlaySomeSound(self.wavefilename)
            self.sound_timer = wx.Timer(self)
            wf = wave.open(self.wavefilename,'rb')
            framerate = wf.getframerate()    # returns the sampling frequency
            nframes = wf.getnframes()        # returns the number of audio frames
            wf.close()

            self.Bind(wx.EVT_TIMER, self.OnTimerEvent, self.sound_timer)
            # The wx.Sound module is very immature in python; it does not 
            # implement the IsPlaying() method, or have a callback for when
            # it is done. Sooo.. we just have to calculate the time required
            # to play through the WAV file and set a timer to reset our controls
            # when that time runs up.    
            ms = (nframes/float(framerate))*float(1000) + 100
            self.sound_timer.Start(ms)
            print "nframes =", nframes
            print "framerate =", framerate
            print "secs = (nframes/framerate)*1000 + 100"
            print "play all timer set for:", str(ms) + "(ms)"
            self.playall_button.SetLabel("Stop")
            #wx.YieldIfNeeded()
    def OnTimerEvent(self, event):
        if self.sound: 
            self.sound.Stop()
            self.sound = None
            self.playall_button.SetLabel("Play All")
            if self.sound_timer:
                print "stopped."
                self.sound_timer.Stop()
                self.sound_timer = None
    def OnSelectAddColor(self, event):
        self.error_add_color = self.parent._getHTMLColor(event.GetValue())
        self.RebuildSpokenTranscript()
    def OnSelectSubColor(self, event):
        self.error_sub_color = self.parent._getHTMLColor(event.GetValue())
        self.RebuildSpokenTranscript()
    def _checkAllListItems(self, check):    
        for index in range(self.list.GetItemCount()):
            self.list.CheckItem(index, check)
    def _convertSphinxFrame2WAVFrame(self, sphinxframe, framerate):
        return sphinxframe * (framerate/100)
    def _bumpStartFrameBack(self, startframe, framerate):
        n = 5     # arbitrary number
        return startframe - (framerate/n)
    def _bumpEndFrameForward(self, endframe, framerate):
        n = 5     # arbitrary number
        return endframe + (framerate/n) * 2 
    def _playWAVPortionOnOther(self, startframe, endframe):
        """ Play back the wave file portion using PyAudio, which should work
        for most operating systems, but not GTK2 due to ASIO sample rate bug. """
        wf = wave.open(self.wavefilename,'rb')
        sampwidth = wf.getsampwidth()    # return the sample width in bytes
        framerate = wf.getframerate()    # returns the sampling frequency
        nframes = wf.getnframes()        # returns the number of audio frames
        nchannels = wf.getnchannels()
        wf.close()

        p = pyaudio.PyAudio()
        stream = p.open(format = 
                p.get_format_from_width(sampwidth),
                channels = nchannels,
                rate = framerate, 
                output = True)

        # Convert the start/end frames to the WAV sample frequencies.  We have
        # to convert because Sphinx frame counts are at a different frequency
        # than file.
        startframe = self._convertSphinxFrame2WAVFrame(startframe, framerate)
        endframe = self._convertSphinxFrame2WAVFrame(endframe, framerate)

        # Adjust the frames to start just before and go just past the trouble spot
        startframe = self._bumpStartFrameBack(startframe,framerate)
        endframe = self._bumpEndFrameForward(endframe,framerate)

        data = wf.readframes(startframe)
        data = wf.readframes(endframe - startframe)
        stream.write(data)
        stream.stop_stream()
        stream.close()
        p.terminate()
        
    def _playWAVPortionOnGTK2(self, startframe, endframe):
        """ Due to a bug in the GTK2 PyAudio with ASIO sample rates, we have 
        to play the portion of the WAV file using this method. This method 
        extracts the frames for the audio data, and resaves them to a new, shorter
        WAV file for playback using the wxPython sound module. """
        wf = wave.open(self.wavefilename,'rb')
        sampwidth = wf.getsampwidth()    # return the sample width in bytes
        framerate = wf.getframerate()    # returns the sampling frequency
        nframes = wf.getnframes()        # returns the number of audio frames
        nchannels = wf.getnchannels()
        wf.close()

        # Convert the start/end frames to the WAV sample frequencies.  We have
        # to convert because Sphinx frame counts are at a different frequency
        # than file.
        startframe = self._convertSphinxFrame2WAVFrame(startframe, framerate)
        endframe = self._convertSphinxFrame2WAVFrame(endframe, framerate)

        # Adjust the frames to start just before and go just past the trouble
        # spot
        startframe = self._bumpStartFrameBack(startframe,framerate)
        endframe = self._bumpEndFrameForward(endframe,framerate)

        try:
            wf = open(self.wavefilename,'rb')
            hdata = wf.read(44)     # standard PCM wave format has a header of 44 bytes, then frames..
            data = wf.read(startframe*sampwidth)
            # If we try to read more frames than actually exist in the WAV
            # file, it is okay.
            data = wf.read((endframe-startframe)*sampwidth)
            wf.close()
            # Here, we actually *might* have been able to play the sound, but
            # the WAV header (hdata) has some incorrect values in it. I didn't 
            # have the time to figure out what exactly was wrong.
            wf2 = wave.open(self.parent.datadir + 'tmp.wav','wb')
            wf2.setnchannels(nchannels)
            try:
                wf2.setsampwidth(sampwidth)
            except ValueError, e:
                if e[1] == pyaudio.paSampleFormatNotSupported:
                    print "ValueError; setting sample size bytes manually to 2"
                    wf2.setsampwidth(2)     # because we know pyaudio.paInt16 is 2 bytes 
            wf2.setframerate(framerate)
            wf2.writeframes(data)
            wf2.close()
            sound = wx.Sound('tmp.wav')
            sound.Play(wx.SOUND_ASYNC)
        except NotImplementedError, v:
            wx.MessageBox(str(v), "Exception Message")


#-------------------------------------------------------------------------------    
class RecordDialog(wx.Dialog):
    def __init__(self, parent, fileprefix):
        wx.Dialog.__init__(self,parent,-1,"Recording...")

        self.parent = parent
        self.fileprefix = fileprefix

        self.mainsizer = wx.BoxSizer(wx.VERTICAL)
        self.buttonsizer = wx.BoxSizer(wx.HORIZONTAL)

        self.okbutton = wx.Button(self, wx.ID_OK,"OK")
        self.okbutton.SetDefault()
        self.cancelbutton = wx.Button(self, wx.ID_CANCEL, "Cancel")

        # We won't run the recording thread under Windows, but we still create
        # it because it contains some of the parameters and methods that the
        # rest of the program interfaces with.
        self.thread = RecordingThread(1, self, fileprefix)

        # wx.Guage(parent, id, range, pos=wx.DefaultPosition, size=wx.DefaultSize, 
        #            style=wx.GA_HORIZONTAL, validator=wx.DefaultValidator, name="guage")
        range = self.thread.getGuageRange()
        self.progressbar = wx.Gauge(self,-1,range)
        self.progressbar.SetBezelFace(3)
        self.progressbar.SetShadowWidth(3)
        self.progresstxt_label = "%s seconds of %s"
        self.progresstxt = wx.StaticText(self,-1,self.progresstxt_label % (0,self.thread.RECORD_SECONDS),style=wx.ALIGN_LEFT)
        self.sound_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimerEvent, self.sound_timer)

        self.buttonsizer.AddStretchSpacer(1)
        self.buttonsizer.Add(self.okbutton)
        self.buttonsizer.Add(self.cancelbutton)
        # remember, wx.ALL pertains to borders, and wx.EXPAND to the available
        # space the following says that it should get 1 unit of free space, and
        # 7 pixels of border 
        self.mainsizer.Add(self.progressbar,1,wx.EXPAND|wx.ALL,7)
        self.mainsizer.Add(self.progresstxt,0,wx.EXPAND|wx.LEFT|wx.RIGHT,7)
        self.mainsizer.Add(self.buttonsizer,0,wx.EXPAND|wx.ALL,7)
        self.SetSizer(self.mainsizer)
        self.Fit()

        self.thread_counter = 0
        self.recorder_prog = None
        if sys.platform.startswith('win'):
            self.recorder_prog = sys.platform + '/recorder.exe'
        elif sys.platform.startswith('darwin'):
            self.recorder_prog = 'darwin/recorder'
        elif sys.platform.startswith('linux'):
            self.recorder_prog = sys.platform + '/recorder'
    def ThreadTick(self,msg):
        self.thread_counter += 1
        self.progressbar.SetValue(self.thread_counter)
        self.progresstxt.SetLabel(self.progresstxt_label % \
                                    (self.thread_counter,self.thread.RECORD_SECONDS))
    def ThreadFinished(self,msg):
        #print "finished!"
        pass
    def OnTimerEvent(self, event):
        self.ThreadTick('asdf')


#------------------------------------------------------------------------------ 
class PrefsDialog(wx.Dialog):
    def __init__(self, parent, prefs):
        self.parent = parent
        self.prefs = prefs
        self.windim_varname = 'prefs_windim'
        windim = parent._loadWindowDimensions(self.windim_varname,(640,480))
        mystyle = wx.DEFAULT_DIALOG_STYLE | wx.TAB_TRAVERSAL | wx.RESIZE_BORDER
        wx.Dialog.__init__(self, parent, -1, "Preferences", style=mystyle,\
                            size=(windim[2],windim[3]))
        if windim[0] > -1 and windim[1] > -1:
            self.SetPosition(wx.Point(windim[0],windim[1]))
        self.panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Here we map our internal control objects to the preference names. We will
        # use this later on to construct lambda functions to return the values.
        self.quiz_text_color = None
        self.context_text_color = None
        self.normal_text_color = None
        self.added_text_color = None
        self.missing_text_color = None
        self.fontsize = None
        self.learn_ahead_rate = None
        self.recognize_speech = None
        self.online_dictionary = None
        self.recording_volume = None
        self.show_missing = None

        # Here is just a mapping of internal preferences to the external labels 
        # displayed to the user. These functions take one argument, the preference
        # name, and return the appropriate value.
        cfunc = self.getColorControlPref
        nfunc = self.getNormalControlPref
        def newMapping(l,c,f):
            return { 'label': l, 'control': c, 'value': f }

        self.pref_mappings = {
            'quiz_text_color': newMapping('Memorize Text Color:',self.quiz_text_color,cfunc),
            'context_text_color': newMapping('Contextual Text Color:',self.context_text_color,cfunc),
            'normal_text_color': newMapping('Normal Text Color:',self.normal_text_color,cfunc),
            'added_text_color': newMapping('Added Text Color:',self.added_text_color,cfunc),
            'missing_text_color': newMapping('Missing Text Color:',self.missing_text_color,cfunc),
            'speech_font_size': newMapping('Speech Font Size:',self.fontsize,nfunc),
            'learn_ahead_rate': newMapping('Learn Ahead Rate:',self.learn_ahead_rate,nfunc),
            'recognize_speech':    newMapping('Perform speech recognition.',self.recognize_speech,nfunc),
            'online_dictionary': newMapping('Automatically update pronunciation dictionary from online database.',self.online_dictionary,nfunc),
            'recording_volume': newMapping('Recording Volume:',self.recording_volume,nfunc),
            'show_missing': newMapping('Display words that should have been spoken but were not.', self.show_missing,nfunc),
        }

        self.nb = wx.Notebook(self.panel)
        # General Tab
        self.general_panel = wx.Panel(self.nb)
        self.general_sizer = wx.BoxSizer(wx.VERTICAL)

        # General Tab - Preparation Dialog
        box = wx.StaticBox(self.general_panel,-1,"Preparation Dialog")
        hsizer = wx.StaticBoxSizer(box, wx.HORIZONTAL)
        for pi in ['quiz_text_color','context_text_color']: 
            st = wx.StaticText(self.general_panel, -1, self.pref_mappings[pi]['label'])
            cb = csel.ColourSelect(self.general_panel, -1, '', self.parent._getRGBColor(self.prefs[pi]))
            self.Bind(csel.EVT_COLOURSELECT, self.OnSelectPrefColor, cb)
            hsizer.Add(st, 0, wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.TOP|wx.BOTTOM,7)
            hsizer.Add(cb, 0, wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL|wx.RIGHT|wx.TOP|wx.BOTTOM,7)
            self.pref_mappings[pi]['control'] = cb
        self.general_sizer.Add(hsizer,0,wx.EXPAND|wx.ALL,7)

        # General Tab - Results Dialog
        box = wx.StaticBox(self.general_panel,-1,"Results Dialog")
        hsizer = wx.StaticBoxSizer(box, wx.HORIZONTAL)
        for pi in ['normal_text_color','added_text_color','missing_text_color']: 
            st = wx.StaticText(self.general_panel, -1, self.pref_mappings[pi]['label'])
            cb = csel.ColourSelect(self.general_panel, -1, '', self.parent._getRGBColor(self.prefs[pi]))
            hsizer.Add(st, 0, wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.TOP|wx.BOTTOM,7)
            hsizer.Add(cb, 0, wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL|wx.RIGHT|wx.TOP|wx.BOTTOM,7)
            self.pref_mappings[pi]['control'] = cb
        self.general_sizer.Add(hsizer,0,wx.EXPAND|wx.ALL,7)

        # Font preferences
        prefname = 'speech_font_size'
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        st = wx.StaticText(self.general_panel,-1,self.pref_mappings[prefname]['label'])
        hsizer.Add(st, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 7)
        prefvalue = int(self.prefs[prefname]) 
        self.pref_mappings[prefname]['control'] = wx.Slider(self.general_panel,-1,prefvalue,8,32,style=wx.SL_HORIZONTAL|wx.SL_AUTOTICKS|wx.SL_LABELS)
        self.Bind(wx.EVT_SLIDER, self.OnFontsizeUpdate, self.pref_mappings[prefname]['control'])
        self.samplefont = wx.StaticText(self.general_panel,-1,'Sample')
        #self.samplefont.SetBackgroundColour('Yellow')
        font = wx.Font(prefvalue,wx.SWISS,wx.NORMAL,wx.NORMAL)
        self.samplefont.SetFont(font)
        hsizer.Add(self.pref_mappings[prefname]['control'], 1, wx.ALIGN_CENTER_VERTICAL|wx.EXPAND|wx.ALL, 7)
        hsizer.Add(self.samplefont, 1, wx.ALIGN_CENTER_VERTICAL|wx.EXPAND|wx.ALL, 7)
        self.general_sizer.Add(hsizer,0,wx.EXPAND|wx.ALL,7)

        self.general_panel.SetSizer(self.general_sizer)

        # Memorization Tab
        self.memo_panel = wx.Panel(self.nb)
        self.memo_sizer = wx.BoxSizer(wx.VERTICAL)
        hsizer = wx.FlexGridSizer(cols=2, hgap=5, vgap=5)
        hsizer.AddGrowableCol(1)
        prefname = 'learn_ahead_rate'
        st = wx.StaticText(self.memo_panel,-1,self.pref_mappings[prefname]['label'])
        prefvalue = int(self.prefs[prefname]) 
        sc_style = wx.SL_HORIZONTAL|wx.SL_AUTOTICKS
        self.pref_mappings[prefname]['control'] = wx.Slider(self.memo_panel,-1,prefvalue,3,5,style=sc_style)
        hsizer.Add(st, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL,7)
        hsizer.Add(self.pref_mappings[prefname]['control'], 1, wx.ALIGN_CENTER_VERTICAL|wx.EXPAND|wx.ALL,7)

        hsizer.AddSpacer(1)
        hsizer2 = wx.BoxSizer(wx.HORIZONTAL)
        label_1 = 'Faster'
        label_5 = 'Slower'
        hsizer2.Add(wx.StaticText(self.memo_panel,-1,label_1,style=wx.ALIGN_LEFT),1,wx.EXPAND)
        hsizer2.Add(wx.StaticText(self.memo_panel,-1,label_5,style=wx.ALIGN_RIGHT),1,wx.EXPAND)
        hsizer.Add(hsizer2, 1, wx.EXPAND|wx.ALL, 7)

        hsizer.AddSpacer(1)
        l = """The learn ahead rate governs how fast newer portions of the text are added to the group being tested. Slower rates also try to limit the amount of memorization you perform in a day so you don't waste time cramming more than is necessary and instead tries to allow time to commit to long term memory."""
        hsizer.Add(wx.StaticText(self.memo_panel,-1,l),1,wx.EXPAND|wx.ALL,7)

        self.memo_sizer.Add(hsizer, 0, wx.EXPAND|wx.ALL, 7)
        self.memo_panel.SetSizer(self.memo_sizer)

        # Speech Tab
        self.speech_panel = wx.Panel(self.nb)
        self.speech_sizer = wx.BoxSizer(wx.VERTICAL)
        hsizer = wx.FlexGridSizer(cols=1, hgap=5, vgap=5)
        hsizer.AddGrowableCol(0)
        prefname = 'recognize_speech'
        l = self.pref_mappings[prefname]['label']
        self.pref_mappings[prefname]['control'] = wx.CheckBox(self.speech_panel, -1, l)
        self.pref_mappings[prefname]['control'].SetValue(self.parent.tf(self.prefs[prefname]))
        hsizer.Add(self.pref_mappings[prefname]['control'], 0, wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)
        prefname = 'show_missing'
        l = self.pref_mappings[prefname]['label']
        self.pref_mappings[prefname]['control'] = wx.CheckBox(self.speech_panel, -1, l)
        self.pref_mappings[prefname]['control'].SetValue(self.parent.tf(self.prefs[prefname]))
        hsizer.Add(self.pref_mappings[prefname]['control'], 0, wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)
        prefname = 'online_dictionary'
        l = self.pref_mappings[prefname]['label']
        self.pref_mappings[prefname]['control'] = wx.CheckBox(self.speech_panel, -1, l) 
        self.pref_mappings[prefname]['control'].SetValue(self.parent.tf(self.prefs[prefname]))
        hsizer.Add(self.pref_mappings[prefname]['control'], 0, wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)
        """
        prefname = 'recording_volume'
        l = self.pref_mappings[prefname]['label']

        hsizer2 = wx.BoxSizer(wx.HORIZONTAL)
        hsizer2.Add(wx.StaticText(self.speech_panel,-1,l,style=wx.ALIGN_LEFT),0,wx.ALL,7)
        prefvalue = float(self.prefs[prefname]) 
        #mystyle = wx.SL_HORIZONTAL|wx.SL_AUTOTICKS|wx.SL_LABELS
        mystyle = wx.SL_HORIZONTAL
        self.pref_mappings[prefname]['control'] = wx.Slider(self.speech_panel,-1,prefvalue,1,100,style=mystyle)
        sl = self.pref_mappings[prefname]['control']
        self.Bind(wx.EVT_SLIDER, self.OnRecordingVolume, sl)
        hsizer2.Add(sl,1,wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_LEFT|wx.EXPAND|wx.ALL,7)
        hsizer.Add(hsizer2, 1, wx.EXPAND|wx.ALL, 7)
        """
        self.speech_sizer.Add(hsizer, 0, wx.EXPAND|wx.ALL, 7)
        self.speech_panel.SetSizer(self.speech_sizer)

        # Advanced Tab
        self.adv_panel = wx.Panel(self.nb)
        self.adv_sizer = wx.BoxSizer(wx.VERTICAL)
        hsizer = wx.FlexGridSizer(cols=2, hgap=5, vgap=5)
        hsizer.AddGrowableCol(0)
        l = "No preferences yet." 
        st = wx.StaticText(self.adv_panel, -1, l) 
        hsizer.Add(st, 0, wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)
        self.adv_sizer.Add(hsizer, 0, wx.EXPAND|wx.ALL, 7)
        self.adv_panel.SetSizer(self.adv_sizer)

        self.nb.AddPage(self.general_panel,"General")
        self.nb.AddPage(self.memo_panel,"Memorization Engine")
        self.nb.AddPage(self.speech_panel,"Speech Engine")
        self.nb.AddPage(self.adv_panel,"Advanced")

        sizer.Add(self.nb, 1, wx.EXPAND|wx.ALL, 7)
        btnsizer = wx.StdDialogButtonSizer()
        okbtn = wx.Button(self.panel, wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self.OnOK, okbtn)
        okbtn.SetDefault()
        btnsizer.AddButton(okbtn)

        cancelbtn = wx.Button(self.panel, wx.ID_CANCEL)
        self.Bind(wx.EVT_BUTTON, self.OnCancel, cancelbtn)
        btnsizer.AddButton(cancelbtn)
        btnsizer.Realize()

        sizer.Add(btnsizer, 0, wx.ALIGN_CENTER_VERTICAL|wx.TOP|wx.BOTTOM|wx.RIGHT, 5)

        self.panel.SetSizer(sizer)
        self.panel.Fit()

        if sys.platform.startswith('win') or sys.platform.startswith('darwin'):
            # for some strange reason, it needs this to trigger an event to redraw sizers
            self.SetSize((windim[2]+1,windim[3]+1))
            self.SetSize((windim[2]-1,windim[3]-1))

    def getColorControlPref(self, prefname):
        """ Find the preference name in our internal mappings structure, find the control
        object, and return the HTML hex value for the color value. """
        if self.pref_mappings.has_key(prefname):
            if self.pref_mappings[prefname]['control']:
                return self.parent._getHTMLColor(self.pref_mappings[prefname]['control'].GetColour())
        return None
    def getNormalControlPref(self, prefname):
        if self.pref_mappings.has_key(prefname):
            if self.pref_mappings[prefname]['control']:
                return self.pref_mappings[prefname]['control'].GetValue()
        return None
    def OnFontsizeUpdate(self, event):
        """ When the font size slider is used, it triggers this event, which allows us
        the opportunity to update the sample text with the new size. """
        fs = self.pref_mappings['speech_font_size']['control'].GetValue()
        font = wx.Font(fs,wx.SWISS,wx.NORMAL,wx.NORMAL)
        self.samplefont.SetFont(font)
        #self.samplefont.SetBackgroundColour('Yellow')

    def OnRecordingVolume(self, event):
        """ Recording volume is a slider that should return a floating point value 
        for how much we are going to scale the volume by. """
        rv = self.pref_mappings['recording_volume']['control'].GetValue()
        print "recording volume =", rv 

    def OnSelectPrefColor(self, event):
        error_add_color = self.parent._getHTMLColor(event.GetValue())
        
    def OnOK(self, event):
        self.parent._saveWindowDimensions(self, self.windim_varname)
        self.EndModal(wx.ID_OK)
    def OnCancel(self, event):
        self.parent._saveWindowDimensions(self, self.windim_varname)
        self.EndModal(wx.ID_CANCEL)
    def getPrefValue(self, prefname):
        value = None
        if self.pref_mappings.has_key(prefname):
            value = self.pref_mappings[prefname]['value'](prefname) 
        return value

#-------------------------------------------------------------------------------    
class ManageGradesDialog(wx.Dialog):
    def __init__(self, parent=None, mem_id=-1,datafile=None, grades=[]):
        self.parent = parent
        self.windim_varname = 'managegrades_windim'
        windim = parent._loadWindowDimensions(self.windim_varname,(640,480))
        mystyle = wx.DEFAULT_DIALOG_STYLE | wx.TAB_TRAVERSAL | wx.RESIZE_BORDER
        wx.Dialog.__init__(self, parent, -1, "Manage Grades", style=mystyle,\
                            size=(windim[2],windim[3]))
        if windim[0] > -1 and windim[1] > -1:
            self.SetPosition(wx.Point(windim[0],windim[1]))
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel = wx.Panel(self)
        self.item_grades = {}
        self.mgw = ManageGradesPanel(self.panel,mem_id,datafile,grades)

        btnsizer = wx.StdDialogButtonSizer()
        
        okbtn = wx.Button(self.panel, wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self.OnOK, okbtn)
        okbtn.SetDefault()
        btnsizer.AddButton(okbtn)

        cancelbtn = wx.Button(self.panel, wx.ID_CANCEL)
        self.Bind(wx.EVT_BUTTON, self.OnCancel, cancelbtn)
        btnsizer.AddButton(cancelbtn)
        btnsizer.Realize()

        okbtn.SetFocus()

        sizer.Add(self.mgw, 1, wx.EXPAND|wx.ALL, 5)
        sizer.Add(btnsizer, 0, wx.ALIGN_CENTER_VERTICAL|wx.TOP|wx.BOTTOM|wx.RIGHT, 5)
        self.panel.SetSizer(sizer)

        if sys.platform.startswith('win') or sys.platform.startswith('darwin'):
            # for some strange reason, it needs this to trigger an event to redraw sizers
            self.SetSize((windim[2]+1,windim[3]+1))
            self.SetSize((windim[2]-1,windim[3]-1))

    def OnOK(self, event):
        self.parent._saveWindowDimensions(self, self.windim_varname)
        self.EndModal(wx.ID_OK)
    def OnCancel(self, event):
        self.parent._saveWindowDimensions(self, self.windim_varname)
        self.EndModal(wx.ID_CANCEL)


#-------------------------------------------------------------------------------    
class ManageGradesPanel(scrolled.ScrolledPanel):
    def __init__(self, parent, mem_id, datafile, grades, id=-1, size=wx.DefaultSize):
        size = (wx.DefaultSize[0],wx.DefaultSize[1]+100)
        scrolled.ScrolledPanel.__init__(self,parent,id,size=size,style=wx.SUNKEN_BORDER)
        self.datafile = datafile
        self.SetScrollRate(20,20)
        self.grades = grades

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        parent = self.GetParent().GetParent()

        conn = sqlite3.connect(self.datafile)    
        conn.row_factory = sqlite3.Row    
        c = conn.cursor()
        sql = """SELECT * FROM tbl_mem_items
                WHERE mem_id=? ORDER BY item_order """
        c.execute(sql, (mem_id,))

        for row in c:
            hsizer = wx.BoxSizer(wx.HORIZONTAL)
            choice = wx.Choice(self,-1,(250,-1),choices = grades)
            self.Bind(wx.EVT_CHOICE, self.OnChangeGrade, choice)
            parent.item_grades[row['item_order']] = row['grade']
            for g in grades:
                choice.SetClientData(choice.FindString(g),row['item_order'])
            choice.SetSelection(choice.FindString(grades[row['grade']]))

            hsizer.Add(choice,0)
            txt = wx.TextCtrl(self,-1,row['mem_item_text'].strip())
            txt.SetToolTip(wx.ToolTip(row['mem_item_text']))
            hsizer.Add(txt,1,wx.EXPAND)
            self.sizer.Add(hsizer,0,wx.EXPAND|wx.LEFT|wx.TOP|wx.RIGHT,7)
        c.close()
        self.SetSizer(self.sizer)

    def OnChangeGrade(self, event):
        cb = event.GetEventObject()
        parent = self.GetParent().GetParent()
        data = cb.GetClientData(event.GetSelection())
        #print "changed grade to '%s' for item: %s" % (event.GetString(), data)
        parent.item_grades[data] = int(event.GetString().lstrip()[0])

#-------------------------------------------------------------------------------
class Timestamp(object):
    def __init__(self,Y,M,D,h,m):
        self.Y = Y    # Year
        self.M = M    # Month
        self.D = D    # Day
        self.h = h     # Hour
        self.m = m  # Minute
    def __repr__(self):
        return"(%i:%i:%i:%i:%i)" % (self.Y,self.M,self.D,self.h,self.m)

    def setNow(self):
        n = datetime.datetime.now()
        self.Y = n[0]
        self.M = n[1]
        self.D = n[2]
        self.h = n[3]
        self.m = n[4]

#-------------------------------------------------------------------------------    
class PrepDialog(wx.Dialog):
    def __init__(self, parent, prefs):
        self.parent = parent
        self.windim_varname = 'prepdialog_windim'
        mystyle = wx.DEFAULT_DIALOG_STYLE | wx.TAB_TRAVERSAL | wx.RESIZE_BORDER
        windim = parent._loadWindowDimensions(self.windim_varname,(410,550))
        wx.Dialog.__init__(self,parent,-1,"Review Text in Preparation for Recall",\
                           size=(windim[2],windim[3]),style=mystyle)
        if windim[0] > -1 and windim[1] > -1:
            self.SetPosition(wx.Point(windim[0],windim[1]))
        self.mainsizer = wx.BoxSizer(wx.VERTICAL)
        self.buttonsizer = wx.StdDialogButtonSizer()
        self.mainsizer.SetMinSize((10,300))

        self.okbutton = wx.Button(self, wx.ID_OK)
        self.okbutton.SetDefault()
        self.Bind(wx.EVT_BUTTON, self.OnOK, self.okbutton)
        self.cancelbutton = wx.Button(self, wx.ID_CANCEL)
        self.Bind(wx.EVT_BUTTON, self.OnCancel, self.cancelbutton)
        memtext_label = wx.StaticText(self,-1,"Review the BOLD Text:")
        self.memtext_text = rt.RichTextCtrl(self, -1, style=wx.TE_MULTILINE) #|wx.ALIGN_CENTER)
        help_label = wx.StaticText(self, -1, "Review the text in bold, black font and prepare to recite it.\nThe text in light gray is simply provided as helpful context for you.")

        self.buttonsizer.Add(self.cancelbutton)
        self.buttonsizer.Add(self.okbutton)
        self.buttonsizer.Realize()

        self.mainsizer.Add(memtext_label,0,wx.LEFT|wx.TOP|wx.RIGHT,7)
        self.mainsizer.Add(self.memtext_text,1,wx.EXPAND|wx.LEFT|wx.RIGHT,7)
        self.mainsizer.Add(help_label,0,wx.LEFT|wx.RIGHT|wx.BOTTOM,7)
        self.mainsizer.Add(self.buttonsizer,0,wx.ALIGN_CENTER_VERTICAL|wx.ALL,7)    # ok/cancel/etc. buttons
        self.okbutton.SetFocus()
        self.SetSizer(self.mainsizer)

    def OnOK(self, event):
        self.parent._saveWindowDimensions(self, self.windim_varname)
        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.parent._saveWindowDimensions(self, self.windim_varname)
        self.EndModal(wx.ID_CANCEL)

#-------------------------------------------------------------------------------    
class EntryDialog(wx.Dialog):
    """
    I would really like to have some plugin panels here where someone could
    define a GUI and some logic that would insert any text they wanted into the
    text field. 

    Here is a url for various portions of bible text that uses the BibleGateway
    web page to pull up text:
    
    http://www.biblegateway.com/passage/index.php?book_id=57&chapter=1&version=49&interface=print
    http://www.biblegateway.com/passage/index.php?search=Philippians%201:1-20;&version=49;&interface=print
    """ 

    def __init__(self,parent):
        self.parent = parent
        self.windim_varname = 'entrydialog_windim'
        mystyle = wx.DEFAULT_DIALOG_STYLE | wx.TAB_TRAVERSAL | wx.RESIZE_BORDER
        windim = parent._loadWindowDimensions(self.windim_varname,(350,450))
        wx.Dialog.__init__(self,parent,-1,"Add/Edit memorization entry",size=(windim[2],windim[3]),style=mystyle)
        if windim[0] > -1 and windim[1] > -1:
            self.SetPosition(wx.Point(windim[0],windim[1]))
        self.panel = wx.Panel(self)

        self.mainsizer = wx.BoxSizer(wx.VERTICAL)
        self.buttonsizer = wx.BoxSizer(wx.HORIZONTAL)    # for ok/cancel, etc.
        self.buttonsizer2 = wx.BoxSizer(wx.HORIZONTAL)    # for actions
        self.mainsizer.SetMinSize((10,400))
        self.buttonsizer.SetMinSize((300,10))

        self.partition_button = wx.Button(self.panel, -1, "Partition")
        self.help_button = wx.BitmapButton(self.panel, -1, wx.Bitmap('i/help-browser.png',wx.BITMAP_TYPE_PNG))
                                        
        self.Bind(wx.EVT_BUTTON, self.OnPartition, self.partition_button)
        self.Bind(wx.EVT_BUTTON, self.OnHelp, self.help_button)

        self.okbutton = wx.Button(self.panel, wx.ID_OK,"OK")
        self.okbutton.SetDefault()
        self.Bind(wx.EVT_BUTTON, self.OnOK, self.okbutton)
        self.cancelbutton = wx.Button(self.panel, wx.ID_CANCEL, "Cancel")
        self.Bind(wx.EVT_BUTTON, self.OnCancel, self.cancelbutton)

        memname_label = wx.StaticText(self.panel,-1,"Name:")
        self.memname_text = wx.TextCtrl(self.panel, -1)
        memtext_label = wx.StaticText(self.panel,-1,"Text:")
        self.memtext_text = wx.TextCtrl(self.panel, -1, style=wx.TE_MULTILINE)
        #self.Bind(wx.EVT_TEXT, self.OnChanged, self.memtext_text)

        self.buttonsizer2.Add(self.partition_button,0,wx.ALIGN_CENTER_VERTICAL|wx.RIGHT,7)
        self.buttonsizer2.Add(self.help_button,0,wx.ALIGN_CENTER_VERTICAL)

        self.buttonsizer.AddStretchSpacer(1)
        self.buttonsizer.Add(self.okbutton)
        self.buttonsizer.Add(self.cancelbutton)
        self.namesizer = wx.BoxSizer(wx.HORIZONTAL)
        self.namesizer.Add(memname_label,0,wx.RIGHT|wx.ALIGN_CENTER_VERTICAL,7)
        self.namesizer.Add(self.memname_text,1,wx.EXPAND)
        self.mainsizer.Add(self.namesizer,0,wx.EXPAND|wx.ALL,7)
        self.mainsizer.Add(memtext_label,0,wx.LEFT|wx.TOP|wx.RIGHT,7)
        self.mainsizer.Add(self.memtext_text,1,wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM,7)
        # action buttons
        self.mainsizer.Add(self.buttonsizer2,0,wx.EXPAND|wx.LEFT|wx.RIGHT,7)
        # ok/cancel/etc. buttons
        self.mainsizer.Add(self.buttonsizer,0,wx.EXPAND|wx.ALL,7) 
        self.panel.SetSizer(self.mainsizer)
        self.memname_text.SetFocus()

        if sys.platform.startswith('win'):
            # for some strange reason, it needs this to trigger an event to
            # redraw sizers
            windim = self.GetSize()
            self.SetSize((windim[0]+1,windim[1]+1))
            self.SetSize((windim[0]-1,windim[1]-1))

    def OnOK(self, event):
        self.parent._saveWindowDimensions(self, self.windim_varname)
        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.parent._saveWindowDimensions(self, self.windim_varname)
        self.EndModal(wx.ID_CANCEL)

    def OnChanged(self, event):
        print "OnChanged()"

    def OnHelp(self, event):
        global website_url
        webbrowser.open(website_url + 'manual_textentry.html',new=2)

    def OnPartition(self, event):
        """ 
        The user would like us to auto-partition the text into sentence-like
        chunks for memorization. 
        """
        newtext='text goes here'
        self.memtext_text.SetValue(newtext)

    def getNearestPartition(self, txt, i):
        """
        Looks for the nearest end-of-partition character after the position i.
        """
        if i > len(txt): return len(txt)
        found = False

        start_pos = 0
        # partition on end of sentences, no commas
        re_eosentence = re.compile(r'[\.\?\!;\'\"]\s') 
        # partition w/ commas
        re_eosentence_wc = re.compile(r'[\.\?\!\)\],;\'\"]\s')
        re_obj = re_eosentence

        while not found: 
            mo = None
            mo = re_obj.search(txt, start_pos)
            if mo:
                # Okay, this is the next nearest one. We need to also find the
                # nearest one before and if that one is closer, return it
                # instead. 
                start_pos = mo.end(0) 
                if start_pos > i:
                    if start_pos >= i*3 and re_obj == re_eosentence:
                        # The text is too long. Introduce commas into the mix
                        # to see if we can possibly get a shorter chunk. If
                        # not, we still end up with this partition.
                        re_obj = re_eosentence_wc
                        start_pos = i*2
                    else:
                        found = True
                else:
                    pass
            else:
                # I guess we just append the rest of this string as a sentence,
                # since we are at the end and can not find another sentence
                # pattern.
                start_pos = len(txt)
                found = True
        return start_pos

#-------------------------------------------------------------------------------
cursor_stack = []
def popCursor(window):
    """ Restore cursor to previous one on the stack for this window. """
    global cursor_stack
    for i in range(0,len(cursor_stack)):
        if cursor_stack[i][0] == window:    
            cursor_obj = cursor_stack.pop(i)
            window.SetCursor(cursor_obj[1])
            return


def pushCursor(window, cursor_type):
    """ Set cursor for window by taking a cursor type (eg. wx.CURSOR_WAIT). """
    global cursor_stack
    oldcursor = window.GetCursor()
    cursor_stack.insert(0,(window,oldcursor))
    window.SetCursor(wx.StockCursor(cursor_type))


def launch():
    """ 
    Wrapper function to launch the application. This is necessary for the
    MacOSX platform so that the initial python file isn't exposed to the end
    user. 
    """
    app = CornerStoneApp(redirect=False,filename='app.log')
    app.MainLoop()

if __name__ == '__main__':
    launch()
    

