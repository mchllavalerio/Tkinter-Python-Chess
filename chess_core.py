import os
import abc
import numpy as np
import pandas as pd

import _pickle as pickle

from text_styles import TextStyle


class IterRegistry(type):
    def __iter__(cls):
        return iter(cls.pieces)


class GameOps(metaclass=IterRegistry):
    """Contains the entire game logic and piece objects
    """

    pieces = []
    column_chars = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    colors = {'num': [1, 2], 'str': ['white', 'black'], 'str_short': ['w', 'b']}
    row_chars = [str(i) for i in range(1, len(column_chars) + 1)]
    field_names = None
    move_count = 0
    current_color = {'num': 1, 'str': 'white', 'str_short': 'w'}
    verbose = True
    board_gui = None
    board_objects = None
    show_warnings = False
    # saves if white/black were already in check (for rochade): idx 0 -> white, idx 1 -> black]
    was_checked = [False, False]
    is_rochade, is_rochade_gui = False, False
    rochade_rook = None
    rochade_rook_move_to = None
    rochade_field_idx = None
    promotion_counter = {p: p_count for p, p_count in zip(['Queen', 'Rook', 'Knight', 'Bishop'], [0, 2, 2, 2])}
    promote_piece = None
    is_checkmate = False
    save_file = os.path.join(os.path.dirname(__file__), 'saved_state.pkl')
    codes = {
        'invalid': 0,
        'empty': 1,
        'opponent': 2,
    }

    def __init__(self, name, short_name, color, current_field, img_file):
        """Creates a chess piece object
        Arguments:
            name: piece name long
            short_name: piece name short
            color: 1 for white, 2 for black
            current_field: piece's start field
            img_file: path to the piece's image
        """

        self.pieces.append(self)
        self.name = name
        self.short_name = short_name
        self.color = color
        self.img_file = img_file
        self.is_alive = True
        self.checks = False

        if GameOps.field_names is None:  # field names only have to be created once
            GameOps.field_names = GameOps.get_field_names(row_chars=self.row_chars, column_chars=self.column_chars)
        self.current_field = current_field
        self.last_field = current_field
        self.field_idx = self.label2index(self.current_field)
        self.possible_moves = []
        self.receive_en_passant = False
        self.perform_en_passant = False
        self.en_passant_idx = (None, None)

        self.move_idx = 0

    @staticmethod
    def get_field_names(row_chars, column_chars):
        return np.array([['{}{}'.format(col, row) for col in column_chars] for row in row_chars])

    @classmethod
    def index2label(cls, field_idx):
        """converts a field index to field label (name)"""

        return cls.field_names[field_idx]

    @classmethod
    def label2index(cls, label):
        """converts a field label (name) to field index"""

        field_idx = np.where(cls.field_names == label)
        return tuple([field_idx[0][0], field_idx[1][0]])

    @classmethod
    def initialize_game(cls, board_objects, board_gui, show_warnings):
        """initializes the game by registering the board objects (pieces), the GUI board and initializing the save file
        """
        cls.board_objects = board_objects
        cls.board_gui = board_gui
        cls.save_state(initializer=True)
        cls.print_warning = show_warnings

    @staticmethod
    def initialize_board(pieces):
        """fills a board matrix with game piece objects"""

        board_frame = np.empty((8, 8), dtype=object)
        for piece in pieces:
            board_frame[piece.field_idx] = piece
        return board_frame

    @staticmethod
    def fill_board(pieces, board_gui):
        """routes the fill_board() method to the GUI"""

        return board_gui.fill_board(pieces)

    @staticmethod
    def instantiate_pieces(piece_specs_fin, img_path):
        """instantiates all game pieces specified in file './piece_specs.csv' """

        piece_specs = pd.read_csv(piece_specs_fin)
        for idx, piece in piece_specs.iterrows():
            piece['img_file'] = os.path.join(img_path, piece['img_file'])
            piece_type = piece['name_long'].split()[0]
            GameOps.obj_from_string(class_name=piece_type, params=piece.to_list())
        return

    @staticmethod
    def obj_from_string(class_name, params, module=None):
        """instantiates an obj of class 'class' from module 'module'."""

        if module is None:  # class is in current file
            return globals()[class_name](*params)
        else:  # class from another module
            return getattr(module, class_name)(*params)

    @classmethod
    def save_state(cls, initializer=False):
        """saves the current game state"""

        move_count = -1 if initializer else cls.move_count - 1
        if os.path.exists(cls.save_file):
            saved_state = cls.load_state()
            os.remove(cls.save_file)
        else:
            saved_state = dict()
        saved_state[move_count] = {
            'board': cls.board_objects.copy(),
            'globalVars': cls.get_global_vars()
        }

        with open(cls.save_file, 'ab') as f_out:
            pickle.dump(saved_state, f_out, -1)
        return

    @classmethod
    def load_state(cls, move_counter=False):
        """loads the game's save file"""

        with open(cls.save_file, 'rb') as f_in:
            _saved_state = pickle.load(f_in)
        return _saved_state

    @classmethod
    def get_global_vars(cls):

        attrs = [
            'pieces', 'move_count', 'was_checked', 'is_rochade', 'is_rochade_gui',
            'rochade_rook', 'rochade_rook_move_to', 'rochade_field_idx', 'promotion_counter', 'is_checkmate'
        ]
        return {attr: getattr(cls, attr) for attr in attrs}

    @classmethod
    def set_global_vars(cls, state):
        """set the class attributes with given values"""

        for attr in state:
            setattr(cls, attr, state[attr])
        return

    @classmethod
    def output_text(cls, text, prefix=None, style='black', is_test=False):
        """outputs gane info text (log) into one of the following:
            -   GUI if game is played with the GUI
            -   console if otherwise
        """

        if not cls.verbose or is_test or (style == 'warning' and not cls.show_warnings):
            return

        # text
        text = '{} {}\n'.format(prefix if prefix is not None else str(cls.move_count) + '.', text)
        text = text.lower()

        # text style
        launcher = 'gui' if cls.board_gui is not None else 'console'
        style = TextStyle.styles[launcher][style]
        style_end = TextStyle.styles[launcher]['end']

        if cls.board_gui is not None:  # print in GUI
            cls.board_gui.insert_text(cls.board_gui.widgets['text']['info'], text, style=style)
        else:  # print in console
            text = style + text + style_end
            print(text)

    def move_counter(self):
        """increments the move count after valid move and keeps track color"""

        self.move_idx += 1
        GameOps.move_count += 1
        if GameOps.is_rochade:
            GameOps.rochade_rook.move_idx += 1
        color_idx = 0 if self.check_color_move('white', move_count=GameOps.move_count) else 1
        for color_cat in self.colors:
            self.current_color[color_cat] = self.colors[color_cat][color_idx]
        return

    @staticmethod
    def check_color_move(color, move_count):
        """checks whether a piece color is of equal color or opponent's color"""
        if type(color) == str:
            color = 1 if color in ['w', 'white'] else 2
        if color - 1 == move_count % 2:
            return True
        else:
            return False

    def get_move_step(self, move_to):
        """returns a tuple of the move vector"""

        move_to_idx = self.label2index(move_to)
        return tuple([move_to_idx[i] - self.field_idx[i] for i in range(2)])

    def get_intermediate_field_names(self, move_to):
        """returns all intermediate steps that need to be valid to successfully execute the move"""

        field_idx = self.field_idx
        move_vector = list(self.get_move_step(move_to))
        step_count = max([abs(s) for s in move_vector])

        intermediate_steps = []
        for s in range(step_count):  # identifies all intermediate field names
            field_idx = tuple([int(field_idx[i] + move_vector[i]/step_count) for i in range(2)])
            intermediate_steps.append(self.index2label(field_idx))

        if 'Knight' in self.name:  # Knight jumps over
            intermediate_steps = [move_to]
        return intermediate_steps

    def invalid_request(self, move_to):
        """checks if the move/piece selection request is valid"""

        request_error = ''
        if not self.move_count % 2 == (self.color - 1):
            request_error = "TurnError: It is {}'s turn".format('white' if self.color == 2 else 'black')
        if not self.is_alive:
            request_error = 'PieceError: {} was already killed'.format(self.short_name)
        if not np.array(np.where(self.field_names == move_to)).size:
            request_error = 'FieldError: The Field does not exist! Try another value',
        return request_error

    def check_move(self, move_to, color, is_test=False):
        """
            0:  -   move is not in piece's move set or
                -   at least one of the intermediate steps or
                -   final step is invalid
                -   rochade moves through check
            1:  move is valid to an empty field
            2:  move is valid and piece kills another piece
        """

        info_text = ''
        end_code = self.codes['invalid']

        # check if move in move set -- check if move is possible
        self.move_types(move_to, is_test=is_test)
        step = list(self.get_move_step(move_to))
        if step not in self.possible_moves:
            info_text = 'MoveError: {} cannot move to {}'.format(self.short_name, move_to)
            return end_code, info_text

        # check if intermediate steps are valid -- move validation
        steps = self.get_intermediate_field_names(move_to)
        for step in steps[:-1]:  # intermediate steps before end field
            if not self.check_field(step, color, self.board_objects, is_test) == self.codes['empty']:
                info_text = 'Intermediate step to {} is invalid'.format(step)
                return end_code, info_text

        # check if rochade moves through check
        if GameOps.is_rochade:
            end_code, info_text = self.check_through_check(steps[:-1])
            if end_code == self.codes['invalid']:
                return end_code, info_text

        # check the destination field 
        end_code = self.check_field(steps[-1], color, self.board_objects, is_test)
        if end_code == self.codes['invalid']:  # invalid destination field or occupied by same color
            pass
        elif end_code == self.codes['empty']:  # empty field
            info_text = '{} moves to {}'.format(self.short_name, steps[-1])
            self.board_gui.valid_move = True
        elif end_code == self.codes['opponent']:  # field occupied by opposite color
            if self.perform_en_passant:  # en passant kill
                enemy_idx = self.en_passant_idx
            else:  # normal kill
                enemy_idx = self.label2index(steps[-1])

            enemy_short_name = self.board_objects[enemy_idx].short_name
            info_text = '{} kills {} on {}'.format(self.short_name, enemy_short_name, steps[-1])
            self.board_gui.valid_move = True
            if not is_test:
                self.board_gui.kill = self.board_objects[enemy_idx]
        else:  # unknown field validity code
            raise ValueError('Unknown field validity: {}'.format(end_code))

        return end_code, info_text

    def check_field(self, field_to_check, piece_color, board_objects, is_test=False):
        """
        :return: field validity with values
            0:  if not valid or field occupied by same color,
            1:  if empty field,
            2:  if field occupied by opposite color
        """

        field_idx = self.label2index(field_to_check)
        validity = self.codes['invalid']
        if isinstance(board_objects[field_idx], GameOps):  # field contains a piece
            field_color = board_objects[field_idx].color
            if piece_color == field_color:  # piece cannot move to field occupied by same color
                self.output_text(
                    text='MoveError: {} contains piece of same color'.format(field_to_check),
                    style='warning', is_test=is_test)
            else:
                validity = self.codes['opponent']  # piece kills opposite color
        else:
            if self.perform_en_passant:  # en passant has same functionality as killing
                validity = self.codes['opponent']
            else:  # field is empty and valid
                validity = self.codes['empty']
        return validity

    def check_through_check(self, steps):
        """check whether king moves through check (i.e. during rochade)"""

        end_code, info_text = self.codes['empty'], ''
        for step in steps:
            GameOps.is_rochade, GameOps.is_rochade_gui = False, False
            mate_board = self.move_piece(move_to=step, move_validity=self.codes['empty'], do_rochade=False)
            is_check = self.check_check(color=self.color)
            self.redo_move(mate_board, move_validity=self.codes['empty'], is_test=False, reset_rochade=is_check)

            if is_check:
                end_code = self.codes['invalid']
                info_text = 'Rochade through check'
                return end_code, info_text
            else:
                GameOps.is_rochade_gui, GameOps.is_rochade = True, True
        return end_code, info_text

    def check_pawn2x(self):
        """checks whether pawn can be promoted"""

        return True if isinstance(self, Pawn) and any(row in self.current_field for row in ['1', '8']) else False

    @staticmethod
    def promote_pawn(pawn, to_class):
        """ promotes pawn into piece of class to_class
        Arguments:
            pawn (object of class Pawn): to pawn that is going to be promoted
            to_class (str): name of class to promote pawn into
        """

        GameOps.promotion_counter[to_class] += 1
        color_text = 'White' if pawn.color == 1 else 'Black'
        name_long = '{} {}'.format(to_class, color_text)
        letter_first = to_class[0] if not to_class == 'Knight' else 'N'
        name_short = '{}_{}{}'.format(letter_first, color_text[0], GameOps.promotion_counter[to_class])
        img_path = pawn.board_gui.image_paths['promotion'][to_class]

        specs = (name_long, name_short, pawn.color, pawn.current_field, img_path)
        new_piece = GameOps.obj_from_string(class_name=to_class, params=specs)

        pawn.board_objects[pawn.field_idx] = new_piece
        pawn.kill_piece(pawn, replace=True)
        pawn.board_gui.images['pieces'][pawn.short_name] = ''

        img = pawn.board_gui.read_image(fin=img_path)
        pawn.board_gui.add_image(img=img, name=new_piece.short_name, img_path=img_path, img_cat='pieces')
        pawn.board_gui.add_piece(to_widget=pawn.board_gui.board, name=new_piece.short_name,
                                 image=img, field_idx=pawn.board_gui.label2index_gui(new_piece.current_field))
        GameOps.output_text(text='Pawn promoted to {}'.format(to_class))

        # check checkmate
        color_opponent = 2 if pawn.color == 1 else 1
        new_piece.check_checkmate(color=color_opponent)
        GameOps.save_state()
        return

    def kill_piece(self, enemy, replace=False):
        """kills (removes) piece from board or replaces it (in case of pawn promotion)"""

        if not replace:
            self.board_objects[enemy.field_idx] = None
        enemy.is_alive = False
        enemy.current_field = 'Out of field'
        enemy.field_idx = None
        return

    def resurrect_piece(self, enemy):
        """resurrects (adds) piece to board"""

        enemy.is_alive = True
        enemy.current_field = self.current_field
        enemy.field_idx = self.field_idx
        return

    def redo_move(self, mate_board, move_validity, is_test=False, reset_rochade=True):
        """moves the piece back to previous position and status and resurrects killed pieces"""

        if move_validity == self.codes['opponent']:
            self.resurrect_piece(mate_board[self.field_idx])

        self.current_field = self.last_field
        self.field_idx = self.label2index(self.last_field)
        for index, x in np.ndenumerate(self.board_objects):
            self.board_objects[index] = mate_board[index]
            if self.board_objects[index]:
                self.board_objects[index].field_idx = index
                self.board_objects[index].current_field = self.field_names[index]
        if reset_rochade:
            GameOps.is_rochade_gui, GameOps.is_rochade = False, False
        if not is_test:  # tell GUI that move is invalid only if it was an actual move (not a test)
            self.board_gui.valid_move = False
            self.board_gui.kill = None
        return

    def reset_en_passant(self):
        """resets the possibility to perform en passant on pawns after move was executed"""

        for piece in GameOps.pieces:
            if not piece == self:
                piece.receive_en_passant = False
        return

    def move(self, move_to):
        """governs the move"""

        move_to = move_to.upper()

        is_test = False

        request_error = self.invalid_request(move_to)
        if request_error:
            self.output_text(text=request_error, style='warning', is_test=is_test)
            return

        self.execute_move(move_to, is_test=is_test)
        self.reset_en_passant()
        return

    def execute_move(self, move_to, is_test=False, bypass_validity=False):
  

        escapes_check = False

        move_validity, info_text = self.check_move(move_to=move_to, color=self.color, is_test=is_test)
        if move_validity == self.codes['invalid']:
            self.output_text(info_text, prefix='--', style='warning', is_test=is_test)
            return escapes_check

        # move type is valid and executed, initial state is saved in case of reverting back
        mate_board = self.move_piece(move_to=move_to, move_validity=move_validity, do_rochade=GameOps.is_rochade)

        if self.check_check(self.color, is_test=is_test):  # move puts player into check -> revert back
            self.redo_move(mate_board=mate_board, move_validity=move_validity, is_test=is_test)
        else:  # move is valid and not in/escapes check
            escapes_check = True
            if is_test:
                self.redo_move(mate_board=mate_board, move_validity=move_validity, is_test=is_test)
            else:  # all tests passed for a valid move
                # pawn promotion requires user interaction in GUI, therefore we need to do it post check_check()
                if self.check_pawn2x():
                    self.board_gui.promotion_choice(color=self.color)

                self.move_counter()
                self.output_text(info_text, is_test=is_test)
                opponent_color = 2 if self.color == 1 else 1
                self.check_checkmate(opponent_color)  # check if opponent is checkmate

        return escapes_check

    def move_piece(self, move_to, move_validity, do_rochade=False):
        """performs the move with one of the following:
            -   rochade
            -   move to empty field
            -   kill normal
            -   kill en passant
        """
        mate_board = self.board_objects.copy()

        self.board_objects[self.field_idx] = None  # empty the current field
        self.last_field = self.current_field  # safe current field for possible redo_move
        self.current_field = move_to  # move to requested field
        self.field_idx = self.label2index(move_to)

        if move_validity == self.codes['opponent']:  # piece kills
            if self.perform_en_passant:  # with en passant
                self.kill_piece(self.board_objects[self.en_passant_idx])
            else:  # normal kill
                self.kill_piece(self.board_objects[self.field_idx])

        self.board_objects[self.field_idx] = self  # piece moves to field

        if do_rochade:  # if rochade move the rook as well
            GameOps.rochade_rook.move_piece(
                move_to=GameOps.rochade_rook_move_to,
                move_validity=self.codes['empty'],
                do_rochade=False)

        if self.check_pawn2x():  # promote pawn
            GameOps.promote_piece = self
        else:
            GameOps.promote_piece = None
        return mate_board

    @classmethod
    def check_check(cls, color, is_test=False):
        """checks whether player is in check by checking if any of the opponent's piece attacks the king"""

        is_check = False
        for piece in GameOps:
            if isinstance(piece, King) and piece.color == color:
                move_to = piece.current_field  # find the King's position
                break

        for piece in GameOps:  # check if King is being attacked by any of opponent's pieces
            if piece.color != color and piece.is_alive:
                # go into test mode so that pieces are not actually moved
                move_validity, info_text = piece.check_move(move_to=move_to, color=piece.color, is_test=True)
                if not move_validity == cls.codes['invalid']:  # break if King is in check
                    is_check = True
                    break

        if is_check:
            cls.output_text(
                text='{} in check'.format('White' if color == 1 else 'Black'),
                prefix='--', style='warning', is_test=is_test)

        return is_check

    def check_checkmate(self, color):
        """checks whether player is in checkmate by checking if player can move out of check"""

        if not self.check_check(color, is_test=False):  # check if player in check; is_test = False to output text
            return

        is_test = True

        for piece in GameOps:
            if piece.color == color and piece.is_alive:
                for i, move_to in np.ndenumerate(self.field_names):
                    escapes_check = piece.execute_move(move_to, is_test=is_test)
                    if escapes_check:
                        GameOps.was_checked[piece.color - 1] = True
                        self.output_text(
                            text='{} can escape check'.format('White' if color == 1 else 'Black'),
                            prefix='--', style='normal', is_test=False)
                        return

        # if none of the pieces can prevent from being in check, then checkmate
        GameOps.is_checkmate = True
        self.output_text(
            text='{} is check mate. Congrats!'.format('White' if color == 1 else 'Black'),
            prefix='**', style='win', is_test=False)

        return

    @abc.abstractmethod
    def move_types(self, move_to, is_test=False):
        """defines the move set of a specific chess piece"""

        pass

    @staticmethod
    def is_diagonal(move_vector):
        """diagonal with same steps in vertical as horizontal direction"""

        move_v, move_h = move_vector
        return abs(move_v) == abs(move_h) and move_v != 0

    @staticmethod
    def is_straight(move_vector):
        """either vertical or horizontal direction"""

        move_v, move_h = move_vector
        return bool(move_v) != bool(move_h)

    @staticmethod
    def is_vertical(move_vector):
        """vertical direction"""

        move_v, move_h = move_vector
        return move_v != 0 and move_h == 0

    @staticmethod
    def is_horizontal(move_vector):
        """horizontal direction"""

        move_v, move_h = move_vector
        return move_v == 0 and move_h != 0


