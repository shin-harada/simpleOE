#!/usr/bin/python
# -*- coding: utf-8 -*-
Config_Font  = 'Monospace, Normal 11'
Config_Width, Config_Height = (800, 800)

import sys, os.path
import datetime, re
import pygtk
pygtk.require('2.0')
import gtk,pango

class ExtendedTextBuffer(gtk.TextBuffer):
    def __init__(self):
        gtk.TextBuffer.__init__(self)
        self.create_tag("header", pixels_below_lines = 5,
                        weight = pango.WEIGHT_ULTRABOLD, underline = pango.UNDERLINE_SINGLE )
        self.create_tag( "search",  foreground='#ff0000', background='#ffff00' )
        self.insHandler = self.connect('insert-text',  self.onInsert )
        self.delHandler = self.connect('delete-range', self.onDelete )
        self.resetUndo()
        # Hiliting-Rules
        self.create_tag( "hilight", foreground='#000000', background='#ffccff' )
        self.create_tag( "comment", foreground='#008800' )
        self.create_tag( "comment2",foreground='#aaaaaa' )
        self.hilightFormats = ((r"\[.*\]","hilight"),(r"^#.*","comment"),(r"^;.*","comment2"))

    # Hilight
    def hilight( self ):
        buf = self.get_start_iter().get_text( self.get_end_iter() )

        first, last = self.get_bounds()
        self.remove_tag_by_name("header", first, last )
        res = re.compile(r"^.*").match( buf )
        self.apply_tag_by_name( "header",
                                self.get_iter_at_offset(res.start()),
                                self.get_iter_at_offset(res.end() ))

        for f in self.hilightFormats:
            self.remove_tag_by_name(f[1], first, last )
            for res in re.compile( f[0], re.M ).finditer(buf):
                self.apply_tag_by_name( f[1],
                                        self.get_iter_at_offset(res.start()),
                                        self.get_iter_at_offset(res.end() ))

    # SEARCH
    def search( self, key, dir, head = False ):
        if key == None or key == "": return None
        first, last = self.get_bounds()
        self.remove_tag_by_name( "search", first, last )

        if head:
            if dir > 0:
                cur = self.get_start_iter()
            else:
                cur = self.get_end_iter()
        else:
            cur = self.get_iter_at_mark( self.get_insert() )

        if dir > 0 :
            r = cur.forward_search( key, gtk.TEXT_SEARCH_TEXT_ONLY )
        else:
            r = cur.backward_search( key, gtk.TEXT_SEARCH_TEXT_ONLY )
        if r == None : return None
        start, end = r
        self.apply_tag_by_name( "search", start, end )
        if dir > 0:
            self.place_cursor(end)
        else:
            self.place_cursor(start)
        return r

    # UNDO
    def onInsert( self, buf, start, txt, length ):
        self.pushUndo( "i", start.get_offset(), start.get_offset()+len(unicode(txt,'utf-8')), txt )

    def onDelete( self, buf, start, end ):
        self.pushUndo( "d", start.get_offset(), end.get_offset(), self.get_text( start, end ) )

    def startRec( self ):
        self.handler_unblock(self.insHandler)
        self.handler_unblock(self.delHandler)

    def stopRec( self ):
        self.handler_block(self.insHandler)
        self.handler_block(self.delHandler)

    def resetUndo( self ):
        self.undoStack = []
        self.redoStack = []

    def pushUndo( self, op, start, end, text ):
        self.redoStack = []
        if len(self.undoStack) > 0:
            cmd = self.undoStack[-1]
            if op == 'i' and cmd[0] == op and cmd[2] == start:
                self.undoStack[-1] = ( op, cmd[1], end, cmd[3]+text )
            elif op == 'd' and cmd[0] == op and end == cmd[1]:   # Backspace
                self.undoStack[-1] = ( op, start, cmd[2], text+cmd[3] )
            elif op == 'd' and cmd[0] == op and cmd[1] == start: # Delete
                self.undoStack[-1] = ( op, cmd[1], end, cmd[3]+text )
            else:
                self.undoStack.append( ( op ,start, end, text ) )
        else:
            self.undoStack.append( ( op ,start, end, text ) )

    def undo( self ):
        if len(self.undoStack) == 0: return
        cmd = self.undoStack.pop()
        self.redoStack.append( cmd )
        self.stopRec()
        if cmd[0] == 'i':
            self.delete( self.get_iter_at_offset(cmd[1]), self.get_iter_at_offset(cmd[2]) )
        else:
            self.insert( self.get_iter_at_offset(cmd[1]), cmd[3] )
        self.startRec()

    def redo( self ):
        if len(self.redoStack) == 0: return
        cmd = self.redoStack.pop()
        self.undoStack.append( cmd )
        self.stopRec()
        if cmd[0] == 'i':
            self.insert( self.get_iter_at_offset(cmd[1]), cmd[3] )
        else:
            self.delete( self.get_iter_at_offset(cmd[1]), self.get_iter_at_offset(cmd[2]) )
        self.startRec()

