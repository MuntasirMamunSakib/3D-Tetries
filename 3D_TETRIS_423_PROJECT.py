from random import choice
import numpy as np
import math
import time
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *


WINDOW_BG = (0.05, 0.05, 0.08)
GRID_BG_COLOR = (0.02, 0.02, 0.03)
GRID_LINE_COLOR = (0.2, 0.2, 0.3)
GRID_EMPTY_CELL = (0.03, 0.08, 0.03)


COLORS = [
    (0.9, 0.2, 0.2),   # Red
    (0.2, 0.4, 0.9),   # Blue
    (0.2, 0.8, 0.3),   # Green
    (0.9, 0.8, 0.1),   # Yellow
    (0.8, 0.2, 0.8),   # Magenta
    (0.1, 0.8, 0.8),   # Cyan
    (0.9, 0.5, 0.1),   # Orange
]

# Grid dimensions
GRID_SIZE = 30
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600

GRID_WIDTH = GRID_SIZE * 10
GRID_HEIGHT = GRID_SIZE * 20

GRID_ROW = 20
GRID_COL = 10

GRID_OFFSET_X = WINDOW_WIDTH - GRID_WIDTH
GRID_OFFSET_Y = 0

# shapes
SHAPES = {
    "O": [[(0, 0), (1, 0), (0, 1), (1, 1)]],
    "T": [
        [(0, 1), (1, 1), (1, 2), (2, 1)],
        [(1, 0), (1, 1), (1, 2), (2, 1)],
        [(0, 1), (1, 0), (1, 1), (2, 1)],
        [(0, 1), (1, 0), (1, 1), (1, 2)],
    ],
    "J": [
        [(2, 1), (1, 1), (0, 1), (0, 0)],
        [(1, 0), (1, 1), (1, 2), (0, 2)],
        [(0, 1), (1, 1), (2, 1), (2, 2)],
        [(1, 0), (1, 1), (1, 2), (2, 0)],
    ],
    "Z": [
        [(0, 0), (1, 0), (1, 1), (2, 1)],
        [(0, 1), (0, 2), (1, 0), (1, 1)],
    ],
    "S": [
        [(2, 0), (1, 0), (1, 1), (0, 1)],
        [(0, 0), (0, 1), (1, 1), (1, 2)],
    ],
    "L": [
        [(1, 0), (1, 1), (1, 2), (2, 2)],
        [(0, 1), (1, 1), (2, 1), (2, 0)],
        [(0, 0), (1, 0), (1, 1), (1, 2)],
        [(0, 1), (0, 2), (1, 1), (2, 1)],
    ],
    "I": [
        [(0, 1), (1, 1), (2, 1), (3, 1)],
        [(1, 0), (1, 1), (1, 2), (1, 3)],
    ],
}


WALL_KICK_OFFSETS = [(0, 0), (0, -1), (0, 1), (-1, 0), (1, 0)]

