#!/usr/bin/python
# -*- coding: utf-8 -*-
Config_Font     = 'Monospace, Normal 11'
Config_TreeFont = 'Monospace, Normal 11'
Config_Width, Config_Height = (800, 800)

import sys, os.path
import datetime, re
import pygtk
pygtk.require('2.0')
import gtk,pango

class ExtendedTextBuffer(gtk.TextBuffer):
    def __init__(self):
        gtk.TextBuffer.__init__(self)
        self.resetUndo()
        self.insHandler = self.connect('insert-text',  self.onInsert )
        self.delHandler = self.connect('delete-range', self.onDelete )

        self.create_tag("header", pixels_below_lines = 5,
                        weight = pango.WEIGHT_ULTRABOLD, underline = pango.UNDERLINE_SINGLE )
        self.create_tag( "search",  foreground='#ff0000', background='#ffff00' )

        # Hiliting-Rules
        self.create_tag( "hilight", foreground='#000000', background='#ffccff' )
        self.create_tag( "comment", foreground='#008800' )
        self.create_tag( "comment2",foreground='#aaaaaa' )
        self.create_tag( "extract", foreground='#1111cc' )
        self.create_tag( "item",    weight = pango.WEIGHT_ULTRABOLD )
        self.hilightFormats = ((r"\[[^\]]*\]","hilight"),(r"^#.*","comment"),(r"^;.*","comment2"),
                               (r"^\>.*","extract"),(r"^-.*","item"))

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
        vbox.show()
        self.win.add(vbox)

        fromFld = gtk.Entry()
        fromFld.set_max_length(50)
        fromFld.show()
        vbox.pack_start(fromFld,True, True, 0 )

        toFld = gtk.Entry()
        toFld.set_max_length(50)
        toFld.show()
        vbox.pack_start(toFld,True, True, 0 )

        hbox = gtk.HBox(False,0)
        hbox.show()
        vbox.pack_start(hbox, True, True, 0 )

        skipBtn = gtk.Button("検索")
        def _search( w ):
            self.focus = search(fromFld.get_text(),1)
        skipBtn.connect("clicked", _search  )
        skipBtn.show()
        hbox.pack_start(skipBtn, True, True, 0 )

        replBtn = gtk.Button("置き換え")
        def _replace( w ):
            if self.focus != None:
                replace( self.focus, toFld.get_text() )
            self.focus = search(fromFld.get_text(),1)
        replBtn.connect("clicked", _replace  )
        replBtn.show()
        hbox.pack_start(replBtn, True, True, 0 )

        closeBtn = gtk.Button("閉じる")
        closeBtn.connect("clicked", lambda w: self.win.destroy() )
        closeBtn.show()
        hbox.pack_start(closeBtn, True, True, 0 )

        self.win.show()
        return 