class ReplaceWindow:
    def keyPress( self, wid, evnt ):
        if evnt.keyval == gtk.keysyms.Escape:
            self.win.destroy()

    def __init__(self, search, replace ):
        self.focus = None

        self.win = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.win.connect("delete_event", lambda w,e: self.win.destroy() )
        self.win.set_modal(gtk.DIALOG_MODAL)
        self.win.set_border_width(10)
        self.win.connect("key-press-event", self.keyPress )

        vbox = gtk.VBox(False,0)
        self.win.add(vbox)
        vbox.show()

        fromFld = gtk.Entry()
        fromFld.set_max_length(50)
        vbox.pack_start(fromFld,True, True, 0 )
        fromFld.show()

        toFld = gtk.Entry()
        toFld.set_max_length(50)
        vbox.pack_start(toFld,True, True, 0 )
        toFld.show()

        hbox = gtk.HBox(False,0)
        vbox.pack_start(hbox, True, True, 0 )
        hbox.show()

        skipBtn = gtk.Button("検索")
        def _search( w ):
            self.focus = search(fromFld.get_text(),1)
        skipBtn.connect("clicked", _search  )
        hbox.pack_start(skipBtn, True, True, 0 )
        skipBtn.show()

        replBtn = gtk.Button("置き換え")
        def _replace( w ):
            if self.focus != None:
                replace( self.focus, toFld.get_text() )
            self.focus = search(fromFld.get_text(),1)
        replBtn.connect("clicked", _replace  )
        hbox.pack_start(replBtn, True, True, 0 )
        replBtn.show()

        closeBtn = gtk.Button("閉じる")
        closeBtn.connect("clicked", lambda w: self.win.destroy() )
        hbox.pack_start(closeBtn, True, True, 0 )
        closeBtn.show()

        self.win.show()
        return 