class TetrisGame3D:
    def __init__(self):
        # Game state
        self.bool_grid = np.full((GRID_ROW, GRID_COL), False, dtype=bool)
        self.filled_grid = np.full((GRID_ROW, GRID_COL, 3), GRID_EMPTY_CELL, dtype=np.float64)

        # shape properties
        self.shape_index = 0
        self.current_shape_type = choice(list(SHAPES.keys()))
        self.current_shape = SHAPES[self.current_shape_type][0]

        self.current_pos = (GRID_ROW - 1, GRID_COL // 2)
        self.current_color = choice(COLORS)
        self.ghost_color = tuple(c * 0.3 for c in self.current_color)


        self.hold_shape_type = None
        self.has_held_this_turn = False

        # Animation
        self.fall_animation = 0.0
        self.rotation_animation = 0.0
        self.clear_animation = {}
        self.game_over_animation = 0.0

        # speed controls
        self.base_drop_interval = 1.0
        self.drop_interval = self.base_drop_interval
        self.soft_drop_active = False
        self.soft_multiplier = 0.08  # soft drop

        # Camera
        self.camera_angle = 0.0
        self.camera_distance = 35
        self.camera_height = 15
        self.camera_auto_rotate = False

        # Collision flags
        self.is_collided_bottom = True
        self.is_collided_left = False
        self.is_collided_right = False

        # Game state
        self.is_game_over = False
        self.is_paused = False
        self.score = 0
        self.level = 1
        self.lines_cleared = 0
        self.next_shape_type = choice(list(SHAPES.keys()))

        # Timing
        self.last_update = time.time()
        self.last_timer_fire = time.time()

    def generate_new_shape(self):
        self.current_shape_type = self.next_shape_type
        self.next_shape_type = choice(list(SHAPES.keys()))

        self.shape_index = 0
        self.current_shape = SHAPES[self.current_shape_type][self.shape_index]

        prev_color = self.current_color
        self.current_color = choice(COLORS)
        while self.current_color == prev_color:
            self.current_color = choice(COLORS)

        self.ghost_color = tuple(c * 0.3 for c in self.current_color)
        self.fall_animation = 0.0
        self.has_held_this_turn = False

        # reset spawn
        self.current_pos = (GRID_ROW - 1, GRID_COL // 2)

        # collision at spawn -> game over
        if self.detect_collision_at_position(self.current_pos):
            self.is_game_over = True
            self.game_over_animation = 1.0
            print(f"GAME OVER! Final Score: {self.score}")

    def try_rotate_with_kicks(self, new_shape):
        # wall-kick attempts
        for dx, dy in WALL_KICK_OFFSETS:
            test_pos = (self.current_pos[0] + dx, self.current_pos[1] + dy)
            if not self.detect_collision_for_shape_at(new_shape, test_pos):
                self.current_pos = test_pos
                self.current_shape = new_shape
                return True
        return False

    def change_shape(self):
        self.rotation_animation = 360.0
        candidate_index = (self.shape_index + 1) % len(SHAPES[self.current_shape_type])
        tmp_shape = SHAPES[self.current_shape_type][candidate_index]
        if self.try_rotate_with_kicks(tmp_shape):
            self.shape_index = candidate_index

    def detect_rotation_collision(self, new_shape):
        for x, y in new_shape:
            new_x = x + self.current_pos[0]
            new_y = y + self.current_pos[1]
            if new_x < 0 or new_y < 0 or new_y >= GRID_COL:
                return True
            if new_x < GRID_ROW and self.bool_grid[new_x, new_y]:
                return True
        return False


    def detect_collision_for_shape_at(self, shape, pos):
        for x, y in shape:
            new_x = x + pos[0]
            new_y = y + pos[1]
            if new_x < 0 or new_y < 0 or new_y >= GRID_COL:
                return True
            if new_x < GRID_ROW and self.bool_grid[new_x, new_y]:
                return True
        return False

    def get_ghost_position(self):
        ghost_pos = self.current_pos
        while True:
            test_pos = (ghost_pos[0] - 1, ghost_pos[1])
            if self.detect_collision_at_position(test_pos):
                return ghost_pos
            ghost_pos = test_pos

    def detect_collision_at_position(self, pos):
        for x, y in self.current_shape:
            new_x = x + pos[0]
            new_y = y + pos[1]
            if new_x < 0:
                return True
            if new_y < 0 or new_y >= GRID_COL:
                return True
            if new_x < GRID_ROW and self.bool_grid[new_x, new_y]:
                return True
        return False

    def detect_bottom_collision(self):
        next_pos = (self.current_pos[0] - 1, self.current_pos[1])
        return self.detect_collision_at_position(next_pos)

    def detect_left_collision(self):
        next_pos = (self.current_pos[0], self.current_pos[1] - 1)
        return self.detect_collision_at_position(next_pos)

    def detect_right_collision(self):
        next_pos = (self.current_pos[0], self.current_pos[1] + 1)
        return self.detect_collision_at_position(next_pos)

    def update_filled_grid(self):
        for x, y in self.current_shape:
            grid_x = x + self.current_pos[0]
            grid_y = y + self.current_pos[1]

            if grid_x >= GRID_ROW:
                self.is_game_over = True
                self.game_over_animation = 1.0
                print(f"GAME OVER! Final Score: {self.score}")
                return

            if 0 <= grid_x < GRID_ROW:
                self.bool_grid[grid_x, grid_y] = True
                self.filled_grid[grid_x, grid_y] = self.current_color

    def check_and_clear_lines(self):
        lines_to_clear = []
        for i in range(GRID_ROW):
            if all(self.bool_grid[i]):
                lines_to_clear.append(i)
                self.clear_animation[i] = 1.0

        if lines_to_clear:
            # Animate line clearing
            for line in lines_to_clear:

                self.score += 100 * self.level
                self.lines_cleared += 1

                # Move lines down
                for j in range(line + 1, GRID_ROW):
                    self.bool_grid[j - 1] = self.bool_grid[j].copy()
                    self.filled_grid[j - 1] = self.filled_grid[j].copy()

                # Clear top line
                self.bool_grid[GRID_ROW - 1] = False
                self.filled_grid[GRID_ROW - 1] = GRID_EMPTY_CELL

            # Update level & gravity
            self.level = 1 + self.lines_cleared // 10
            self.base_drop_interval = max(0.08, 1.0 - (self.level - 1) * 0.08)
            self._sync_drop_interval()

            print(f"Score: {self.score} | Level: {self.level} | Lines: {self.lines_cleared}")

    def place_on_grid(self):
        self.update_filled_grid()
        if not self.is_game_over:
            self.check_and_clear_lines()
            self.generate_new_shape()
            self.is_collided_bottom = False

    def move_auto_down(self):
        if self.is_game_over or self.is_paused:
            return

        if self.detect_bottom_collision():
            self.place_on_grid()
        else:
            self.current_pos = (self.current_pos[0] - 1, self.current_pos[1])
            self.fall_animation += 1.0

    def move_left(self):
        if not self.is_game_over and not self.is_paused and not self.detect_left_collision():
            self.current_pos = (self.current_pos[0], self.current_pos[1] - 1)

    def move_right(self):
        if not self.is_game_over and not self.is_paused and not self.detect_right_collision():
            self.current_pos = (self.current_pos[0], self.current_pos[1] + 1)

    def soft_drop_step(self):
        """Move down +1 score per cell."""
        if self.is_game_over or self.is_paused:
            return
        if self.detect_bottom_collision():
            self.place_on_grid()
        else:
            self.current_pos = (self.current_pos[0] - 1, self.current_pos[1])
            self.fall_animation += 1.0
            self.score += 1  # soft drop points

    def drop_piece(self):
        if self.is_game_over or self.is_paused:
            return

        cells = 0  # hard drop
        while not self.detect_bottom_collision():
            self.current_pos = (self.current_pos[0] - 1, self.current_pos[1])
            self.fall_animation += 1.0
            cells += 1

        self.score += cells * 2
        self.place_on_grid()

    #  Hold mechanics
    def hold_piece(self):
        if self.is_game_over or self.is_paused or self.has_held_this_turn:
            return
        self.has_held_this_turn = True

        if self.hold_shape_type is None:
            self.hold_shape_type = self.current_shape_type
            self.generate_new_shape()
        else:
            self.current_shape_type, self.hold_shape_type = self.hold_shape_type, self.current_shape_type
            self.shape_index = 0
            self.current_shape = SHAPES[self.current_shape_type][0]
            self.current_pos = (GRID_ROW - 1, GRID_COL // 2)
            # keep current color/ghost
            self.ghost_color = tuple(c * 0.3 for c in self.current_color)

    def restart_game(self):
        self.__init__()

    def toggle_pause(self):
        self.is_paused = not self.is_paused

    def update_animations(self, dt):
        # Update rotation animation
        if self.rotation_animation > 0:
            self.rotation_animation = max(0, self.rotation_animation - dt * 720)

        # Update clear animations
        for line in list(self.clear_animation.keys()):
            self.clear_animation[line] -= dt * 2
            if self.clear_animation[line] <= 0:
                del self.clear_animation[line]

        # Update camera rotation
        if self.camera_auto_rotate:
            self.camera_angle += dt * 20

    def _sync_drop_interval(self):
        self.drop_interval = self.base_drop_interval * (self.soft_multiplier if self.soft_drop_active else 1.0)

    def draw_block_3d(self, x, y, z, color, scale=0.9, rotation=0):
        glPushMatrix()

        # Position
        glTranslatef(x, y, z)

        #rotation for animation
        if rotation != 0:
            glRotatef(rotation, 0, 1, 0)

        glScalef(scale, scale, scale)


        glMaterialfv(GL_FRONT, GL_AMBIENT, [c * 0.3 for c in color] + [1.0])
        glMaterialfv(GL_FRONT, GL_DIFFUSE, list(color) + [1.0])
        glMaterialfv(GL_FRONT, GL_SPECULAR, [0.8, 0.8, 0.8, 1.0])
        glMaterialf(GL_FRONT, GL_SHININESS, 100.0)

        # Draw cube
        glColor3f(*color)
        glutSolidCube(1.0)


        glColor3f(0, 0, 0)
        glLineWidth(1.0)
        glutWireCube(1.01)

        glPopMatrix()

    def draw_grid_base(self):
        # Draw grid floor
        glDisable(GL_LIGHTING)

        # Grid background
        glColor3f(0.1, 0.1, 0.15)
        glBegin(GL_QUADS)
        glVertex3f(-0.5, -0.5, -0.5)
        glVertex3f(GRID_COL - 0.5, -0.5, -0.5)
        glVertex3f(GRID_COL - 0.5, GRID_ROW - 0.5, -0.5)
        glVertex3f(-0.5, GRID_ROW - 0.5, -0.5)
        glEnd()

        # Grid lines
        glColor3f(0.2, 0.2, 0.3)
        glLineWidth(1.0)

        # Vertical lines
        glBegin(GL_LINES)
        for i in range(GRID_COL + 1):
            glVertex3f(i - 0.5, -0.5, -0.49)
            glVertex3f(i - 0.5, GRID_ROW - 0.5, -0.49)
        glEnd()

        # Horizontal lines
        glBegin(GL_LINES)
        for i in range(GRID_ROW + 1):
            glVertex3f(-0.5, i - 0.5, -0.49)
            glVertex3f(GRID_COL - 0.5, i - 0.5, -0.49)
        glEnd()

        # Draw walls
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glColor4f(0.1, 0.1, 0.2, 0.2)

        # Left wall
        glBegin(GL_QUADS)
        glVertex3f(-0.5, -0.5, -0.5)
        glVertex3f(-0.5, -0.5, 2)
        glVertex3f(-0.5, GRID_ROW - 0.5, 2)
        glVertex3f(-0.5, GRID_ROW - 0.5, -0.5)
        glEnd()

        # Right wall
        glBegin(GL_QUADS)
        glVertex3f(GRID_COL - 0.5, -0.5, -0.5)
        glVertex3f(GRID_COL - 0.5, -0.5, 2)
        glVertex3f(GRID_COL - 0.5, GRID_ROW - 0.5, 2)
        glVertex3f(GRID_COL - 0.5, GRID_ROW - 0.5, -0.5)
        glEnd()

        glDisable(GL_BLEND)
        glEnable(GL_LIGHTING)

    def draw_next_piece_preview(self):
        glPushMatrix()
        glTranslatef(GRID_COL + 3, GRID_ROW - 5, 0)

        # Draw preview box
        glDisable(GL_LIGHTING)
        glColor3f(0.2, 0.2, 0.3)
        glBegin(GL_LINE_LOOP)
        glVertex3f(-2, -2, 0)
        glVertex3f(3, -2, 0)
        glVertex3f(3, 3, 0)
        glVertex3f(-2, 3, 0)
        glEnd()
        glEnable(GL_LIGHTING)

        # Draw next shape
        next_shape = SHAPES[self.next_shape_type][0]
        next_color = (0.5, 0.5, 0.7)

        for x, y in next_shape:
            self.draw_block_3d(y - 1, x, 0, next_color, 0.7)

        glPopMatrix()


    def draw_hold_piece_preview(self):
        if self.hold_shape_type is None:
            return
        glPushMatrix()
        glTranslatef(-4, GRID_ROW - 5, 0)

        glDisable(GL_LIGHTING)
        glColor3f(0.2, 0.2, 0.3)
        glBegin(GL_LINE_LOOP)
        glVertex3f(-2, -2, 0)
        glVertex3f(3, -2, 0)
        glVertex3f(3, 3, 0)
        glVertex3f(-2, 3, 0)
        glEnd()
        glEnable(GL_LIGHTING)

        hold_shape = SHAPES[self.hold_shape_type][0]
        hold_color = (0.7, 0.7, 0.5)
        for x, y in hold_shape:
            self.draw_block_3d(y - 1, x, 0, hold_color, 0.7)
        glPopMatrix()


game = None

def keyboard(key, x, y):
    global game

    if key == b'q' or key == b'\x1b':  # q or ESC
        print(f"Thanks for playing! Final Score: {game.score}")
        glutDestroyWindow(glutGetWindow())
    elif key == b'a':
        game.move_left()
    elif key == b'd':
        game.move_right()
    elif key == b's':
        game.drop_piece()
    elif key == b'w':
        game.change_shape()
    elif key == b' ':
        if game.is_game_over:
            game.restart_game()
        else:
            game.drop_piece()
    elif key == b'p':
        game.toggle_pause()
    elif key == b'c':
        game.camera_auto_rotate = not game.camera_auto_rotate
    elif key in (b'h', b'H'):
        game.hold_piece()
    elif key in (b'r', b'R'):
        game.restart_game()


    # camera rotation with k / l ---
    elif key in (b'l', b'L'):
        # rotate clockwise by step degrees
        step = 15
        game.camera_angle = (game.camera_angle + step) % 360
    elif key in (b'k', b'K'):
        # rotate counter-clockwise
        step = 15
        game.camera_angle = (game.camera_angle - step) % 360

    glutPostRedisplay()

def special_keys(key, x, y):
    global game

    if key == GLUT_KEY_LEFT:
        game.move_left()
    elif key == GLUT_KEY_RIGHT:
        game.move_right()
    elif key == GLUT_KEY_DOWN:
        game.soft_drop_active = True
        game._sync_drop_interval()
        game.soft_drop_step()
    elif key == GLUT_KEY_UP:
        game.change_shape()

    glutPostRedisplay()


def special_keys_up(key, x, y):
    global game
    if key == GLUT_KEY_DOWN:
        game.soft_drop_active = False
        game._sync_drop_interval()

def draw_score_and_info():
    # Save current state
    glPushAttrib(GL_ALL_ATTRIB_BITS)

    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST)


    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, WINDOW_WIDTH, WINDOW_HEIGHT, 0, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    # Draw score background
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(0.1, 0.1, 0.15, 0.9)
    glBegin(GL_QUADS)
    glVertex2f(10, 10)
    glVertex2f(220, 10)
    glVertex2f(220, 160)
    glVertex2f(10, 160)
    glEnd()

    # Draw border
    glLineWidth(2.0)
    glColor3f(0.3, 0.3, 0.4)
    glBegin(GL_LINE_LOOP)
    glVertex2f(10, 10)
    glVertex2f(220, 10)
    glVertex2f(220, 160)
    glVertex2f(10, 160)
    glEnd()

    # Title
    glColor3f(0.8, 0.8, 1.0)
    glRasterPos2f(20, 35)
    for char in "3D TETRIS":
        glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(char))

    # Score
    glColor3f(1.0, 1.0, 1.0)
    glRasterPos2f(20, 60)
    score_string = f"Score: {game.score}"
    for char in score_string:
        glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(char))

    # Level
    glColor3f(0.9, 0.9, 0.9)
    glRasterPos2f(20, 85)
    level_string = f"Level: {game.level}"
    for char in level_string:
        glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(char))

    # Lines
    glColor3f(0.9, 0.9, 0.9)
    glRasterPos2f(20, 110)
    lines_string = f"Lines: {game.lines_cleared}"
    for char in lines_string:
        glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(char))


    if game.soft_drop_active:
        glColor3f(0.7, 1.0, 0.7)
        glRasterPos2f(20, 135)
        for char in "Soft Drop":
            glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(char))

    # Game state messages
    if game.is_paused:
        glColor3f(1.0, 1.0, 0.0)
        glRasterPos2f(20, 155)
        for char in "PAUSED":
            glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(char))
    elif game.is_game_over:
        # Draw game over message
        glColor4f(0.0, 0.0, 0.0, 0.8)
        glBegin(GL_QUADS)
        glVertex2f(WINDOW_WIDTH/2 - 150, WINDOW_HEIGHT/2 - 40)
        glVertex2f(WINDOW_WIDTH/2 + 150, WINDOW_HEIGHT/2 - 40)
        glVertex2f(WINDOW_WIDTH/2 + 150, WINDOW_HEIGHT/2 + 40)
        glVertex2f(WINDOW_WIDTH/2 - 150, WINDOW_HEIGHT/2 + 40)
        glEnd()

        glColor3f(1.0, 0.2, 0.2)
        glRasterPos2f(WINDOW_WIDTH/2 - 60, WINDOW_HEIGHT/2 - 10)
        for char in "GAME OVER":
            glutBitmapCharacter(GLUT_BITMAP_TIMES_ROMAN_24, ord(char))

        glColor3f(1.0, 1.0, 1.0)
        glRasterPos2f(WINDOW_WIDTH/2 - 100, WINDOW_HEIGHT/2 + 20)
        for char in "Press SPACE to restart":
            glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(char))

    # Controls (right side)
    glColor4f(0.1, 0.1, 0.15, 0.8)
    glBegin(GL_QUADS)
    glVertex2f(WINDOW_WIDTH - 210, 10)
    glVertex2f(WINDOW_WIDTH - 10, 10)
    glVertex2f(WINDOW_WIDTH - 10, 190)
    glVertex2f(WINDOW_WIDTH - 210, 190)
    glEnd()

    glColor3f(0.8, 0.8, 1.0)
    glRasterPos2f(WINDOW_WIDTH - 200, 30)
    for char in "Controls:":
        glutBitmapCharacter(GLUT_BITMAP_HELVETICA_12, ord(char))

    controls = [
        ("A/D or Arrows", "Move"),
        ("W or Up", "Rotate"),
        ("S or Space", "Hard drop"),
        ("Down", "Soft drop"),
        ("H", "Hold piece"),
        ("P", "Pause"),
        ("C", "Camera"),
        ("R", "Restart"),
        ("Q", "Quit")
    ]

    y_pos = 50
    for key, action in controls:
        glColor3f(1.0, 1.0, 0.5)
        glRasterPos2f(WINDOW_WIDTH - 200, y_pos)
        for char in key:
            glutBitmapCharacter(GLUT_BITMAP_HELVETICA_10, ord(char))

        glColor3f(0.8, 0.8, 0.8)
        glRasterPos2f(WINDOW_WIDTH - 110, y_pos)
        for char in f"- {action}":
            glutBitmapCharacter(GLUT_BITMAP_HELVETICA_10, ord(char))
        y_pos += 18

    glDisable(GL_BLEND)

    # Restore state
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

    glPopAttrib()
    glEnable(GL_LIGHTING)
    glEnable(GL_DEPTH_TEST)