class OutlineEditor:
    # ===== ファイルの操作
    def _setText2Buf( self, mode, itr, head, txt, attr ):
        if not mode: return

        store = self.TreeStore
        buf = ExtendedTextBuffer()
        buf.stopRec()
        buf.set_text(txt[:-1])
        buf.hilight()
        buf.connect("changed", self.textUpdated )
        buf.place_cursor(buf.get_start_iter())
        buf.startRec()
        head = head + " (%d)"% buf.get_line_count()
        last = store.append(itr, [head, buf, attr ] )
        return last

    def _deSerialize( self, fp, itr):
        store = self.TreeStore
        mode = False
        head = None
        txt  = ""
        attr = None
        last = None
        for line in fp:
            #if line == "\NewEntry\n":
            m = re.compile(r"\NewEntry(?: (.+))?").match(line,1)
            if m:
                last = self._setText2Buf( mode, itr, head, txt, attr )
                mode = True
                head = None
                txt  = ""
                attr = m.group(1)
            elif line == "\\NewFolder\n" :
                last = self._setText2Buf( mode, itr, head, txt, attr )
                mode = False
                self._deSerialize( fp, last )
            elif line == "\\EndFolder\n" :
                last = self._setText2Buf( mode, itr, head, txt, attr )
                mode = False
                return
            else:
                txt = txt + line
                if head == None: # 最初の行はエントリ名でもある
                    head = line[:-1]
        self._setText2Buf( mode, itr, head, txt, attr )

    def loadFile( self, fname ):
        store = self.TreeStore
        store.clear()
        itr = store.get_iter_root()
        fp = open( fname, 'r' )
        self._deSerialize( fp, itr )
        fp.close()
        self.TreeView.set_cursor( 0 )

    def _serialize( self, fp, itr ):
        if None == itr:
            return
        attr = self.TreeStore.get(itr,2)[0]
        if attr:
            fp.write( "\\NewEntry %s\n"%attr )
        else :
            fp.write( "\\NewEntry\n" )
        buf = self.TreeStore.get(itr,1)[0]
        fp.write( buf.get_start_iter().get_text(buf.get_end_iter() ) )
        fp.write( "\n" )
        store = self.TreeStore
        if store.iter_has_child(itr):
            fp.write( "\\NewFolder\n" )
            self._serialize( fp, store.iter_children(itr) )
            fp.write( "\\EndFolder\n" )
        self._serialize( fp, store.iter_next(itr) )

    def _saveFile( self ):
        fp = open( self.fileName, 'w' )
        itr = self.TreeStore.get_iter_root()
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
    def normalStatusBar(self):
        txtBuf = self.TextView.get_buffer()
        self.sbarMessage(" c:%d  l:%d " % (txtBuf.get_char_count(), txtBuf.get_line_count()) )
        # txtBuf.props.cursor_position

    def textUpdated(self, txtBuf ): # ツリータイトルのかきかえ
        (store, itr) = self.TreeView.get_selection().get_selected()
        if txtBuf.get_line_count() > 1:
            buf = txtBuf.get_start_iter().get_text( txtBuf.get_iter_at_line(1) )[:-1] 
        else:
            buf = txtBuf.get_start_iter().get_text( txtBuf.get_end_iter() )
        self.TreeStore.set_value(itr, 0, buf + " (%d)"%txtBuf.get_line_count() )
        self.normalStatusBar()
        self.changed = True
        txtBuf.hilight()

    # ===== ツリーの操作
    def rowSelected( self, treeView ): # for "cursor-changed"
        # なぜか、ここに二回来る…
        (store, itr) = treeView.get_selection().get_selected()

        buf = store.get(itr,1)[0]
        if buf == None: return
        self.TextView.set_buffer( buf )
        self.TextView.scroll_to_mark( buf.get_insert(), 0.3 )

        # 最初だけ失敗する。謎のエラーの模様.
        # http://stackoverflow.com/questions/7032233/mysterious-gobject-warning-assertion-g-is-object-object-failed

    def rowMoved( self, treeModel, path, itr ):
        # ツリーが並び替えられた場合フォーカスを与える
        # 移動をするとサブツリー含めて呼ばれてしまうので、結構うざったい
        self.TreeView.expand_to_path( path )
        self.TreeView.set_cursor( path )

    def sideScroll( self, treeView, event ):
        selection = treeView.get_selection()
        (store, itr) = selection.get_selected()
        if itr == None: return
        buf = store.get(itr,1)[0]
        if buf == None: return
        '''
        if event.direction == gtk.gdk.SCROLL_UP:
            itr = list.pop(-1)
            if itr != None:
                path = store.get_string_from_iter( itr )
                treeView.expand_to_path( path )
                treeView.set_cursor( path )
                ev = gtk.gdk.Event(gtk.gdk.KEY_PRESS)
                ev.keyval = gtk.keysyms.Up
                treeView.emit('key-press-event', ev )
                treeView.emit('key_press_event', ev )
        else:
            itr = list.pop(0)
            if itr != None:
                path = store.get_string_from_iter( itr )
                treeView.expand_to_path( path )
                treeView.set_cursor( path )
        '''
        list = self._getTreeIters( store, itr, -1 if event.direction == gtk.gdk.SCROLL_UP else 1 , False )
        list.pop(0)
        if len(list)>0:
            itr = list.pop(0)
            path = store.get_string_from_iter( itr )
            treeView.expand_to_path( path )
            treeView.set_cursor( path )

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
            self.saveAsDialog( widget )
            return
        self._saveFile()
        self.sbarMessage("ファイルを保存しました")

    def saveAsDialog( self, widget ):
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

    def openDocumentDialog(self, widget ):
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
        return [txt+" (1)", buf, None ]

    def addChild( self, widget ):
        (store, itr) = self.TreeView.get_selection().get_selected()
        store.append(itr, self._newItem() )
        self.changed = True

    def addItem( self, widget ):
        (store, itr) = self.TreeView.get_selection().get_selected()
        store.insert_after( None, itr, self._newItem() )
        self.changed = True

    def deleteItem( self, button ):
        (store, itr) = self.TreeView.get_selection().get_selected()
        cur = self.TreeView.get_cursor()[0]
        if cur[:-1] == ():
            c2 = (0,)
        else:
            if cur[-1] == 0:
                c2 = cur[:-1]
            else:
                c2 = cur[:-1]+(cur[-1]-1, )
        store.remove(itr)
        if store.get_iter_root() == None:
            self.addChild( button )
        self.TreeView.set_cursor(c2)
        self.changed = True

    # --- tree context menu
    def _addAttribute2Tree( self, menuItem, pos, atr ):
        itr = self.TreeStore.get_iter(pos[0])
        self.TreeStore.set_value( itr, 2, atr )
        self.changed = True
        
    def treeContextMenu( self, treeView, event ):
        if event.button == 3:
            pos = self.TreeView.get_path_at_pos( int(event.x), int(event.y) )
            if pos == None: return
            menu = gtk.Menu()

            item = gtk.MenuItem("Blue" )
            item.connect('activate', self._addAttribute2Tree, pos, '1' )
            menu.append(item)
            item = gtk.MenuItem("Green" )
            item.connect('activate', self._addAttribute2Tree, pos, '2' )
            menu.append(item)
            item = gtk.MenuItem("Red" )
            item.connect('activate', self._addAttribute2Tree, pos, '3' )
            menu.append(item)
            item = gtk.MenuItem("Normal" )
            item.connect('activate', self._addAttribute2Tree, pos, '0' )
            menu.append(item)

            menu.show_all()
            menu.popup(None,None,None,event.button,event.time)

    # ----- search
    # リストにある要素の一覧を返す
    def _getTreeIters( self, store, itr, dir, loop=True ):
        self.iList = []
        store.foreach( lambda m,p,i: self.iList.append(i) )
        if dir == -1: self.iList.reverse()
        while store.get_string_from_iter(itr) != store.get_string_from_iter(self.iList[0]): 
            i = self.iList.pop(0)
            if loop:
                self.iList.append(i)
        return self.iList

    def _search( self, str, dir ):
        selection = self.TreeView.get_selection()
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
                    path = self.TreeStore.get_string_from_iter( itr )
                    self.TreeView.set_cursor( path )
                    break
        start, end = i
        self.TextView.scroll_to_iter( start, 0.3 )
        return i

    def search( self, widget, entry, dir ):
        return self._search( entry.get_text(), dir )

    # ----- replace
    def _replace( self, itrs, str ):
        start, end = itrs
        self.TextView.get_buffer().delete( start, end )
        self.TextView.get_buffer().insert( start, str )
        return

    def replace(self,wid):
        p = ReplaceWindow( self._search, self._replace )

    # ----- Undo
    def undo( self, wid ):
        (store, itr) = self.TreeView.get_selection().get_selected()
        buf = store.get(itr,1)[0]
        buf.undo()

    def redo( self, wid ):
        (store, itr) = self.TreeView.get_selection().get_selected()
        buf = store.get(itr,1)[0]
        buf.redo()

    # --- output a message to the status bar
    def sbarMessage( self, msg ):
        self.StatusBar.pop( self.conID )
        self.StatusBar.push( self.conID, msg )

    # ===== 初期化
    def __init__(self):
        # vars
        self.fileName = None
        self.changed  = False

        # ===== main window
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.connect("delete_event", self.quitApl)
        self.window.set_size_request(Config_Width, Config_Height)

        # ===== vBox ( menu | tool | main | status )
        self.vBox = gtk.VBox(False,0)
        self.vBox.show()
        self.window.add(self.vBox)

        # ===== Menu Bar
        mBar    = gtk.MenuBar()
        self.vBox.add(mBar)
        self.vBox.set_child_packing(mBar, False,True,0,0)

        def _addImageMenuItem( menu, agr, stock, key, func ):
            i = gtk.ImageMenuItem( stock, agr )
            key, mod = gtk.accelerator_parse(key)
            i.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE )
            i.connect("activate", func )
            menu.append(i)

        agr = gtk.AccelGroup()
        self.window.add_accel_group(agr)

        fmi = gtk.MenuItem("_File" )
        mBar.append(fmi)
        menu  = gtk.Menu()
        _addImageMenuItem( menu, agr, gtk.STOCK_OPEN,    "<Control>O",        self.openDocumentDialog )
        _addImageMenuItem( menu, agr, gtk.STOCK_SAVE,    "<Control>S",        self.saveDocument )
        _addImageMenuItem( menu, agr, gtk.STOCK_SAVE_AS, "<Shift><Control>S", self.saveAsDialog )
        menu.append( gtk.SeparatorMenuItem() )
        _addImageMenuItem( menu, agr, gtk.STOCK_QUIT,    "<Control>Q",        self.quitApl )
        fmi.set_submenu(menu)

        fmi = gtk.MenuItem("_Edit" )
        mBar.append(fmi)
        menu  = gtk.Menu()
        _addImageMenuItem( menu, agr, "検索",    "<Control>R",   lambda s: self.findEntry.grab_focus() )
        _addImageMenuItem( menu, agr, "置換",    "<Shift><Control>R",     self.replace )
        menu.append( gtk.SeparatorMenuItem() )
        _addImageMenuItem( menu, agr, "Undo",    "<Control>Z",  self.undo )
        _addImageMenuItem( menu, agr, "Redo",    "<Shift><Control>Z",   self.redo )
        fmi.set_submenu(menu)

        # ===== tool bar
        self.toolbar = gtk.Toolbar()
        self.toolbar.show()
        self.vBox.add(self.toolbar)
        self.vBox.set_child_packing(self.toolbar, False,True,0,0)

        icon = gtk.image_new_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "Open File", None, icon, self.openDocumentDialog )

        icon = gtk.image_new_from_stock(gtk.STOCK_SAVE, gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "Save File", None, icon, self.saveDocument )
        self.toolbar.append_space()

        icon = gtk.image_new_from_stock(gtk.STOCK_NEW,  gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "New Entry", None, icon, self.addItem )

        icon = gtk.image_new_from_stock(gtk.STOCK_ADD,  gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "New Child", None, icon, self.addChild )
        self.toolbar.append_space()

        icon = gtk.image_new_from_stock(gtk.STOCK_DELETE, gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "Delete Entry",
                                 None, icon, self.deleteItem )
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
        self.findEntry = gtk.Entry()
        self.findEntry.connect("icon-press", lambda s, t, u : self.findEntry.set_text("") )
        self.findEntry.connect("activate", self.search, self.findEntry, 1 )
        self.findEntry.set_icon_from_stock( 1, gtk.STOCK_DELETE )
        self.findEntry.show()
        self.toolbar.append_widget(self.findEntry,  "Find String", "Private")

        icon = gtk.image_new_from_stock(gtk.STOCK_MEDIA_REWIND, gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "Search backward",
                                 None, icon, self.search, (self.findEntry, -1) )

        icon = gtk.image_new_from_stock(gtk.STOCK_MEDIA_FORWARD, gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "Search forward",
                                 None, icon, self.search, (self.findEntry, 1) )

        icon = gtk.image_new_from_stock(gtk.STOCK_FIND_AND_REPLACE, gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "Replace",
                                 None, icon, self.replace, None )

        # ===== Main area ( tree | text )
        self.hPane = gtk.HPaned()
        self.hPane.set_position( 200 )
        self.hPane.show()
        self.vBox.add(self.hPane)

        # ===== TreeStore / view / column
        self.TreeStore = gtk.TreeStore( str, ExtendedTextBuffer, str )
        self.TreeStore.append(None, self._newItem() )
        self.TreeStore.connect("row-changed", self.rowMoved )
        #self.TreeStore.connect("row-inserted", self.rowMoved2 )
        #self.tree.connect("unselect-all", self.rowMoved )

        # ===== TreeView
        self.TreeView = gtk.TreeView( self.TreeStore )
        self.TreeView.modify_font(pango.FontDescription(Config_TreeFont))
        self.TreeView.set_search_column(0)
        self.TreeView.set_reorderable(True)
        self.TreeView.connect("cursor-changed", self.rowSelected )
        self.TreeView.connect("button_press_event", self.treeContextMenu )
        self.TreeView.connect("scroll_event", self.sideScroll )
        self.TreeView.show()
        self.TreeView.set_cursor(0)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.connect( "scroll_event", lambda a,b: True ) # ホイールスクロールを無効化
        sw.show()
        sw.add(self.TreeView)
        self.hPane.add(sw)

        # ----- TreeViewColumn
        tvc  = gtk.TreeViewColumn('Entry 一覧')
        self.TreeView.append_column(tvc)

        cell = gtk.CellRendererPixbuf()
        tvc.pack_start(cell, False )
        icon = self.window.render_icon(gtk.STOCK_DND, gtk.ICON_SIZE_BUTTON)
        def _setTVPix( col, cell, model, itr ):
            cell.props.pixbuf = icon
        tvc.set_cell_data_func( cell, _setTVPix )

        cell = gtk.CellRendererText()
        tvc.pack_start(cell, False )
        def _setTVAttr( col, cell, model, itr ):
            colmap={ '0':'#000000', '1':'#0000ff', '2':'#006600', '3':'#ff0000' }
            cell.props.text = model.get(itr,0)[0]
            attr = model.get(itr,2 )[0]
            if attr == None:
                cell.props.foreground = 'black'
            else:
                cell.props.foreground = colmap[attr]
        tvc.set_cell_data_func( cell, _setTVAttr )

        # ===== TextView / area
        self.TextView = gtk.TextView( )
        self.TextView.modify_font(pango.FontDescription(Config_Font))
        self.TextView.connect("move-cursor", lambda a, b, c, d: self.normalStatusBar() )
        self.TextView.set_wrap_mode(gtk.WRAP_CHAR)
        self.TextView.set_border_width(3)
        self.TextView.show()

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)        
        sw.add(self.TextView)
        sw.show()
        self.hPane.add(sw)

        # ===== StatusBar
        self.StatusBar = gtk.Statusbar()
        self.StatusBar.show()

        self.vBox.add( self.StatusBar )
        self.vBox.set_child_packing(self.StatusBar, False,True,0,0)
        self.conID = self.StatusBar.get_context_id("Message")

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
                self.sbarMessage("ファイル %s をあらたにつくります。" % argvs[1])
            else:
                self.sbarMessage("ファイル名 %s は不適切です(ディレクトリなど)" % argvs[1])

        # ===== window
        self.window.show_all()

    def main(self):
        gtk.main()

if __name__ == "__main__":
    apl = OutlineEditor()
    apl.main()
