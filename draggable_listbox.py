# draggable_listbox.py
import tkinter as tk


class DraggableListbox(tk.Listbox):
    """ドラッグ＆ドロップで並び替え可能なリストボックス"""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.bind("<Button-1>", self.on_click)
        self.bind("<B1-Motion>", self.on_drag)
        self.dragged_index = None

    def on_click(self, event):
        self.dragged_index = self.nearest(event.y)

    def on_drag(self, event):
        if self.dragged_index is not None:
            current_index = self.nearest(event.y)
            if current_index != self.dragged_index:
                item = self.get(self.dragged_index)
                self.delete(self.dragged_index)
                self.insert(current_index, item)
                self.selection_clear(0, tk.END)
                self.selection_set(current_index)
                self.activate(current_index)
                self.dragged_index = current_index
