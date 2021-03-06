from distutils.log import info
import os
from tkinter import Y, Tk, Menu, Label, Frame, Canvas, RIGHT, PhotoImage, messagebox, filedialog as fd
import time
from tkinter.messagebox import showinfo
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import Menu
from chess_core import GameOps
from PIL import ImageTk, Image
from tkinter.filedialog import askopenfile
from tkinter.filedialog import asksaveasfile
ytext = 1000

def button_control(func):
    def wrap(*args, **kwargs):
        event = args[1]
        if event.widget['state'] == 'disabled':
            return
        gui = func(*args, **kwargs)
        if gui.board_flip:
            gui.flip_board()
        return
    return wrap


def disable_event():
    pass


class GameBoard(tk.Frame):

    column_chars, row_chars = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'], ['1', '2', '3', '4', '5', '6', '7', '8']
    label_column, label_row = [], []
    images = {'pieces': {}, 'button': {}, 'promotion': {}}
    widgets = {'button': {}, 'text': {}, 'window': {}}
    image_paths = {'pieces': {}, 'button': {}, 'promotion': {}}

  
            
    def __init__(self, parent, board_state, root_dir, n_rows=8, n_cols=8, color1='#F0D9B5', color2='#B58863'):
        parent.resizable(True, True)
        tk.Frame.__init__(self, parent)
        self.parent = parent
        self.root_dir = root_dir
        self.board_state = board_state
        self._saved_states = 0
        self.final_move = -1
        self.redo_move = 0
        self.state_change = False
        self.n_rows = n_rows
        self.n_cols = n_cols
        self.color1 = color1
        self.color2 = color2
        self.pieces = {}
        self.piece_selected = None
        self.click_idx = 0
        self.valid_move = False
        self.kill = None
        self.board_labels = self.get_field_names()
        self.field_names = self.get_field_names()
        self.board_flip = False
        self.is_flipped = False

        # get board game dimensions
        self.layout = self.get_game_layout(window_w=960, window_h=540, n_rows=n_rows, n_cols=n_cols)
        self.screen_center = int(self.parent.winfo_screenwidth() / 2), int(self.parent.winfo_screenheight() / 2)

        # create main window
        self.mainWindow = parent
        self.mainWindow.title('Chess')
        self.mainWindow.geometry('{}x{}+{}+{}'.format(
            self.layout['total_w'], self.layout['board_ext_h'],
            *self.center_window(w=self.layout['total_w'], h=self.layout['board_ext_h'], center_xy=self.screen_center)
        ))
        
        self.mainWindow.bind('<Configure>', self.refresh)
        self.board = tk.Canvas(self, borderwidth=0, highlightthickness=2, highlightbackground='black',
                                width=self.layout['board_ext_w'],
                                height=self.layout['board_ext_h'],
                                background='bisque')
        self.board.bind('<Button-1>', self.click_board)  # left mouse interaction with board
        self.board.pack(side=tk.LEFT, fill=tk.Y, expand=tk.FALSE, padx=0, pady=0)
        self.board.bind('<Configure>', self.draw_board)
        self.highlighter = None  # the highlighter for game piece selection

        # create panel canvas (for additional widgets) -- THE THINGY SA RIGHT
        self.panel = tk.Canvas(self, borderwidth=0, highlightthickness=2, highlightbackground='black',
                                width=self.layout['panel_w'] + self.layout['label_w'],
                                height=self.layout['board_ext_h'],
                                background='bisque')

        # board flip switch button images -- SWITCH SIDES NG WHO'S TURN
        self.save_image(fin=os.path.join(self.root_dir, 'images', 'buttons', 'on_off', 'on.png'),
                        img_cat='button', img_name='flip_on', scale=0.4)
        self.save_image(fin=os.path.join(self.root_dir, 'images', 'buttons', 'on_off', 'off.png'),
                        img_cat='button', img_name='flip_off', scale=0.4)

        self.panel.pack(side=tk.RIGHT, fill=tk.Y, expand=tk.FALSE, padx=0, pady=0)
        self.panel.bind('<Configure>', self.draw_panel)

        # pack the entire GUI
        self.pack(side='top', fill='both', expand='False', padx=0, pady=0)
        return

    def get_field_names(self):
        """creates an nd array with the board field names"""

        return GameOps.get_field_names(row_chars=self.row_chars, column_chars=self.column_chars)

    def coord_to_field(self, event):
        """converts the event (click) coordinates to the corresponding game board field index
        Arguments:
            event: left mouse click event on game board
        Returns:
            field_idx: clicked game board field index (row index, column index)
        """

        x = event.x - self.layout['board_x']
        y = event.y
        if (self.layout['board_w'] > x > 0) and (self.layout['board_h'] > y > 0):
            row_idx = (self.n_rows - 1) - int(y / self.layout['field_w'])
            col_idx = int(x / self.layout['field_w'])
            field_idx = (row_idx, col_idx)
        else:
            field_idx = None
        return field_idx

    def index2label(self, field_idx):
        """converts a field index (of flippable GUI board) to field label (name)"""

        return self.field_names[field_idx]

    def label2index_gui(self, label):
        """converts a field label (name) to field index (of flippable GUI board)"""

        return tuple(np.argwhere(self.field_names == label)[0])

    @staticmethod
    def label2index_game(label):
        """converts a field label (name) to field index (of non-flippable chess_core.GameOps board)"""

        return GameOps.label2index(label=label)

    def refresh(self, event):
        """updates the layout values whenever the window size is changed"""

        self.layout = self.get_game_layout(
            window_w=self.mainWindow.winfo_width(), window_h=self.mainWindow.winfo_height(), n_rows=self.n_rows,
            n_cols=self.n_cols, last_layout=self.layout)
        return

    def center_window(self, w, h, center_xy):
        """returns the x, y coordinates required to center a window around center_xy (where anchor='nw')"""
      
        x = int(center_xy[0] - w / 2)  # x_offset
        y = int(center_xy[1] - h / 2)  # y_offset
        return x, y

    def draw_board(self, event):
        """Draw the game board and update layout dimensions with the current window size"""

        self.board.delete('square')
        self.board.delete('labels')
        self.board.config(width=self.layout['board_ext_w'], height=self.layout['board_ext_h'])
        # create row and column labels
        self.label_row = []
        self.label_column = []
        for row, col in zip(range(self.n_rows), range(self.n_rows)):
            self.label_row.append(tk.Label(self.board, text=self.row_chars[::-1][row], fg='black', bg='bisque'))
            self.label_column.append(tk.Label(self.board, text=self.column_chars[col], fg='black', bg='bisque'))
            self.board.create_window(
                self.layout['label_w'] / 2,
                self.layout['label_w'] + self.layout['field_w'] * row,
                window=self.label_row[row], tags='labels'
            )
            self.board.create_window(
                (self.layout['field_w'] * col) + 2 * self.layout['label_w'],
                self.layout['label_w'] / 2 + self.n_cols * self.layout['field_w'],
                window=self.label_column[col], tags='labels'
            )

        # create field squares
        color = self.color2
        for row in range(self.n_rows):
            color = self.color1 if color == self.color2 else self.color2
            for col in range(self.n_cols):
                x1 = (col * self.layout['field_w'] + self.layout['label_w'])
                y1 = (row * self.layout['field_w'])
                x2 = x1 + self.layout['field_w']
                y2 = y1 + self.layout['field_w']
                self.board.create_rectangle(x1, y1, x2, y2, outline='black', fill=color, tags='square')
                color = self.color1 if color == self.color2 else self.color2

        # place all pieces
        for piece in GameOps.pieces:
            if piece.is_alive:
                self.place_piece(piece.short_name, self.label2index_gui(piece.current_field))

        self.board.tag_raise('piece')
        self.board.tag_lower('square')

        if self.highlighter is not None:
            self.board.delete(self.highlighter)
            self.highlighter = self.create_highlighter(self.board, self.layout['field_idx'])
        return

    def draw_panel(self, event):

        # delete all buttons in case of resized window
        self.panel.delete('panel')

        # resize the panel
        self.panel.config(width=self.layout['panel_w'] + self.layout['label_w'], height=self.layout['board_ext_h'])

        pad = 5

        # create new buttons at updated positions
        width = 120
        height = 25
        x_pad, y_pad = 1, height + 3 * pad

        undo_x = 3 * pad
        undo_y = 3 * pad
        redo_y = undo_y + 1.25 * height
        about_y = redo_y + 1.25 * height
        flip_y = about_y + y_pad
        history_y = flip_y + y_pad
        info_y = 90
        warning_x = self.layout['panel_w'] - 3 * pad
        warning_y = flip_y

        half_width = 1 * (self.layout['panel_w'] - 2 * (undo_x))
        if not self.widgets['button']:
            ###############UNDO BUTTON ######################
            self.widgets['button']['undo'] = self.make_button(
                button_name='UNDO', button_method=self.click_undo,
                canvas=self.panel, x= 145, y=redo_y, w=width, h=height,
                anchor='nw', tags='panel', state=tk.DISABLED)
            ###############UNDO BUTTON ######################

            ###############REDO BUTTON ######################
            self.widgets['button']['redo'] = self.make_button(
                button_name='REDO', button_method=self.click_redo,
                canvas=self.panel, x=undo_x, y=redo_y, w=width, h=height,
                anchor='nw', tags='panel', state=tk.DISABLED)
            ###############REDO BUTTON ######################
            
            ###############ABOUT BUTTON ######################
            self.widgets['button']['ABOUT'] = self.make_button(
                button_name='ABOUT', button_method=self.click_about,
                canvas=self.panel, x= 275, y=undo_y, w=width, h=height,
                anchor='nw', tags='panel', state=tk.NORMAL)    
            ###############ABOUT BUTTON ######################

            self.widgets['button']['flip'] = self.make_button(
                button_name='FLIP', button_method=self.click_flip,
                canvas=self.panel, x=undo_x, y=230, w=50, h=height,
                anchor='nw', tags='panel', state=tk.NORMAL,
                image=self.images['button']['flip_off'])




            self.widgets['button']['warnings'] = self.make_button(
                button_name='WARNINGS', button_method=self.click_warning,
                canvas=self.panel, x=395, y=redo_y, w=width, h=height,
                anchor='ne', tags='panel', state=tk.NORMAL)


                ###############OPEN BUTTON ######################
            self.widgets['button']['open'] = self.make_button(
                 button_name='OPEN', button_method=self.click_open,
                 canvas=self.panel, x=undo_x, y=undo_y, w=width, h=height,
                 anchor='nw', tags='panel', state=tk.NORMAL)    
                ###############OPEN BUTTON ######################

                
                ###############SAVE BUTTON ######################
            self.widgets['button']['save'] = self.make_button(
                 button_name='SAVE', button_method=self.click_savefile,
                 canvas=self.panel, x=145, y=undo_y, w=width, h=height,
                 anchor='nw', tags='panel', state=tk.NORMAL)    
                ###############SAVE BUTTON ######################


            self.widgets['text']['info'] = self.make_text(
                canvas=self.panel, x=undo_x, y=info_y, h=5*height, w=half_width, anchor='nw')



        return

    @staticmethod
    def read_image(fin, resize=None, scale=None):
        """reads and image file and converts it into a tkinter PhotoImage"""

        img = Image.open(fin)
        if resize is not None and scale is None:
            img = img.resize(resize, Image.ANTIALIAS)
        elif resize is None and scale is not None:
            img = img.resize(tuple(int(val * scale) for val in img.size), Image.ANTIALIAS)
        return ImageTk.PhotoImage(img)

    def save_image(self, fin, img_cat, img_name, resize=None, scale=None):
        """saves image so that reference is not lost"""

        self.images[img_cat][img_name] = self.read_image(fin, resize, scale)

    def fill_board(self, pieces):
        """fills the board with the game pieces"""

        for piece in pieces:
            img = GameBoard.read_image(fin=piece.img_file)
            self.add_piece(to_widget=self.board, name=piece.short_name, image=img, field_idx=piece.field_idx)
            self.add_image(img=img, name=piece.short_name, img_path=piece.img_file, img_cat='pieces')
        return

    def flip_board(self):
        """flips the GUI board so that each player can play its point of view"""

        field_label = self.index2label(self.layout['field_idx'])
        self.row_chars = self.row_chars[::-1]
        self.column_chars = self.column_chars[::-1]
        self.field_names = self.get_field_names()
        if self.highlighter is not None:
            self.layout['field_idx'] = self.label2index_gui(field_label)
        self.draw_board(None)
        self.is_flipped = True if not self.is_flipped else False

    @staticmethod
    def get_game_layout(window_w, window_h, n_rows, n_cols, last_layout=None):
        """creates the dimensions for a GUI board game including field labels and a user interface panel:
        Arguments:
            window_w: GUI window width
            window_h: GUI window height
            n_rows: the number of field rows (for chess: n_rows=8)
            n_cols: the number of field columns (for chess: n_cols=8)
        Returns:
            layout: (dict) a dict containing all relevant variable for the layout
        """

        layout = {}
        window_square_length = min(window_w, window_h)
        field_w = int(window_square_length / (n_cols + 0.5))
        layout['scale'] = field_w / last_layout['field_w'] if last_layout is not None else 1
        layout['field_w'] = field_w
        layout['label_w'] = int(layout['field_w'] / 2)
        layout['board_x'] = layout['label_w']
        layout['board_y'] = 0  # 0 for now
        layout['board_w'] = int(n_cols * layout['field_w'])
        layout['board_h'] = layout['board_w']
        layout['board_ext_h'] = int(window_square_length)
        layout['board_ext_w'] = int(layout['board_w'] + layout['label_w'] + 0.5 * layout['label_w'])
        layout['panel_x'] = int(layout['board_ext_w'])
        layout['panel_w'] = int(window_w - layout['panel_x'])
        layout['total_w'] = int(layout['panel_x'] + layout['panel_w'])
        layout['field_idx'] = last_layout['field_idx'] if last_layout is not None else (0, 0)
        layout['field_idx_reset'] = layout['field_idx']
        return layout

    @staticmethod
    def make_button(button_name, button_method, canvas, x, y, h=10, w=10, anchor='c', tags='', state=tk.NORMAL, image=None):
        """creates a tkinter button widget with a name and method
        Arguments:
            button_name: (str) the name of the button
            button_method: (method) the method to execute upon button click
            canvas: (tkinter.Tk.Canvas obj) the tkinter canvas obj in which to place the button
            x, y: (int) button placement coordinates
            anchor: (str) button placement anchor ('n', 'e', 's', 'w', 'c', ...)
        Returns:
            button: tkinter button widget
        """

        button = tk.Button(canvas, text=button_name, state=state, image=image)
        button.place(x=x, y=y, width=w, height=h, anchor=anchor)
        button.bind('<Button-1>', button_method)
        return button
