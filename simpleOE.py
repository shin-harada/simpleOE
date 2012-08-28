#!/usr/bin/python
# -*- coding: utf-8 -*-
Config_Font  = 'Monospace, Normal 11'
Config_Width, Config_Height = (800, 800)


import os.path
import pygtk
pygtk.require('2.0')
import gtk,pango

class ExtendedTextBuffer(gtk.TextBuffer):
    def __init__(self):
        gtk.TextBuffer.__init__(self)
        self.searchTag = self.create_tag( foreground='#ff0000', background='#ffff00' )

    def search( self, key, dir, head = False ):
        if key == None or key == "": return
        first, last = self.get_bounds()
        self.remove_tag( self.searchTag, first, last )

        if head: 
            cur = self.get_start_iter()
        else:
            cur = self.get_iter_at_mark( self.get_insert() ) # カーソル位置

        if dir > 0 :
            r = cur.forward_search( key, gtk.TEXT_SEARCH_TEXT_ONLY )
        else:
            r = cur.backward_search( key, gtk.TEXT_SEARCH_TEXT_ONLY )
        if r == None : return False
        start, end = r
        self.apply_tag( self.searchTag, start, end )
        if dir > 0:
            self.place_cursor(end)
        else:
            self.place_cursor(start)
        return True

class outlineEditor:
    # ===== ファイルの操作
    def setText2Buf( self, mode, itr, head, txt ):
        if not mode: return
        store = self.treeStore

        buf = ExtendedTextBuffer()
        buf.set_text(txt)
        last = store.append(itr, [head, buf ] )
        buf.connect("changed", self.textUpdated )
        return last

    def deSerial( self, fp, itr):
        store = self.treeStore
        mode = False
        head = None
        txt  = ""
        last = None
        for line in fp:
            if line == "\\NewEntry\n":
                last = self.setText2Buf( mode, itr, head, txt )
                mode = True
                txt  = ""
                head = None
            elif line == "\\NewFolder\n" :
                last = self.setText2Buf( mode, itr, head, txt )
                mode = False
                self.deSerial( fp, last )
            elif line == "\\EndFolder\n" :
                last = self.setText2Buf( mode, itr, head, txt )
                mode = False
                return
            else:
                txt = txt + line
                if head == None: # 最初の行はエントリ名でもある
                    head = line[:-1]
        self.setText2Buf( mode, itr, head, txt )

    def loadFile( self, fname ):
        store = self.treeStore
        store.clear()
        itr = store.get_iter_root()
        fp = open( fname, 'r' )
        self.deSerial( fp, itr )
        fp.close()
        self.tree.set_cursor( 0 )

    def serialize( self, fp, itr ):
        if None == itr:
            return
        fp.write( "\\NewEntry\n" )
        buf = self.treeStore.get(itr,1)[0]
        fp.write( buf.get_start_iter().get_text(buf.get_end_iter() ) )
        fp.write( "\n" )
        store = self.treeStore
        if store.iter_has_child(itr):
            fp.write( "\\NewFolder\n" )
            self.serialize( fp, store.iter_children(itr) )
            fp.write( "\\EndFolder\n" )
        self.serialize( fp, store.iter_next(itr) )

    def saveFile( self ):
        fp = open( self.fileName, 'w' )
        itr = self.treeStore.get_iter_root()
        self.serialize( fp,itr ) 
        fp.close
        self.changed = False

    # ===== テキストの操作
    def textUpdated(self, wid ): # ツリータイトルのかきかえ
        # ノードを移動すると、イテレータが並び替えで無効になるので、記録したものを利用
        itr = self.cursor
        treeStore = self.treeStore
        if wid.get_line_count() > 1:
            treeStore.set_value(itr, 0, wid.get_start_iter().get_text( wid.get_iter_at_line(1) )[:-1] )
        else:
            treeStore.set_value(itr, 0, wid.get_start_iter().get_text( wid.get_end_iter() ) )
        self.changed = True

    # ===== ツリーの操作
    def rowSelected( self, treeView, textView ): # for "cursor-changed"
        # なぜか、ここに二回来る…
        selection = treeView.get_selection()
        (store, itr) = selection.get_selected()
        textView.set_buffer( store.get(itr,1)[0] )
        # 最初だけ失敗する。謎のエラーの模様.
        # http://stackoverflow.com/questions/7032233/mysterious-gobject-warning-assertion-g-is-object-object-failed
        self.cursor = itr

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
        self.saveFile()

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
        self.window.set_title(self.fileName)
        self.saveFile()
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
            self.window.set_title(self.fileName)
            self.loadFile( self.fileName )
        else:
            dlg.destroy()

    def addChild( self, widget, treeView ):
        selection = treeView.get_selection()
        (store, itr) = selection.get_selected()

        buf = ExtendedTextBuffer();
        buf.set_text("New Item")
        last = store.append(itr, ["New Item", buf ] )
        buf.connect("changed", self.textUpdated )
        self.changed = True

    def addItem( self, widget, treeView ):
        selection = treeView.get_selection()
        (store, itr) = selection.get_selected()
        par = store.iter_parent(itr)

        buf = ExtendedTextBuffer();
        buf.set_text("New Item")
        last = store.append(par, ["New Item", buf ] )
        buf.connect("changed", self.textUpdated )
        self.changed = True

    def deleteItem( self, button, treeView ):
        selection = treeView.get_selection()
        (store, itr) = selection.get_selected()
        cur = treeView.get_cursor()[0][0] -1
        if cur < 0 :  cur = 0
        if store.remove(itr) == 0:
            self.addChild( button, treeView )
        self.tree.set_cursor(cur)
        self.changed = True

    def search( self, widget, entry, dir ): # Entry
        selection = self.tree.get_selection()
        (store, itr) = selection.get_selected()

        buf = store.get(itr,1)[0]
        buf.search( entry.get_text(), dir )
        '''
        # 次のノードも検索するようにするには…
        i = itr
        while i != None :
            buf = store.get(i,1)[0]
            if buf.search( entry.get_text(), dir ):
                self.text.set_buffer( store.get(i,1)[0] )
                self.tree.set_cursor( store.get_path(i) )
                return

            i2 = store.iter_children(i)
            if i2 != None:
                i = i2
                continue
            i2 = store.iter_next(i)
            if i2 != None:
                i = i2
                continue
            i2 = store.iter_parent(i)
            if i2 == None:
                return
            i = store.iter_next(i2) # ここで 頭から探さないと...
            # ぎゃ。iter_prev は無いとか…。
        '''

    # ---
    def addImageMenuItem( self, menu, agr, stock, key, func ):
        i   = gtk.ImageMenuItem( stock, agr )
        key, mod = gtk.accelerator_parse(key)
        i.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE )
        i.connect("activate", func )
        menu.append(i)

    # ===== 初期化
    def __init__(self):
        # vars
        self.fileName = None
        self.changed  = False
        self.cursor   =  None

        # main window
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.connect("delete_event", self.quitApl)
        self.window.set_usize(Config_Width, Config_Height)

        self.text = gtk.TextView( )
        self.text.modify_font(pango.FontDescription(Config_Font))

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

        self.addImageMenuItem( menu, agr, gtk.STOCK_OPEN,    "<Control>O",        self.openDocumentDlg )
        self.addImageMenuItem( menu, agr, gtk.STOCK_SAVE,    "<Control>S",        self.saveDocument )
        self.addImageMenuItem( menu, agr, gtk.STOCK_SAVE_AS, "<Shift><Control>S", self.saveAsDlg )
        menu.append( gtk.SeparatorMenuItem() )
        self.addImageMenuItem( menu, agr, gtk.STOCK_QUIT,    "<Control>Q",        self.quitApl )

        menu  = gtk.Menu()
        fmi = gtk.MenuItem("_Edit" )
        fmi.set_submenu(menu)
        mb.append(fmi)

        self.addImageMenuItem( menu, agr, gtk.STOCK_FIND,    "<Control>F",       lambda s: self.findEntry.grab_focus() )

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

        # ===== tree store
        self.treeStore = gtk.TreeStore(str,ExtendedTextBuffer)

        buf = ExtendedTextBuffer()
        buf.set_text("New Item")
        last = self.treeStore.append(None,["New Item", buf ] )
        buf.connect("changed", self.textUpdated )

        # tree view
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)        
        sw.show()
        self.hPane.add(sw)
        self.tree = gtk.TreeView( self.treeStore )
        self.tree.connect("cursor-changed", self.rowSelected, self.text )
        sw.add(self.tree)

        # create the TreeViewColumn to display the data
        self.tvcolumn = gtk.TreeViewColumn('')

        self.tree.append_column(self.tvcolumn)
        self.cell = gtk.CellRendererText()
        self.tvcolumn.pack_start(self.cell, True)

        # set the cell "text" attribute to column 0 - retrieve text
        # from that column in treeStore
        self.tvcolumn.add_attribute(self.cell, 'text', 0)
   
        self.tree.set_search_column(0)
        self.tree.set_reorderable(True)
        self.tree.set_cursor(0)
        self.tree.show()
        self.treeStore.connect("row-changed", self.rowMoved )
        #self.treeStore.connect("row-inserted", self.rowMoved2 )
        #self.tree.connect("unselect-all", self.rowMoved )

        # ===== text area
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)        
        sw.show()
        self.hPane.add(sw)
        self.text.set_wrap_mode(gtk.WRAP_CHAR)
        self.text.set_border_width(3)
        self.text.show()
        sw.add(self.text)

        # ----- tool bar
        icon = gtk.image_new_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "Open",
                                 None, icon, self.openDocumentDlg )

        icon = gtk.image_new_from_stock(gtk.STOCK_SAVE, gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "Save",
                                 None, icon, self.saveDocument )

        icon = gtk.image_new_from_stock(gtk.STOCK_SAVE_AS, gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "SaveAs",
                                 None, icon, self.saveAsDlg )

        self.toolbar.append_space()

        icon = gtk.image_new_from_stock(gtk.STOCK_NEW,  gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "New Entry",
                                 None, icon, self.addItem,    self.tree )

        icon = gtk.image_new_from_stock(gtk.STOCK_ADD,  gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "New Child",                                                              
                                 None, icon, self.addChild,   self.tree )
        self.toolbar.append_space()

        icon = gtk.image_new_from_stock(gtk.STOCK_DELETE, gtk.ICON_SIZE_BUTTON)
        self.toolbar.append_item(None, "delete",
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

        # ===== status bar
        self.sbar = gtk.Statusbar()
        self.vBox.add(self.sbar)
        self.vBox.set_child_packing(self.sbar, False,True,0,0)
        self.sbar.show()

        # and the window
        self.window.show_all()

    def main(self):
        gtk.main()

if __name__ == "__main__":
    apl = outlineEditor()
    apl.main()