class Pawn(GameOps):
    """Pawn has different move sets depending on the current game situation:
        1) if Pawn has not moved yet: Pawn can move one or two steps vertically
        2) if Pawn has already moved: Pawn can move one step vertically
        3) Pawn can onl kill in a one-step positive (relative to the black/white) diagonal direction or
            through en passant
    """

    normal_moves = [[1, 0]]
    special_moves = [[2, 0]]
    kill_moves = [[1, -1], [1, 1]]

    def move_types(self, move_to, is_test=False):
        if self.move_idx == 0:  # case 1)
            self.possible_moves = self.normal_moves + self.special_moves + self.kill_moves
        else:  # case 2) & 3)
            self.possible_moves = self.normal_moves + self.kill_moves
        if self.color == 2:  # black
            self.possible_moves = [[-i for i in m] for m in self.possible_moves]

        # exclude invalid moves
        kill_moves = self.possible_moves[-2:]
        move_vector = list(self.get_move_step(move_to))
        move_to_idx = self.label2index(move_to)
        move_valid = True

        self.perform_en_passant = False
        if abs(move_vector[0]) == 2 and not is_test:  # if pawn moves two in first move, it can receive en passant
            self.receive_en_passant = True

        if move_vector in kill_moves:
            # Pawn can only move diagonally if it kills another Piece
            if self.board_objects[move_to_idx] is None:
                move_valid = False

                # check whether en passant can be performed
                en_passant_idx = (self.field_idx[0], move_to_idx[1])
                en_passant_piece = self.board_objects[en_passant_idx]
                if isinstance(en_passant_piece, Pawn):
                    if en_passant_piece.receive_en_passant and en_passant_piece.color != self.color:
                        move_valid = True
                        self.perform_en_passant = True
                        self.en_passant_idx = en_passant_idx
        else:
            # Pawn can only move if field is not occupied
            if self.board_objects[move_to_idx] is not None:
                move_valid = False

        if not move_valid:
            self.possible_moves = []
        return