def display():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)


    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(45, WINDOW_WIDTH / WINDOW_HEIGHT, 0.1, 100)


    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    # Dynamic camera position for better 3D view
    cam_x = game.camera_distance * math.sin(math.radians(game.camera_angle + 30))
    cam_z = game.camera_distance * math.cos(math.radians(game.camera_angle + 30))

    gluLookAt(
        cam_x + GRID_COL/2, game.camera_height + 10, cam_z + 5,
        GRID_COL/2, GRID_ROW/3, -2,
        0, 1, 0
    )


    light_pos = [GRID_COL/2 + 5, GRID_ROW + 10, 15, 1.0]
    glLightfv(GL_LIGHT0, GL_POSITION, light_pos)


    light2_pos = [-5, GRID_ROW/2, 10, 1.0]
    glLightfv(GL_LIGHT1, GL_POSITION, light2_pos)

    # Draw grid base and walls
    game.draw_grid_base()


    for i in range(GRID_ROW):
        for j in range(GRID_COL):
            if game.bool_grid[i, j]:
                color = game.filled_grid[i, j]

                # Apply animation for clearing lines
                scale = 0.9
                z_offset = 0
                if i in game.clear_animation:
                    scale = 0.9 * game.clear_animation[i]
                    color = tuple(c + (1-c) * (1-game.clear_animation[i]) for c in color)
                    z_offset = (1 - game.clear_animation[i]) * 2

                game.draw_block_3d(j, i, z_offset, color, scale)


    if not game.is_game_over:
        for x, y in game.current_shape:
            block_x = y + game.current_pos[1]
            block_y = x + game.current_pos[0]

            # Add falling animation with 3D depth
            anim_offset = (game.fall_animation % 1.0) * 0.1

            game.draw_block_3d(
                block_x,
                block_y - anim_offset,
                0.5,  # Raised above the grid for 3D effect
                game.current_color,
                0.95,
                game.rotation_animation
            )

        # Draw ghost piece with transparency
        ghost_pos = game.get_ghost_position()
        for x, y in game.current_shape:
            block_x = y + ghost_pos[1]
            block_y = x + ghost_pos[0]

            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            game.draw_block_3d(block_x, block_y, -0.2, game.ghost_color, 0.7)
            glDisable(GL_BLEND)


    game.draw_next_piece_preview()
    game.draw_hold_piece_preview()


    draw_score_and_info()

    glutSwapBuffers()