class OutlineEditor:
    # ===== ファイルの操作
    def _setText2Buf( self, mode, itr, head, txt ):
        if not mode: return

        store = self.treeStore
        buf = ExtendedTextBuffer()
        buf.stopRec()
        buf.set_text(txt[:-1])
        buf.hilight()
        buf.connect("changed", self.textUpdated )
        buf.place_cursor(buf.get_start_iter())
        buf.startRec()
        icon = self.window.render_icon(gtk.STOCK_DND, gtk.ICON_SIZE_BUTTON)
        head = head + " (%d)"% buf.get_line_count()
        last = store.append(itr, [head, buf, icon ] )
        return last

    def _deSerial( self, fp, itr):
        store = self.treeStore
        mode = False
        head = None
        txt  = ""
        last = None
        for line in fp:
            if line == "\\NewEntry\n":
                last = self._setText2Buf( mode, itr, head, txt )
                mode = True
                txt  = ""
                head = None
            elif line == "\\NewFolder\n" :
                last = self._setText2Buf( mode, itr, head, txt )
                mode = False
                self._deSerial( fp, last )
            elif line == "\\EndFolder\n" :
                last = self._setText2Buf( mode, itr, head, txt )
                mode = False
                return
            else:
                txt = txt + line
                if head == None: # 最初の行はエントリ名でもある
                    head = line[:-1]
        self._setText2Buf( mode, itr, head, txt )

    def loadFile( self, fname ):
        store = self.treeStore
        store.clear()
        itr = store.get_iter_root()
        fp = open( fname, 'r' )
        self._deSerial( fp, itr )
        fp.close()
        self.tree.set_cursor( 0 )

    def _serialize( self, fp, itr ):
        if None == itr:
            return
        fp.write( "\\NewEntry\n" )
        buf = self.treeStore.get(itr,1)[0]
        fp.write( buf.get_start_iter().get_text(buf.get_end_iter() ) )
        fp.write( "\n" )
        store = self.treeStore
        if store.iter_has_child(itr):
            fp.write( "\\NewFolder\n" )
            self._serialize( fp, store.iter_children(itr) )
            fp.write( "\\EndFolder\n" )
        self._serialize( fp, store.iter_next(itr) )

    def _saveFile( self ):
        fp = open( self.fileName, 'w' )
        itr = self.treeStore.get_iter_root()
        self._serialize( fp,itr ) 
        fp.close
        self.changed = False

    '''
    # ----- Printer
    def _printText( self, op, context, pageNo ):
        plo = context.create_pango_layout("") 
        plo.set_text( "ここでテキストを書き込む" )
        # ここのpango layout でフォーマットすれば良い？？
        # どうも、ページ単位でフォーマットしないといけない模様…？

        cCtxt = context.get_cairo_context()
        cCtxt.show_layout( plo )

    def printOperation( self ):
        pOp = gtk.PrintOperation()
        pOp.set_n_pages(1)
        pOp.connect("draw_page", self._printText )
        pOp.run( gtk.PRINT_OPERATION_ACTION_PRINT_DIALOG, None )
        '''

    # ===== テキストの操作
    def textUpdated(self, txtBuf ): # ツリータイトルのかきかえ
        (store, itr) = self.tree.get_selection().get_selected()
        if txtBuf.get_line_count() > 1:
            buf = txtBuf.get_start_iter().get_text( txtBuf.get_iter_at_line(1) )[:-1] 
        else:
            buf = txtBuf.get_start_iter().get_text( txtBuf.get_end_iter() )
        self.treeStore.set_value(itr, 0, buf + " (%d)"%txtBuf.get_line_count() )
        self.changed = True
        self.sbarMessage(" c:%d  l:%d " % (txtBuf.get_char_count(), txtBuf.get_line_count() ) )
        txtBuf.hilight()

    # ===== ツリーの操作
    def rowSelected( self, treeView, textView ): # for "cursor-changed"
        # なぜか、ここに二回来る…
        (store, itr) = treeView.get_selection().get_selected()

        buf = store.get(itr,1)[0]
        if buf == None: return
        textView.set_buffer( buf )
        self.text.scroll_to_mark( buf.get_insert(), 0.3 )

        # 最初だけ失敗する。謎のエラーの模様.
        # http://stackoverflow.com/questions/7032233/mysterious-gobject-warning-assertion-g-is-object-object-failed

    def rowMoved( self, treeModel, path, itr ):
        # ツリーが並び替えられた場合フォーカスを与える
        # 移動をするとサブツリー含めて呼ばれてしまうので、結構うざったい
        self.tree.expand_to_path( path )
        self.tree.set_cursor( path )

    # ===== ツールバー
    def quitApl(self, widget, data=None):
        if self.changed :
            dlg = gtk.MessageDialog( None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                     gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO,
                                     "保存していないデータがあります。本当に終了しますか？")
            if gtk.RESPONSE_YES != dlg.run():
                dlg.destroy()
                return True
        gtk.main_quit()

    def saveDocument( self, widget ):
        if self.fileName == None:
            self.saveAsDlg( widget )
            return
        self._saveFile()
        self.sbarMessage("ファイルを保存しました")

    def saveAsDlg( self, widget ):
        dlg = gtk.FileSelection("Save As")
        dlg.ok_button.connect("clicked", lambda s : dlg.response(gtk.RESPONSE_OK) )
        dlg.cancel_button.connect("clicked", lambda s: dlg.response(gtk.RESPONSE_CANCEL) )
        if dlg.run() != gtk.RESPONSE_OK:
            dlg.destroy()
            return
        fn = dlg.get_filename()
        dlg.destroy()
        print fn
        if os.path.isdir(fn): # ディレクトリの場合
            # self.sbar.push( self.sbar.get_context_id("menu"), "ディレクトリです。保存はされませんでした。" )
            dlg = gtk.MessageDialog( None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                     gtk.MESSAGE_QUESTION,
                                     gtk.BUTTONS_OK,  "ディレクトリです。保存はされませんでした。")
            dlg.run()
            dlg.destroy()
            return
        if os.path.isfile(fn): # 既存ファイルの場合
            dlg = gtk.MessageDialog( None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                     gtk.MESSAGE_QUESTION,
                                     gtk.BUTTONS_YES_NO,  "すでにファイルがあります。上書きしますか？")
            if gtk.RESPONSE_YES != dlg.run():
                dlg.destroy()
                return True
            dlg.destroy()
        self.fileName = fn
        self.window.set_title(self.fileName+" - simpleOE")
        self._saveFile()
        return

    def openDocumentDlg(self, widget ):
        dlg = gtk.FileSelection("Open Document")
        dlg.ok_button.connect("clicked", lambda s : dlg.response(gtk.RESPONSE_OK) )
        dlg.cancel_button.connect("clicked", lambda s: dlg.response(gtk.RESPONSE_CANCEL) )
        if dlg.run() == gtk.RESPONSE_OK:
            fn = dlg.get_filename()
            dlg.destroy()
            if not os.path.isfile(fn ):
                dlg = gtk.MessageDialog( None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                         gtk.MESSAGE_QUESTION,
                                         gtk.BUTTONS_OK,  "そのようなファイルはありません。")
                dlg.run()
                dlg.destroy()
                return
            self.fileName = fn
            self.loadFile( self.fileName )
            self.window.set_title(self.fileName+" - simpleOE")
        else:
            dlg.destroy()

    # ----- ツリーの操作
    def _newItem( self ):
        buf = ExtendedTextBuffer();
        d = datetime.datetime.today()
        txt = '%s/%s/%s' % (d.year, d.month, d.day)
        buf.set_text(txt)
        buf.connect("changed", self.textUpdated )
        buf.hilight()
        icon = self.window.render_icon(gtk.STOCK_DND, gtk.ICON_SIZE_BUTTON)
        return [txt+" (1)", buf, icon ]

    def addChild( self, widget, treeView ):
        selection = treeView.get_selection()
        (store, itr) = selection.get_selected()
        store.append(itr, self._newItem() )
        self.changed = True

    def addItem( self, widget, treeView ):
        selection = treeView.get_selection()
        (store, itr) = selection.get_selected()
        par = store.iter_parent(itr)
        #store.append(par, self._newItem() )
        store.insert_after( None, itr, self._newItem() )
        self.changed = True


    def deleteItem( self, button, treeView ):
        selection = treeView.get_selection()
        (store, itr) = selection.get_selected()
        cur = treeView.get_cursor()[0]
        if cur[:-1] == ():
            c2 = (0,)
        else:
            if cur[-1] == 0:
                c2 = cur[:-1]
            else:
                c2 = cur[:-1]+(cur[-1]-1, )
        store.remove(itr)
        if store.get_iter_root() == None:
            self.addChild( button, treeView )
        self.tree.set_cursor(c2)
        self.changed = True

    # ----- search
    def _getTreeIters( self, store, itr, dir ):
        self.iList = []
        store.foreach( lambda m,p,i: self.iList.append(i) )
        if dir == -1: self.iList.reverse()
        while store.get_string_from_iter(itr) != store.get_string_from_iter(self.iList[0]): 
            i = self.iList.pop(0)
            self.iList.append(i)
        return self.iList

    def _search( self, str, dir ):
        selection = self.tree.get_selection()
        (store, itr) = selection.get_selected()
        buf = store.get(itr,1)[0]

        i = buf.search( str, dir )
        if None == i:
            list = self._getTreeIters( store, itr, dir )
            itr = list.pop(0)
            while True:
                if len(list) == 0:
                    self.sbarMessage("「%s」は、みつかりませんでした。" % str )
                    return None
                itr = list.pop(0)
                buf = store.get(itr,1)[0]
                i = buf.search( str, dir, True )
                if i != None:
                    path = self.treeStore.get_string_from_iter( itr )
                    self.tree.set_cursor( path )
                    break
        start, end = i
        self.text.scroll_to_iter( start, 0.3 )
        return i

    def search( self, widget, entry, dir ):
        return self._search( entry.get_text(), dir )

    # ----- replace
    def _replace( self, itrs, str ):
        start, end = itrs
        self.text.get_buffer().delete( start, end )
        self.text.get_buffer().insert( start, str )
        return

    def replace(self,wid):
        p = ReplaceWindow( self._search, self._replace )

    # ----- Undo
    def undo( self, wid ):
        selection = self.tree.get_selection()
        (store, itr) = selection.get_selected()
        buf = store.get(itr,1)[0]
        buf.undo()

    def redo( self, wid ):
        selection = self.tree.get_selection()
        (store, itr) = selection.get_selected()
        buf = store.get(itr,1)[0]
        buf.redo()

    # --- output a message to status bar
    def sbarMessage( self, msg ):
        self.sbar.pop( self.conID )
        self.sbar.push( self.conID, msg )

    # ===== 初期化
    def __init__(self):
        # vars
        self.fileName = None
        self.changed  = False

        # main window
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.connect("delete_event", self.quitApl)
        #self.window.set_usize(Config_Width, Config_Height)
        self.window.set_size_request(Config_Width, Config_Height)

        # vBox ( menu | tool | main | status )
        self.vBox = gtk.VBox(False,0)
        self.window.add(self.vBox)
        self.vBox.show()

        # Menu Bar
        mb    = gtk.MenuBar()
        self.vBox.add(mb)
        self.vBox.set_child_packing(mb, False,True,0,0)

        agr = gtk.AccelGroup()
        self.window.add_accel_group(agr)

        menu  = gtk.Menu()
        fmi = gtk.MenuItem("_File" )
        fmi.set_submenu(menu)
        mb.append(fmi)

        def addImageMenuItem( menu, agr, stock, key, func ):
            i   = gtk.ImageMenuItem( stock, agr )
            key, mod = gtk.accelerator_parse(key)
            i.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE )
            i.connect("activate", func )
            menu.append(i)

        addImageMenuItem( menu, agr, gtk.STOCK_OPEN,    "<Control>O",        self.openDocumentDlg )
        addImageMenuItem( menu, agr, gtk.STOCK_SAVE,    "<Control>S",        self.saveDocument )
        addImageMenuItem( menu, agr, gtk.STOCK_SAVE_AS, "<Shift><Control>S", self.saveAsDlg )
        menu.append( gtk.SeparatorMenuItem() )
        addImageMenuItem( menu, agr, gtk.STOCK_QUIT,    "<Control>Q",        self.quitApl )

        menu  = gtk.Menu()
        fmi = gtk.MenuItem("_Edit" )
        fmi.set_submenu(menu)
        mb.append(fmi)
        addImageMenuItem( menu, agr, "検索",    "<Control>R",   lambda s: self.findEntry.grab_focus() )
        addImageMenuItem( menu, agr, "置換",    "<Shift><Control>R",     self.replace )
        menu.append( gtk.SeparatorMenuItem() )
        addImageMenuItem( menu, agr, "Undo",    "<Control>Z",  self.undo )
        addImageMenuItem( menu, agr, "Redo",    "<Shift><Control>Z",   self.redo )

        # tool bar
        self.toolbar = gtk.Toolbar()
        self.vBox.add(self.toolbar)
        self.vBox.set_child_packing(self.toolbar, False,True,0,0)
        self.toolbar.show()

        # ===== Main area ( tree | text )
        self.hPane = gtk.HPaned()
        self.vBox.add(self.hPane)
        self.hPane.set_position( 200 )
        self.hPane.show()

        # text view
        self.text = gtk.TextView( )
        self.text.modify_font(pango.FontDescription(Config_Font))

        # tree store
        self.treeStore = gtk.TreeStore( str, ExtendedTextBuffer, gtk.gdk.Pixbuf )
        last = self.treeStore.append(None, self._newItem() )

        # tree view
        self.tree = gtk.TreeView( self.treeStore )
        self.tree.connect("cursor-changed", self.rowSelected, self.text )

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.show()
        sw.add(self.tree)
        self.hPane.add(sw)

        # create the TreeViewColumn to display the data
        tvcolumn = gtk.TreeViewColumn('Entry 一覧')
        self.tree.append_column(tvcolumn)

        pix = gtk.CellRendererPixbuf()
        tvcolumn.pack_start(pix, False)
        tvcolumn.add_attribute(pix,'pixbuf',2)

        cell = gtk.CellRendererText()
        tvcolumn.pack_start(cell, True)
        tvcolumn.add_attribute(cell, 'text', 0)
 
        self.tree.set_search_column(0)
        self.tree.set_reorderable(True)
        self.tree.set_cursor(0)
        self.tree.show()

        self.treeStore.connect("row-changed", self.rowMoved )
        #self.treeStore.connect("row-inserted", self.rowMoved2 )
        #self.tree.connect("unselect-all", self.rowMoved )

        # ===== text area
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)        
        sw.show()
        self.hPane.add(sw)
        self.text.set_wrap_mode(gtk.WRAP_CHAR)
        self.text.set_border_width(3)
        self.text.show()
        sw.add(self.text)

        # ----- tool bar
        icon = gtk.image_new_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "Open File", None, icon, self.openDocumentDlg )

        icon = gtk.image_new_from_stock(gtk.STOCK_SAVE, gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "Save File", None, icon, self.saveDocument )
        self.toolbar.append_space()

        icon = gtk.image_new_from_stock(gtk.STOCK_NEW,  gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "New Entry", None, icon, self.addItem,    self.tree )

        icon = gtk.image_new_from_stock(gtk.STOCK_ADD,  gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "New Child", None, icon, self.addChild,   self.tree )
        self.toolbar.append_space()

        icon = gtk.image_new_from_stock(gtk.STOCK_DELETE, gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "Delete Entry",
                                 None, icon, self.deleteItem, self.tree )
        self.toolbar.append_space()

        '''
        icon = gtk.image_new_from_stock(gtk.STOCK_GOTO_LAST, gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "Expand",
                                 None, icon, None,None )

        icon = gtk.image_new_from_stock(gtk.STOCK_GOTO_FIRST, gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "Collapse",
                                 None, icon, None,None )
                                 '''
        # search box
        icon = gtk.image_new_from_stock(gtk.STOCK_CLEAR, gtk.ICON_SIZE_BUTTON)
        self.findEntry = gtk.Entry()
        self.findEntry.connect("icon-press", lambda s, t, u : self.findEntry.set_text("") )
        self.findEntry.connect("activate", self.search, self.findEntry, 1 )
        self.toolbar.append_widget(self.findEntry,  "Find String", "Private")
        self.findEntry.set_icon_from_stock( 1, gtk.STOCK_DELETE )
        self.findEntry.show()

        icon = gtk.image_new_from_stock(gtk.STOCK_MEDIA_REWIND, gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "Search backward",
                                 None, icon, self.search, (self.findEntry, -1) )

        icon = gtk.image_new_from_stock(gtk.STOCK_MEDIA_FORWARD, gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "Search forward",
                                 None, icon, self.search, (self.findEntry, 1) )

        icon = gtk.image_new_from_stock(gtk.STOCK_FIND_AND_REPLACE, gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "Replace",
                                 None, icon, self.replace, None )

        # ===== status bar
        self.sbar = gtk.Statusbar()
        self.vBox.add(self.sbar)
        self.vBox.set_child_packing(self.sbar, False,True,0,0)
        self.sbar.show()
        self.conID = self.sbar.get_context_id("Message")

        # ==== argv 
        argvs = sys.argv
        if len(argvs) > 1:
            if os.path.isfile( argvs[1] ):
                self.loadFile( argvs[1] )
                self.fileName = argvs[1]
                self.window.set_title(self.fileName + " - simpleOE")
            elif not os.path.exists( argvs[1] ):
                self.fileName = argvs[1]
                self.window.set_title(self.fileName + " - simpleOE")
            else:
                self.sbarMessage("ファイル名"+argvs[1]+"は不適切です(ディレクトリなど)")

        # ===== window
        self.window.show_all()

    def main(self):
        gtk.main()

if __name__ == "__main__":
    apl = OutlineEditor()
    apl.main()