################## TEXTBOX ###############
    @staticmethod
    def make_text(canvas, x, y, h=10, w=10, anchor='c'):
        """creates a text box tkinter widget"""
        text_box = tk.Text(canvas)
        text_box.place(x=x, y=y, width=w, height=h, anchor=anchor)
        vsb = tk.Scrollbar(text_box, orient="vertical", command=text_box.yview)
        vsb.pack(side="right", fill="y")
        text_box.config(state=tk.DISABLED, yscrollcommand=vsb.set)
        return text_box
################## TEXTBOX ###############
    @staticmethod
    def output_text(*args, **kwargs):
        """redirects the text output method to the chess_core.GameOps class"""

        GameOps.output_text(*args, **kwargs)

    @staticmethod
    def insert_text(text_box, text, style=None):
        """inserts text into a text_box tkinter text widget"""

        text_box.tag_config(style, foreground=style)
        text_box.config(state=tk.NORMAL)
        text_box.insert('end', text, style)
        text_box.config(state=tk.DISABLED)
        text_box.see('end')

    def make_pop_up(self, title, lock=True, w=100, h=100, x_off=0, y_off=0, center_xy=None):
        """creates a pop up window.
        Arguments:
            lock: (bool) if lock == True only the pop up window can be interacted with until it's closed
            center_xy
        """
        win = tk.Toplevel()
        win.wm_title(title)
        win.resizable(width=tk.FALSE, height=tk.FALSE)
        if lock:
            win.protocol('WM_DELETE_WINDOW', disable_event)
            win.grab_set()
        if center_xy is not None:
            x_off, y_off = self.center_window(w=w, h=h, center_xy=center_xy)
        win.geometry('{}x{}+{}+{}'.format(w, h, x_off, y_off))
        return win

    @staticmethod
    def close_pop_up(win, was_locked=True):
        """closes a pop up window"""
        if was_locked:
            win.grab_release()
        win.destroy()
        return

    def promotion_choice(self, color):
        """creates a pop up window to choose which piece class the pawn will be promoted to"""
        img_sample = self.images['pieces'][next(iter(self.images['pieces']))]
        w, h = img_sample.width(), img_sample.height()
        self.widgets['window']['promote'] = self.make_pop_up(title='Promotion Choice', lock=True,
                                                             w=w*4, h=h, center_xy=self.screen_center)
        win_canvas = tk.Canvas(self.widgets['window']['promote'], bg='bisque', borderwidth=0, highlightthickness=0)
        win_canvas.pack(expand=tk.TRUE, fill=tk.BOTH)
        piece_specs_fin = os.path.join(self.root_dir, 'promotion_specs.csv')
        piece_specs = pd.read_csv(piece_specs_fin)
        for idx, piece in piece_specs.loc[piece_specs.color == color].reset_index().iterrows():
            img_path = os.path.join(self.root_dir, 'images', piece['img_file'])
            piece['img_file'] = img_path
            piece_type = piece['name_long'].split()[0]
            img = self.read_image(img_path)
            self.make_button(button_name=piece_type, button_method=self.click_promotion, canvas=win_canvas,
                             x=(idx * w), y=(w / 2), w=w, h=h, image=img, anchor='w')
            self.add_image(img=img, name=piece_type, img_path=img_path, img_cat='promotion')
        return

    def click_promotion(self, event):
        """registers which piece class user clicked for the pawn promotion and initiates pawn promotion"""

        piece_type = event.widget['text']
        GameOps.promote_pawn(pawn=GameOps.promote_piece, to_class=piece_type)
        self.close_pop_up(win=self.widgets['window']['promote'], was_locked=True)
        return

    def click_board(self, event):
        """This function controls the game board interaction
            1) the first click (click_idx==0) selects the chess piece
            2) the second click can choose a different piece or move the piece to the desired field (if move is valid)
            3) in case of an invalid move, the user will be informed
        """

        if GameOps.is_checkmate:
            return
        field_idx = self.coord_to_field(event)
        if field_idx is None:
            return
        field_name = self.index2label(field_idx)
        board_idx = self.label2index_game(field_name)

        self.layout['field_idx'] = field_idx
        piece = self.board_state[board_idx]
        piece_color = piece.color if piece else 0
        move_count = GameOps.move_count

        if self.click_idx == 0:  # select piece
            self.first_board_click(piece, field_idx, piece_color, move_count)
        else:
            self.second_board_click(piece, field_idx, piece_color, field_name, move_count)
        return

    def first_board_click(self, piece, field_idx, piece_color, move_count):
        """governs the first board click by one of the following operations:
            -   select a piece if field contains a piece of the player's color
            -   do nothing if field is empty or contains opponent's piece
        """

        if piece:
            if not GameOps.check_color_move(piece_color, move_count):
                return
            self.layout['field_idx_reset'] = field_idx
            self.highlighter = self.create_highlighter(canvas=self.board, field_idx=self.layout['field_idx'])
            self.piece_selected = piece
            self.click_idx += 1
        else:
            self.piece_selected = None

    def second_board_click(self, piece, field_idx, piece_color, field_name, move_count):
        """governs the second board click by one of the following operations:
            -   select another piece
            -   perform a piece move if valid move
            -   do nothing if invalid move and output a warning
        """

        if self.click_idx == 1 and GameOps.check_color_move(piece_color, move_count):  # select another piece
            self.end_move()
            self.remove_highlighter()
            self.layout['field_idx'] = field_idx
            self.first_board_click(piece, field_idx, piece_color, move_count)
        else:  # do the move
            self.piece_selected.move(field_name)
            if self.valid_move:
                if self.kill is not None:
                    self.images['pieces'][self.kill.short_name] = ''
                self.place_piece(self.piece_selected.short_name, field_idx)
                if GameOps.is_rochade_gui:
                    rochade_field_idx = GameOps.rochade_rook.label2index(GameOps.rochade_rook_move_to)
                    self.place_piece(GameOps.rochade_rook.short_name, rochade_field_idx)
                    GameOps.is_rochade_gui = False
                    GameOps.is_rochade = False
                self.valid_move = False
                self.kill = None
                self.final_move = GameOps.move_count - 1
                self.redo_move = self.final_move
                GameOps.save_state()
                self.end_move()
                self.remove_highlighter()
                self.update_bottons()
                self.parent.update()
                if self.board_flip:
                    self.flip_board()
                    time.sleep(0.5)
            else:
                self.layout['field_idx'] = self.layout['field_idx_reset']

    def end_move(self):
        """ends a move by resetting the click count"""

        self.click_idx = 0
        return

    def create_highlighter(self, canvas, field_idx):
        """creates a highlighter for the currently selected piece"""

        return canvas.create_rectangle(self.rectangle_field_coords(field_idx), width=4, tags='square')

    def remove_highlighter(self):
        """removes the piece selection highlighter from GUI board"""

        self.board.delete(self.highlighter)
        self.highlighter = None
        return

    def rectangle_field_coords(self, field_idx):
        """gives the rectangle coordinates for a field at field_idx on the game board"""

        row, col = field_idx
        x_0 = self.layout['board_x'] + col * self.layout['field_w']
        y_0 = (self.n_rows - row) * self.layout['field_w']
        x_1 = x_0 + self.layout['field_w']
        y_1 = y_0 - self.layout['field_w']
        return x_0, y_0, x_1, y_1

    def add_piece(self, to_widget, name, image, field_idx, x=0, y=0):
        """Add a piece to the game board"""

        to_widget.create_image(0, 0, image=image, tags=(name, 'piece'), anchor='c')
        self.place_piece(name, (field_idx[0], field_idx[1]))
        return

    @classmethod
    def add_image(cls, img, name, img_path, img_cat):
        """adds/saves an image under attributes images and image_paths. This is necessary as tkinter images need to
        have an existing reference."""
        cls.images[img_cat][name] = img
        cls.image_paths[img_cat][name] = img_path
        return


    @classmethod
    def add_images(cls, piece_images, piece_image_paths):
        """Save images and paths"""

        cls.images['pieces'] = piece_images
        cls.image_paths = piece_image_paths
        return

    def place_piece(self, name, field_idx):
        """Place a piece at the given row/column from field_idx
        Arguments:
             name: (str) the piece's 3 character short name
             field_idx: (tuple) the (row_idx, col_idx) where to place the piece
        """

        row_idx = (self.n_rows - 1) - field_idx[0]
        col_idx = field_idx[1]
        x0 = self.layout['board_x'] + self.layout['field_w'] * (0.5 + col_idx)
        y0 = self.layout['board_y'] + self.layout['field_w'] * (0.5 + row_idx)
        self.board.coords(name, x0, y0)
        return

    def load_states(self, state_count):
        """loads a specific state of the current game
        Arguments:
            state_count: (int) the index for the specific game state to load
        """

        self.end_move()
        self.remove_highlighter()
        if not self.final_move >= state_count >= -1:
            print('cannot progress further')
            return
        if self.redo_move == self.final_move:
            self.state_change = True
            self._saved_states = GameOps.load_state()

        self.redo_move = state_count
        state = self._saved_states[self.redo_move].copy()
        GameOps.set_global_vars(state=state['globalVars'])
        for i in range(len(self.board_state)):
            for j in range(len(self.board_state[i])):
                self.board_state[i][j] = None
                self.board_state[i][j] = state['board'][i][j]
        self.board.delete('piece')
        for p in GameOps:
            if p.is_alive:
                img = self.read_image(fin=p.img_file)
                self.add_piece(to_widget=self.board, name=p.short_name, image=img, field_idx=p.field_idx)
                self.add_image(img=img, name=p.short_name, img_path=p.img_file, img_cat='pieces')
        self.output_text('Loaded Move {}'.format('Initial' if state_count == -1 else state_count),
                         prefix='=>', style='load')
        return

    def update_bottons(self):
        """controls how the UNDO/REDO buttons are displayed"""

        if self.redo_move == -1:
            self.widgets['button']['undo']['state'] = tk.DISABLED
        else:
            
            self.widgets['button']['undo']['state'] = tk.NORMAL
            

        if self.redo_move == self.final_move:
            self.widgets['button']['redo']['state'] = tk.DISABLED
        else:
            self.widgets['button']['redo']['state'] = tk.NORMAL
        
        return

  
    def click_flip(self, event):
        """method for the flip board button that flips the board"""

        move_count = GameOps.move_count
        if self.board_flip:
            self.widgets['button']['flip'].config(image=self.images['button']['flip_off'])
            self.board_flip = False
            if bool(move_count % 2) and self.is_flipped:
                self.flip_board()
        else:
            self.widgets['button']['flip'].config(image=self.images['button']['flip_on'])
            self.board_flip = True
            if bool(move_count % 2) and not self.is_flipped:
                self.flip_board()

    @button_control
    def click_undo(self, event):
        """method for the UNDO button that loads the last game state"""

        state_count = self.redo_move - 1
        self.load_states(state_count)
        self.update_bottons()
        return self