class Rook(GameOps):
    """Rook can move either horizontally or vertically (straight)"""

    def move_types(self, move_to, is_test=False):
        move_vector = list(self.get_move_step(move_to))
        if self.is_straight(move_vector):  # vertical-only or horizontal-only
            self.possible_moves = [move_vector]
        return


class Knight(GameOps):
    """Knight has eight possible moves (with different signs) coming from two major move types:
        1) Two horizontal steps, one vertical step
        1) Two vertical steps, one horizontal step
    """

    normal_moves = [[2, -1], [2, 1], [1, 2], [-1, 2], [-2, -1], [-2, 1], [1, -2], [-1, -2]]

    def move_types(self, move_to, is_test=False):
        self.possible_moves = self.normal_moves
        return


class Bishop(GameOps):
    """Bishop can move diagonally"""

    def move_types(self, move_to, is_test=False):
        move_vector = list(self.get_move_step(move_to))
        if self.is_diagonal(move_vector):
            self.possible_moves = [move_vector]
        return


class Queen(GameOps):
    """Queen can move in any direction (diagonal, vertical, horizontal)"""

    def move_types(self, move_to, is_test=False):
        move_vector = list(self.get_move_step(move_to))
        if self.is_diagonal(move_vector) or self.is_straight(move_vector):
            self.possible_moves = [move_vector]
        return