def update(value):
    global game

    if game is None:
        return

    current_time = time.time()
    dt = current_time - game.last_update
    game.last_update = current_time

    # Update animations
    game.update_animations(dt)

    # Auto-drop piece based on interval
    if not game.is_paused and not game.is_game_over:

        game.move_auto_down()

    # reschedule with current interval
    glutTimerFunc(int(game.drop_interval * 1000), update, 0)
    glutPostRedisplay()

def reshape(width, height):
    global WINDOW_WIDTH, WINDOW_HEIGHT
    WINDOW_WIDTH = width
    WINDOW_HEIGHT = height
    glViewport(0, 0, width, height)

def main():
    global game

    glutInit()
    glutInitDisplayMode(GLUT_RGB | GLUT_DOUBLE | GLUT_DEPTH)
    glutInitWindowSize(WINDOW_WIDTH, WINDOW_HEIGHT)
    glutInitWindowPosition(100, 100)
    glutCreateWindow(b"Professional 3D Tetris")

    # OpenGL setup
    glClearColor(*WINDOW_BG, 1.0)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT, GL_AMBIENT_AND_DIFFUSE)

    # Enhanced lighting
    glLightfv(GL_LIGHT0, GL_AMBIENT, [0.2, 0.2, 0.2, 1.0])
    glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1.0])
    glLightfv(GL_LIGHT0, GL_SPECULAR, [1.0, 1.0, 1.0, 1.0])

    # Additional lighting
    glEnable(GL_LIGHT1)
    glLightfv(GL_LIGHT1, GL_POSITION, [-5, 10, 5, 1.0])
    glLightfv(GL_LIGHT1, GL_DIFFUSE, [0.3, 0.3, 0.4, 1.0])

    # Enable smooth shading
    glShadeModel(GL_SMOOTH)

    # Initialize game
    game = TetrisGame3D()

    # Register callbacks
    glutDisplayFunc(display)
    glutKeyboardFunc(keyboard)
    glutSpecialFunc(special_keys)
    glutSpecialUpFunc(special_keys_up)
    glutReshapeFunc(reshape)
    glutTimerFunc(1000, update, 0)

    print("=== Professional 3D Tetris ===")
    print("Controls:")
    print("  A/D or Arrow Keys - Move left/right")
    print("  W or Up Arrow - Rotate (with wall-kicks)")
    print("  Down Arrow - Soft drop (+1/cell)")
    print("  S or Space - Hard drop (+2/cell)")
    print("  H - Hold/Swap current piece")
    print("  P - Pause")
    print("  C - Toggle camera rotation")
    print("  R - Restart")
    print("  Q or ESC - Quit")
    print("=============================")

    glutMainLoop()

if __name__ == "__main__":
    main()