#############About Func###########

    def click_about(self, event):
        """show about"""
    
        messagebox.showinfo("About Game",
                            """Chess is a board game played between two players. It is sometimes called Western chess or international chess to distinguish it from related games such as xiangqi and shogi.
                            
Program edited and created by Michaella Valerio, Nathaniel Ang, Julian Valdez, Dempster Gabriel""")
        self.mainloop() 
     
#############About Func###########


    @button_control
    def click_redo(self, event):
        """method for the REDO button that loads the next game state"""

        state_count = self.redo_move + 1
        self.load_states(state_count)
        self.update_bottons()
        return self

    def click_warning(self, event):
        GameOps.show_warnings = True if not GameOps.show_warnings else False
        widget = self.widgets['button']['warnings']
        widget.configure(state=tk.DISABLED if GameOps.show_warnings else tk.NORMAL)
        widget.configure(fg='black' if not GameOps.show_warnings else 'gray')
        return

    ####OPEN FILE####
    def click_open(self, event):

            """method for the open button"""
            file = askopenfile(mode ='r', filetypes =[('Python Files', '*.py')])
            if file is not None:
                content = file.read()
            print(content)
            return

    ####SAVE FILE####
    def click_savefile(self,event):
        files = [('All Files', '*.*'), 
             ('Python Files', '*.py'),
             ('Text Document', '*.txt')]
        file = asksaveasfile(filetypes = files, defaultextension = files)
  