class King(GameOps):
    """King can has two move types:
        1) move one step in any direction
        2) King can do a rochade once if King has not been in check, has not moved yet and rochade is a valid move
    """

    normal_moves = [[1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]]
    rochade = [[0, -2], [0, 2]]

    def move_types(self, move_to, is_test=False):
        self.possible_moves = self.normal_moves
        if self.move_idx == 0:
            move_vector = list(self.get_move_step(move_to))
            is_rochade, rook_rochade = self.check_rochade(move_vector, is_test=is_test)
            if is_rochade:
                self.possible_moves = self.normal_moves + [move_vector]
                self.set_rochade(move_vector, rook_rochade)
        return

    def check_rochade(self, move_vector, is_test=False):
        """checks whether the move is a valid rochade"""

        move_v, move_h = move_vector
        is_rochade, rook_rochade = False, None
        if move_vector in self.rochade and not GameOps.was_checked[self.color - 1] and not is_test:
            rooks = [p for p in GameOps if 'Rook' in p.name and p.color == self.color and p.is_alive]
            for rook in rooks:
                if (move_h > 0 and '2' in rook.name) or (move_h < 0 and '1' in rook.name) and rook.move_idx == 0:
                    is_rochade = True
                    rook_rochade = rook
                    break
        return is_rochade, rook_rochade

    def set_rochade(self, move_vector, rook_rochade):
        """sets all required settings for the rochade"""

        GameOps.is_rochade = True
        GameOps.is_rochade_gui = True
        GameOps.rochade_rook = rook_rochade
        rochade_idx = (self.field_idx[0], self.field_idx[1] + int(move_vector[1] / 2))
        GameOps.rochade_rook_move_to = self.index2label(rochade_idx)
        return
