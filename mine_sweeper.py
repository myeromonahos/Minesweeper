from picographics import PicoGraphics, DISPLAY_TUFTY_2040 # 320 * 240
from pimoroni import Button
from machine import Pin, PWM
import time
import random
import machine


##### Display & hardware

display = PicoGraphics(display=DISPLAY_TUFTY_2040)
WIDTH, HEIGHT = display.get_bounds()
display.set_backlight(1.0)

button_left = Button(7, invert=False)
button_right = Button(9, invert=False)
button_up = Button(22, invert=False)
button_down = Button(6, invert=False)
button_reveal = Button(8, invert=False)

BLACK = display.create_pen(0, 0, 0)
GREY  = display.create_pen(80, 80, 80)
WHITE = display.create_pen(160, 160, 160)
YELLOW = display.create_pen(128,255,00)#(255, 255, 00)
RED = display.create_pen(255, 0, 0)
ORANGE = display.create_pen(255, 165, 0)
GREEN = display.create_pen(0, 255, 0)
STARS = display.create_pen(255,215,0)

FRONTIER_COLOURS = [
    display.create_pen(255, 0, 255),   # magenta
    display.create_pen(0, 255, 255),   # cyan
    display.create_pen(255, 255, 0),   # yellow
    display.create_pen(0, 255, 0),     # green
    display.create_pen(255, 128, 0),   # orange
]


##### States

STATE_INIT = 0
STATE_PLAY = 1
STATE_WIN  = 2
STATE_COMPLETE = 3
STATE_ANEW = 4

state = STATE_INIT


##### Switches

first_click = True
ask_solver_q = True
ask_mistakes_q = True
ask_mistakes_q_v2 = False
list_mistakes = []
ask_flood_q = True
ask_grid_q = True
ask_difficulty_q = True
difficulty = "easy"
use_solver = True
mistakes = False
press_start = None
long_press_used = False
FLAG_HOLD_TIME = 500 # in miliseconds
game_start_time = None
game_end_time = None
elapsed_time = 0
paused_time_total = 0
pause_time = None
MAX_GROUP = 12




#################### Mines functions ####################


##### Place mines, avoiding first revealed tiles and its neighboors

def place_mines_avoiding(cx, cy):
    placed = 0
    while placed < MINES:
        x = random.randrange(GRID_W)
        y = random.randrange(GRID_H)

        # Skip first revealed tile and its neighbours.
        if abs(x - cx) <= 1 and abs(y - cy) <= 1:
            continue

        if not mines[y][x]:
            if too_close(x, y) and random.random() < 0.8:
                continue
            mines[y][x] = True
            placed += 1
            
def too_close(x, y):
    # This avoids too many mines being too close to each other. But it makes the task harder for the solvers.
    # Use with cuation: (-1, 0, 1) is fine, (-2, -1, 0, 1, 2) is too much.
    for dy in (-1, 0, 1): # (-2, -1, 0, 1, 2):
        for dx in (-1, 0, 1): # (-2, -1, 0, 1, 2):
            nx, ny = x + dx, y + dy
            if 0 <= nx < GRID_W and 0 <= ny < GRID_H:
                if mines[ny][nx]:
                    return True
    return False


##### Count neighbouring mines, add numbers to the grid

def count_neighbours(cx, cy):
    count = 0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx = cx + dx
            ny = cy + dy
            if 0 <= nx < GRID_W and 0 <= ny < GRID_H:
                if mines[ny][nx]:
                    count += 1
    return count

def compute_numbers():
    for y in range(GRID_H):
        for x in range(GRID_W):
            if not mines[y][x]:
                numbers[y][x] = count_neighbours(x, y)




#################### Solvers functions #################### 


##### basic solver sub-function - records coordinates of all tiles in neighbourood of (x,y)

def get_neighbours(x, y):
    neighbours = []
    
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx = x + dx
            ny = y + dy
            if 0 <= nx < GRID_W and 0 <= ny < GRID_H:
                neighbours.append((nx, ny))
    return neighbours


##### Basic solver main

def solver_basic(start_x, start_y): 
    s_revealed = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]
    s_flags = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]

    stack = [(start_x, start_y)] # coordinates of the first click
    
    # rule 1: flood-reveal of all the empty tiles connected to first click or to any tile later found to
    # have zero traps in its neighbourhood. 
    while stack:
        x, y = stack.pop()
        if s_revealed[y][x]:
            continue
        if mines[y][x]:
            return False  # Just to be extra safe - should (must) never happen here.
                          
        s_revealed[y][x] = True

        if numbers[y][x] == 0:
            for nx, ny in get_neighbours(x, y):
                if not s_revealed[ny][nx]:
                    stack.append((nx, ny))
                    
    progress = True

    while progress:
        progress = False

        for y in range(GRID_H):
            for x in range(GRID_W):
                if not s_revealed[y][x]: # select a revealed tile...
                    continue
                if numbers[y][x] == 0:   # wich is connected to at least one trap.
                    continue

                neighbours = get_neighbours(x, y) # find coordinates of neighbouring tiles
                
                hidden = []
                flagged = 0

                for nx, ny in neighbours:
                    if s_flags[ny][nx]:
                        flagged += 1 # count flags already planted in neighbourhood
                    elif not s_revealed[ny][nx]:
                        hidden.append((nx, ny)) # add all non-revealed, non-flagged tiles to stack 
                
                # rule 2: if all hidden tiles are trapped, plant flags and carry on.
                if hidden and numbers[y][x] == flagged + len(hidden):
                    for nx, ny in hidden:
                        if not s_flags[ny][nx]:
                            s_flags[ny][nx] = True
                            progress = True

                # rule 3: if all hidden tiles are safe, reveal them and carry on.
                if hidden and numbers[y][x] == flagged:
                    for nx, ny in hidden:
                        if not s_revealed[ny][nx]:
                            s_revealed[ny][nx] = True
                            if numbers[ny][nx] == 0: # super-safe tiles are treated in first while loop
                                stack.append((nx, ny))
                            progress = True 

    # check if all safe tiles were revealed
    for y in range(GRID_H):
        for x in range(GRID_W):
            if not mines[y][x] and not s_revealed[y][x]:
                return False

    return True


##### medium solver sub-function - subset rule (rule 4)

def apply_subset_rule(x1, y1, x2, y2, s_revealed, s_flags): 
    n1 = numbers[y1][x1]
    n2 = numbers[y2][x2]

    if n1 == 0 or n2 == 0:
        return False, []

    H1 = set()
    H2 = set()
    f1 = f2 = 0

    for nx, ny in get_neighbours(x1, y1):
        if s_flags[ny][nx]:
            f1 += 1
        elif not s_revealed[ny][nx]:
            H1.add((nx, ny))

    for nx, ny in get_neighbours(x2, y2):
        if s_flags[ny][nx]:
            f2 += 1
        elif not s_revealed[ny][nx]:
            H2.add((nx, ny))

    if not H1 or not H2:
        return False, []

    n1 -= f1
    n2 -= f2

    if not H1.issubset(H2):
        return False, []

    diff = H2 - H1
    if not diff:
        return False, []

    progress = False
    newly_revealed = []

    # case 1: remaining tiles are mines
    if n2 - n1 == len(diff):
        for x, y in diff:
            if not s_flags[y][x]:
                s_flags[y][x] = True
                progress = True

    # case 2: remaining tiles are safe
    elif n2 - n1 == 0:
        for x, y in diff:
            if not s_revealed[y][x]:
                s_revealed[y][x] = True
                newly_revealed.append((x, y))
                progress = True

    return progress, newly_revealed


##### medium solver main

def solver_medium(start_x, start_y): 
    s_revealed = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]
    s_flags = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]

    stack = [(start_x, start_y)]
    
    # rule 1
    while stack:
        x, y = stack.pop()
        if s_revealed[y][x]:
            continue
        if mines[y][x]:
            return False
            
        s_revealed[y][x] = True

        if numbers[y][x] == 0:
            for nx, ny in get_neighbours(x, y):
                if not s_revealed[ny][nx]:
                    stack.append((nx, ny))
                    
    progress = True

    while progress:
        progress = False

        for y in range(GRID_H):
            for x in range(GRID_W):
                if not s_revealed[y][x]:
                    continue
                if numbers[y][x] == 0:
                    continue

                neighbours = get_neighbours(x, y)
                
                hidden = []
                flagged = 0

                for nx, ny in neighbours:
                    if s_flags[ny][nx]:
                        flagged += 1
                    elif not s_revealed[ny][nx]:
                        hidden.append((nx, ny))
                
                # rule 2
                if hidden and numbers[y][x] == flagged + len(hidden):
                    for nx, ny in hidden:
                        if not s_flags[ny][nx]:
                            s_flags[ny][nx] = True
                            progress = True
                
                # rule 3
                if hidden and numbers[y][x] == flagged:
                    for nx, ny in hidden:
                        if not s_revealed[ny][nx]:
                            s_revealed[ny][nx] = True
                            progress = True
                            
                            if numbers[ny][nx] == 0:
                                stack.append((nx, ny))
                                
        # rule 4 - subset rule
        for y1 in range(GRID_H):
            for x1 in range(GRID_W):
                if not s_revealed[y1][x1]:
                    continue
                if numbers[y1][x1] == 0:
                    continue  # tiles with 0 neighbouring traps are treated separately in the stack above
                
                for x2, y2 in get_neighbours(x1, y1):
                    if not s_revealed[y2][x2]:
                        continue
                    if numbers[y2][x2] == 0:
                        continue

                    progress_made, newly_revealed = apply_subset_rule(x1, y1, x2, y2, s_revealed, s_flags)
                    if progress_made:
                        progress = True
                        for x, y in newly_revealed:
                            if numbers[y][x] == 0:
                                stack.append((x, y))
                        

    for y in range(GRID_H):
        for x in range(GRID_W):
            if not mines[y][x] and not s_revealed[y][x]:
                return False

    return True


##### advanced solver sub-function 1 - find if a tile is on the frontier 

def is_frontier_tile(x, y, revealed, flags):
    if revealed[y][x] or flags[y][x]:
        return False

    for nx, ny in get_neighbours(x, y):
        if revealed[ny][nx] and numbers[ny][nx] > 0:
            return True

    return False
# a frontier tile is: not revealed, not flagged, touches at least one revealed tile with > 0 number


##### advanced solver sub-function 2 - arrange frontier tiles into sets

def build_number_to_frontier_map(revealed, flags):
    mapping = {}

    for y in range(GRID_H):
        for x in range(GRID_W):
            if revealed[y][x] and numbers[y][x] > 0:
                adj = set() # no duplicates, order not important
                for nx, ny in get_neighbours(x, y):
                    if is_frontier_tile(nx, ny, revealed, flags):
                        adj.add((nx, ny))
                if adj:
                    mapping[(x, y)] = adj

    return mapping
    # mapping =
    #{ (3, 4): {(2, 4), (3, 5)}, 
    #  (5, 4): {(5, 5), (6, 5)...} ... }
    # where (3,4) is a revealed tile with number > 0. (2,4) & (3,5) are two frontier tiles connected to (3,4)


##### advanced solver sub-function 3 - re-arrange frontier tiles from the sets into frontier groups

def build_frontier_groups(revealed, flags):
    number_map = build_number_to_frontier_map(revealed, flags)

    groups = [] # will be the final list of frontier groups
    visited = set() # contains all frontier tiles already placed in a group
    
    for frontier_set in number_map.values(): # pick one set of frontier tiles
        for tile in frontier_set: # pick one frontier tile from this set
            if tile in visited: # if this tile is already assigned, move to next tile
                continue

            group = set() # start a new group - will later be appended to "groups"
            stack = [tile]

            while stack:
                t = stack.pop()
                if t in visited:
                    continue

                visited.add(t) # tile t will not be visited again
                group.add(t) # tile t is assigned to this group

                for adj in number_map.values(): # pick a second set of frontier tiles
                    if t in adj: # if tile t is also present in this second set...
                        for other in adj: # ... add the tiles from that second set to the stack
                            if other not in visited:
                                stack.append(other)

            groups.append(group)

    return groups


##### advanced solver sub-function 4 - within each frontier group, find the exact number of mines hidden

def extract_constraints_for_group(group, revealed, flags):
    constraints = []

    for y in range(GRID_H):
        for x in range(GRID_W):
            if not revealed[y][x]:
                continue
            n = numbers[y][x]
            if n == 0:
                continue

            frontier = []
            flagged = 0

            for nx, ny in get_neighbours(x, y):
                if flags[ny][nx]:
                    flagged += 1
                elif (nx, ny) in group:
                    frontier.append((nx, ny))

            if frontier:
                constraints.append({
                    "tiles": frontier,
                    "count": n - flagged
                })

    return constraints
# constraint = { "tiles": [(3,4), (4,4), (5,4)], "count": 2 }
#              ...


##### advanced solver sub-function 5 - convert "constraint" in an easier format to read for Tufty (indices instead of coordinates)

def index_constraints(constraints, index_map):
#    indexed = []
#
#    for c in constraints:
#        idxs = [index_map[t] for t in c["tiles"]]
#        indexed.append((idxs, c["count"]))
#
#    return indexed
    indexed = []
    for c in constraints:
        m = 0
        for t in c["tiles"]:
            m |= (1 << index_map[t])
        indexed.append((m, c["count"]))
    return indexed
# indexed = ([1, 2, 3], 2)    among tiles 1, 2, 3, there are two traps
#           ...


##### advanced solver sub-function 6 - enumerate mine assignments

#def enumerate_group(group_size, constraints):
#    valid_masks = []
#
#    for mask in range(1 << group_size): # 1 << group_size = 2^group_size: total nb of possible trap patterns in the group
#        ok = True # assume this patern is correct, then try to falsify it
#
#        for idxs, count in constraints: # among all tiles indexed in idxs, count must be traps
#            c = 0
#            for i in idxs:
#                if mask & (1 << i):
#                    c += 1
#                    # & is bitwise version of AND, so (1 << i) is interpreted as the bit shifter in that case.
#                    # For each tile in idxs, count how many of them are marked as mines in this mask.
#            if c != count:
#                ok = False
#                break
#
#        if ok:
#            valid_masks.append(mask)
#
#    return valid_masks
def popcount(x):
    c = 0
    while x:
        x &= x - 1   # drop lowest set bit
        c += 1
    return c
def enumerate_group(group_size, constraints):
    valid_masks = []

    # constraints is already: [(cmask, count), ...]

    for mask in range(1 << group_size):
        ok = True

        for cmask, count in constraints:
            if popcount(mask & cmask) != count:
                ok = False
                break

        if ok:
            valid_masks.append(mask)

    return valid_masks


##### advanced solver sub-function 7 - deduction: finds certainly safe and certainly trapped tiles

def deduce_from_masks(masks, group_size):
    if not masks:
        return {}, {}

    always_mine = [True] * group_size
    always_safe = [True] * group_size

    for mask in masks:
        for i in range(group_size):
            if mask & (1 << i): # true if i is a mine in this mask
                always_safe[i] = False # not safe for sure because i is a mine in this mask
            else:
                always_mine[i] = False # not trapped for sure because i is not a mine in this mask

    mines = set(i for i in range(group_size) if always_mine[i])
    safe = set(i for i in range(group_size) if always_safe[i])

    return mines, safe


##### advanced solver sub-function 8

def apply_group_deductions(group_tiles, mine_idxs, safe_idxs, flags, revealed):
    progress = False

    for i in mine_idxs:
        x, y = group_tiles[i]
        if not flags[y][x]:
            flags[y][x] = True
            progress = True

    for i in safe_idxs:
        x, y = group_tiles[i]
        if not revealed[y][x]:
            revealed[y][x] = True
            progress = True

    return progress


##### advanced solver sub-function 9

def solve_frontier_group(group, revealed, flags):
    group_tiles = list(group)
    if len(group_tiles) > MAX_GROUP:
        return False

    index = {t: i for i, t in enumerate(group_tiles)}

    constraints = extract_constraints_for_group(group, revealed, flags)
    indexed = index_constraints(constraints, index)

    masks = enumerate_group(len(group_tiles), indexed)
    if not masks:
        return False

    mines, safe = deduce_from_masks(masks, len(group_tiles))
    return apply_group_deductions(group_tiles, mines, safe, flags, revealed)


##### advanced solver main

def solver_advanced(start_x, start_y):
    s_revealed = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]
    s_flags = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]

    stack = [(start_x, start_y)]

    # rule 1
    while stack:
        x, y = stack.pop()
        if s_revealed[y][x]:
            continue
        if mines[y][x]:
            return False

        s_revealed[y][x] = True

        if numbers[y][x] == 0:
            for nx, ny in get_neighbours(x, y):
                if not s_revealed[ny][nx]:
                    stack.append((nx, ny))

    progress = True

    while progress:
        progress = False

        # rules 2 & 3
        for y in range(GRID_H):
            for x in range(GRID_W):
                if not s_revealed[y][x]:
                    continue
                if numbers[y][x] == 0:
                    continue

                hidden = []
                flagged = 0

                for nx, ny in get_neighbours(x, y):
                    if s_flags[ny][nx]:
                        flagged += 1
                    elif not s_revealed[ny][nx]:
                        hidden.append((nx, ny))

                # rule 2
                if hidden and numbers[y][x] == flagged + len(hidden):
                    for nx, ny in hidden:
                        if not s_flags[ny][nx]:
                            s_flags[ny][nx] = True
                            progress = True

                # rule 3
                if hidden and numbers[y][x] == flagged:
                    for nx, ny in hidden:
                        if not s_revealed[ny][nx]:
                            s_revealed[ny][nx] = True
                            progress = True
                            if numbers[ny][nx] == 0:
                                stack.append((nx, ny))

        # rule 4
        for y1 in range(GRID_H):
            for x1 in range(GRID_W):
                if not s_revealed[y1][x1]:
                    continue
                if numbers[y1][x1] == 0:
                    continue

                for x2, y2 in get_neighbours(x1, y1):
                    if not s_revealed[y2][x2]:
                        continue
                    if numbers[y2][x2] == 0:
                        continue

                    made, newly = apply_subset_rule(x1, y1, x2, y2, s_revealed, s_flags)
                    if made:
                        progress = True
                        for x, y in newly:
                            if numbers[y][x] == 0:
                                stack.append((x, y))

        # rule 5 - frontiere grouping
        if not progress:
            frontier_groups = build_frontier_groups(s_revealed, s_flags)
            for group in frontier_groups:
                if solve_frontier_group(group, s_revealed, s_flags):
                    progress = True

    for y in range(GRID_H):
        for x in range(GRID_W):
            if not mines[y][x] and not s_revealed[y][x]:
                return False

    return True


#################### Instructions ####################  

def instructions():    
    options = ["Skip & play", "Exit game"]
    selected_option = 0
    scroll = 0
    
    pressed = False
    
    while True:
        display.set_pen(BLACK)
        display.clear()
    
        display.set_pen(GREEN)
        display.set_font("bitmap8")
        display.text("Instructions", 15, 10 + scroll, scale=3)
        
        display.text("'a' to move left.", 15, 50 + scroll, scale=2)
        display.text("'c' to move right.", 15, 75 + scroll, scale=2)
        display.text("'up' to move up.", 15, 100 + scroll, scale=2)
        display.text("'down' to move down.", 15, 125 + scroll, scale=2)
        display.text("'b' to select.", 15, 160 + scroll, scale=2)
        
        display.text("While in game...", 15, 200 + scroll, scale=2)
        
        display.text("Short 'b' reveals a tile.", 15, 240 + scroll, scale=2)
        
        display.text("Once revealed, the tile either", 15, 280 + scroll, scale=2)
        display.text("* shows the number of", 40, 305 + scroll, scale=2)
        display.text("neighbouring traps,", 57, 330 + scroll, scale=2)
        display.text("* turns red if it is trapped !", 40, 355 + scroll, scale=2)
        
        display.text("Long 'b' plants a flag (it turns", 15, 395 + scroll, scale=2)
        display.text("the tile orange).", 15, 420 + scroll, scale=2)
        
        display.text("While the cursor is on a flag,", 15, 460 + scroll, scale=2)
        display.text("long 'b' removes the flag (but", 15, 485 + scroll, scale=2)
        display.text("does not reveal the tile).", 15, 510 + scroll, scale=2)
        
        display.text("You win after revealing all the", 15, 550 + scroll, scale=2)
        display.text("tiles that do not hide a trap", 15, 575 + scroll, scale=2)
        display.text("(irrespective of flags).", 15, 600 + scroll, scale=2)
        
        display.set_pen(GREEN)
        display.text("End of instructions.", 65, 700 + scroll, scale=2)
        
        display.set_pen(ORANGE) # arrows
        size = 10
        x = 310
        y = 160
        display.line(x, y, x, y + size)
        display.line(x, y + size, x - size // 2, y + size - size // 2)
        display.line(x, y + size, x + size // 2, y + size - size // 2)
        display.line(x+1, y, x+1, y + size)
        display.line(x+1, y + size, x+1 - size // 2, y + size - size // 2)
        display.line(x+1, y + size, x+1 + size // 2, y + size - size // 2)
        size = 10
        x = 310
        y = 66
        display.line(x, y, x, y + size)
        display.line(x, y, x + size // 2, y + size // 2)
        display.line(x, y, x - size // 2, y + size // 2)
        display.line(x+1, y, x+1, y + size)
        display.line(x+1, y, x+1 + size // 2, y + size // 2)
        display.line(x+1, y, x+1 - size // 2, y + size // 2)
        
        display.set_pen(GREY)
        display.rectangle(0, 211, WIDTH, 3)
        display.set_pen(BLACK)
        display.rectangle(0, 214, WIDTH, 28)
        
        if selected_option == 0:
            display.set_pen(ORANGE)
            display.text("> Skip & play", 10, 219, scale=2)
            display.set_pen(ORANGE // 2)
            display.text("Exit game", 200, 219, scale=2)
        else:
            display.set_pen(ORANGE // 2)
            display.text("Skip & play", 10, 219, scale=2)
            display.set_pen(ORANGE)
            display.text("> Exit game", 200, 219, scale=2)
            
        display.update()
        
        if button_left.read():
            selected_option = (selected_option - 1) % len(options)
            time.sleep(0.02)
            
        if button_right.read():
            selected_option = (selected_option + 1) % len(options)
            time.sleep(0.02)
            
        if button_down.read():
            scroll = scroll - 9
        
        if button_up.read():
            scroll = scroll + 9
            
        if button_reveal.read():
            pressed = True
            
        if not button_reveal.is_pressed and pressed:
        
            if options[selected_option] == "Skip & play":
                return STATE_PLAY
            
            if options[selected_option] == "Exit game":
                exit_game()




#################### start-of-game functions ####################


##### question about size of grid
            
def grid_q():
    display.set_pen(BLACK)
    display.clear()
    
    display.set_pen(GREEN)
    display.set_font("bitmap8")
    
    TEXT = "Which grid size would you like ?"
    display.text(TEXT, 10, 50, scale=2)
    
    options = ["Small", "Medium", "Large"]
    selected_option = 0
    pressed = False
    
    while True:
        display.set_pen(BLACK)
        display.rectangle(0, 70, WIDTH, 150)
        
        if selected_option == 0:
            display.set_pen(GREEN)
            display.text("> Small  (8*8 tiles, 10 traps)", 10, 100, scale=2)
            display.set_pen(GREEN // 2)
            display.text("Medium  (8*10 tiles, 15 traps)", 10, 150, scale=2)
            display.set_pen(GREEN // 2)
            display.text("Large  (10*13 tiles, 20 traps)", 10, 200, scale=2)
        elif selected_option == 1:
            display.set_pen(GREEN // 2)
            display.text("Small  (8*8 tiles, 10 traps)", 10, 100, scale=2)
            display.set_pen(GREEN)
            display.text("> Medium  (8*10 tiles, 15 traps)", 10, 150, scale=2)
            display.set_pen(GREEN // 2)
            display.text("Large  (10*13 tiles, 20 traps)", 10, 200, scale=2)
        elif selected_option == 2:
            display.set_pen(GREEN // 2)
            display.text("Small  (8*8 tiles, 10 traps)", 10, 100, scale=2)
            display.set_pen(GREEN // 2)
            display.text("Medium  (8*10 tiles, 15 traps)", 10, 150, scale=2)
            display.set_pen(GREEN)
            display.text("> Large  (10*13 tiles, 20 traps)", 10, 200, scale=2)
            
        display.update()
        
        if button_up.read():
            selected_option = (selected_option - 1) % len(options)
            time.sleep(0.02)
            
        if button_down.read():
            selected_option = (selected_option + 1) % len(options)
            time.sleep(0.02)
        
        if button_reveal.read():
            pressed = True
            
        if not button_reveal.is_pressed and pressed:
            
            if options[selected_option] == "Small":
                return "small"
            
            if options[selected_option] == "Medium":
                return "medium"
            
            if options[selected_option] == "Large":
                return "large"
                
                
##### question about using solver

def use_solver_q():
    display.set_pen(BLACK)
    display.clear()
    
    display.set_pen(GREEN)
    display.set_font("bitmap8")
    
    TEXT = "Would you like to make sure that"
    display.text(TEXT, 10, 50, scale=2)
    TEXT = "the board is solvable without"
    display.text(TEXT, 10, 80, scale=2)
    TEXT = "having to rely on luck ?"
    display.text(TEXT, 10, 110, scale=2)
    
    options = ["Yes", "No"]
    selected_option = 0
    pressed = False
    
    while True:
        display.set_pen(BLACK)
        display.rectangle(0, 170, WIDTH, 30)
        
        if selected_option == 0:
            display.set_pen(GREEN)
            display.text("> Yes", 95, 180, scale=2)
            display.set_pen(GREEN // 2)
            display.text("No", 190, 180, scale=2)
        else:
            display.set_pen(GREEN // 2)
            display.text("Yes", 95, 180, scale=2)
            display.set_pen(GREEN)
            display.text("> No", 190, 180, scale=2)
            
        display.update()
        
        if button_right.read():
            selected_option = (selected_option - 1) % len(options)
            time.sleep(0.02)
            
        if button_left.read():
            selected_option = (selected_option + 1) % len(options)
            time.sleep(0.02)
            
        if button_reveal.read():
            pressed = True
            
        if not button_reveal.is_pressed and pressed:
            
            if options[selected_option] == "No":
                return False
            
            if options[selected_option] == "Yes":
                return True
            
            
##### question about difficulty level
            
def difficulty_q_solver():
    display.set_pen(BLACK)
    display.clear()

    display.set_pen(GREEN)
    display.set_font("bitmap8")
    display.text("Which difficulty level would", 20, 40, scale=2)
    display.text("you like ?", 20, 70, scale=2)

    options = ["Easy", "Medium", "Difficult"]
    selected_option = 0
    pressed = False

    while True:
        display.set_pen(BLACK)
        display.rectangle(0, 100, WIDTH, 130)
        
        if selected_option == 0:
            display.set_pen(GREEN)
            display.text("> Easy", 125, 120, scale=2)
            display.set_pen(GREEN // 2)
            display.text("Medium", 125, 160, scale=2)
            display.set_pen(GREEN // 2)
            display.text("Difficult", 125, 200, scale=2)
        elif selected_option == 1:
            display.set_pen(GREEN // 2)
            display.text("Easy", 125, 120, scale=2)
            display.set_pen(GREEN)
            display.text("> Medium", 125, 160, scale=2)
            display.set_pen(GREEN // 2)
            display.text("Difficult", 125, 200, scale=2)
        elif selected_option == 2:
            display.set_pen(GREEN // 2)
            display.text("Easy", 125, 120, scale=2)
            display.set_pen(GREEN // 2)
            display.text("Medium", 125, 160, scale=2)
            display.set_pen(GREEN)
            display.text("> Difficult", 125, 200, scale=2)

        display.update()
        
        if button_down.read():
            selected_option = (selected_option + 1) % len(options)
            time.sleep(0.02)
            
        if button_up.read():
            selected_option = (selected_option - 1) % len(options)
            time.sleep(0.02)

        if button_reveal.read():
            pressed = True
            
        if not button_reveal.is_pressed and pressed:
            
            if options[selected_option] == "Easy":
                return "easy"
            
            if options[selected_option] == "Medium":
                return "medium"
            
            if options[selected_option] == "Difficult":
                return "difficult"


##### question about using flood reveal

def use_flood_q():
    display.set_pen(BLACK)
    display.clear()
    
    display.set_pen(GREEN)
    display.set_font("bitmap8")
    
    TEXT = "Would you like to enable flood-"
    display.text(TEXT, 10, 45, scale=2)
    display.text("reveal ?", 10, 70, scale=2)
    TEXT = "Meaning that empty areas will"
    display.text(TEXT, 10, 110, scale=2)
    TEXT = "automatically be revealed."
    display.text(TEXT, 10, 135, scale=2)
    
    options = ["Yes", "No"]
    selected_option = 0
    pressed = False
    
    while True:
        display.set_pen(BLACK)
        display.rectangle(0, 170, WIDTH, 30)
        
        if selected_option == 0:
            display.set_pen(GREEN)
            display.text("> Yes", 95, 185, scale=2)
            display.set_pen(GREEN // 2)
            display.text("No", 190, 185, scale=2)
        else:
            display.set_pen(GREEN // 2)
            display.text("Yes", 95, 185, scale=2)
            display.set_pen(GREEN)
            display.text("> No", 190, 185, scale=2)
            
        display.update()
        
        if button_right.read():
            selected_option = (selected_option - 1) % len(options)
            time.sleep(0.02)
            
        if button_left.read():
            selected_option = (selected_option + 1) % len(options)
            time.sleep(0.02)
            
        if button_reveal.read():
            pressed = True
            
        if not button_reveal.is_pressed and pressed:
            
            if options[selected_option] == "No":
                display.set_pen(BLACK)
                display.rectangle(0, 0, WIDTH, HEIGHT)
                display.set_pen(GREEN)
                display.text("Play", WIDTH // 2 - 30, HEIGHT // 2 - 15, scale=3)
                display.update()
                time.sleep(0.7)
                return False
            
            if options[selected_option] == "Yes":
                display.set_pen(BLACK)
                display.rectangle(0, 0, WIDTH, HEIGHT)
                display.set_pen(GREEN)
                display.text("Play", WIDTH // 2 - 30, HEIGHT // 2 - 15, scale=3)
                display.update()
                time.sleep(0.7)
                return True




#################### in-game functions ####################


##### Question about continuing game despite mistakes

def mistakes_q():
    display.set_pen(BLACK)
    display.clear()
    
    display.set_pen(GREEN)
    display.set_font("bitmap8")
    
    TEXT = "You fell into a trap..."
    display.text(TEXT, 9, 40, scale=3)
    
    options = ["Continue the game", "Start a new game", "Exit"]
    selected_option = 0
    
    while True:
        display.set_pen(BLACK)
        display.rectangle(0, 100, WIDTH, 200)
        
        if selected_option == 0:
            display.set_pen(GREEN)
            display.text("> Continue the game", 70, 100, scale=2)
            display.set_pen(GREEN // 2)
            display.text("Start a new game", 70, 130, scale=2)
            display.set_pen(GREEN // 2)
            display.text("Exit", 70, 160, scale=2)
        elif selected_option == 1:
            display.set_pen(GREEN // 2)
            display.text("Continue the game", 70, 100, scale=2)
            display.set_pen(GREEN)
            display.text("> Start a new game", 70, 130, scale=2)
            display.set_pen(GREEN // 2)
            display.text("Exit", 70, 160, scale=2)
        elif selected_option == 2:
            display.set_pen(GREEN // 2)
            display.text("Continue the game", 70, 100, scale=2)
            display.set_pen(GREEN // 2)
            display.text("Start a new game", 70, 130, scale=2)
            display.set_pen(GREEN)
            display.text("> Exit", 70, 160, scale=2)
            
        display.update()
        
        if button_up.read():
            selected_option = (selected_option - 1) % len(options)
            time.sleep(0.02)
            
        if button_down.read():
            selected_option = (selected_option + 1) % len(options)
            time.sleep(0.02)
            
        if button_reveal.read():
            
            if options[selected_option] == "Continue the game":
                return STATE_PLAY
            if options[selected_option] == "Start a new game":
                return STATE_ANEW
            if options[selected_option] == "Exit":
                exit_game()


##### Display time in game

def format_time(seconds):
    if seconds < 60:
        return f"{seconds}"

    minutes = seconds // 60
    secs = seconds % 60

    if minutes < 60:
        return f"{minutes}:{secs:02d}"

    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}:{mins:02d}:{secs:02d}"


##### auto-reveal connected tiles with 0 neighbouring traps

def auto_reveal(start_x, start_y):
    stack = [(start_x, start_y)]

    while stack:
        x, y = stack.pop()

        if revealed[y][x]:
            continue
        if flags[y][x]:
            continue

        revealed[y][x] = True

        # If this tile is truly not trapped, find and reveal neighbouring empty tiles (if any)
        if numbers[y][x] == 0:
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue

                    nx = x + dx
                    ny = y + dy

                    if 0 <= nx < GRID_W and 0 <= ny < GRID_H:
                        if not revealed[ny][nx] and not mines[ny][nx]:
                            stack.append((nx, ny))




#################### end-of-game functions ####################


##### check if game is won / complete

def check_win(): # win = all remaining covered tiles hide traps 
    for y in range(GRID_H):
        for x in range(GRID_W):
            if not mines[y][x] and not revealed[y][x]:
                return False
    return True


##### congratulations if game won

def congratulations():
    selected_option = 0    
    STAR_COUNT = 30
    stars = []
    
    for _ in range(STAR_COUNT):
        stars.append({
            "x": random.randint(0, WIDTH - 1),
            "y": random.randint(0, HEIGHT - 1),
            "speed": random.uniform(0.5, 2.0)
        })
        
    options = ["Yes", "No"]
    selected_option = 0
    
    while True:
        display.set_pen(BLACK)
        display.clear()

        display.set_pen(STARS)
        for star in stars:
            star["y"] += star["speed"]

            if star["y"] > HEIGHT:
                star["y"] = - 2
                star["x"] = random.randint(0, WIDTH - 1)
                star["speed"] = random.uniform(0.5, 2.0)

            display.pixel(int(star["x"])+1, int(star["y"]))
            display.pixel(int(star["x"]), int(star["y"])+1)
            display.pixel(int(star["x"])-1, int(star["y"]))
            display.pixel(int(star["x"]), int(star["y"])-1)

        display.set_pen(ORANGE)
        text = "play time = " + format_time((elapsed_time - paused_time_total) // 1000)
        display.text(text, 5, HEIGHT - 19, scale=2)
        display.set_pen(GREEN)
        display.set_font("bitmap8")
        display.text("Congratulations !", 45, 40, scale=3)
        display.text("You won.", 100, 80, scale=3)
        display.text("Play again ?", 105, 144, scale=2)

        display.set_pen(BLACK)
        display.rectangle(109, 179, 100, 17)

        if selected_option == 0:
            display.set_pen(GREEN)
            display.text("> Yes", 110, 180, scale=2)
            display.set_pen(GREEN // 2)
            display.text("No", 175, 180, scale=2)
        else:
            display.set_pen(GREEN // 2)
            display.text("Yes", 110, 180, scale=2)
            display.set_pen(GREEN)
            display.text("> No", 175, 180, scale=2)

        display.update()
        time.sleep(0.02)
        
        if button_right.read():
            selected_option = (selected_option - 1) % len(options)
            time.sleep(0.02)
            
        if button_left.read():
            selected_option = (selected_option + 1) % len(options)
            time.sleep(0.02)
            
        if button_reveal.read():
            time.sleep(0.02)
            display.set_pen(BLACK)
            display.rectangle(109, 179, 100, 17)
            display.set_pen(GREEN)
            display.text(f"{options[selected_option]}", 142, 180, scale=2)
            display.update()
            time.sleep(1)
            
            if options[selected_option] == "No":
                return False
            if options[selected_option] == "Yes":
                return True


##### less enthusiastic congratulations if game complete but lost

def complete():
    display.set_pen(BLACK)
    display.clear()
    
    display.set_pen(ORANGE)
    text = "play time = " + format_time((elapsed_time - paused_time_total) // 1000)
    display.text(text, 5, HEIGHT - 19, scale=2)
    display.set_pen(GREEN)
    display.set_font("bitmap8")
    display.text("Congratulations, you", 15, 25, scale=3)
    display.text("found all the traps", 22, 60, scale=3)
    display.text("... but you fell into some of them.", 5, 110, scale=2)
    display.text("Play again ?", 105, 158, scale=2)
    options = ["Yes", "No"]
    selected_option = 0
    
    while True:
        display.set_pen(BLACK)
        display.rectangle(90, 190, WIDTH, 30)
        
        if selected_option == 0:
            display.set_pen(GREEN)
            display.text("> Yes", 100, 190, scale=2)
            display.set_pen(GREEN // 2)
            display.text("No", 185, 190, scale=2)
        else:
            display.set_pen(GREEN // 2)
            display.text("Yes", 100, 190, scale=2)
            display.set_pen(GREEN)
            display.text("> No", 185, 190, scale=2)
            
        display.update()
        
        if button_left.read():
            selected_option = (selected_option - 1) % len(options)
            time.sleep(0.02)
            
        if button_right.read():
            selected_option = (selected_option + 1) % len(options)
            time.sleep(0.02)
            
        if button_reveal.read():
            
            if options[selected_option] == "Yes":
                return True
            if options[selected_option] == "No":
                return False


##### reset game

def reset_game():
    global press_start, long_press_used, mistakes, first_click
    global ask_grid_q, ask_solver_q, ask_flood_q, ask_mistakes_q, ask_mistakes_q_v2, list_mistakes, ask_difficulty_q
    global game_start_time, game_end_time, elapsed_time, paused_time_total, pause_time
    global cursor_x, cursor_y
    
    press_start = None
    long_press_used = False
    mistakes = False
    first_click = True
    
    ask_grid_q = True
    ask_solver_q = True
    ask_flood_q = True
    ask_mistakes_q = True
    ask_mistakes_q_v2 = False
    list_mistakes = []
    ask_difficulty_q = True
    difficulty = "easy"
    game_start_time = None
    game_end_time = None
    elapsed_time = 0
    paused_time_total = 0
    pause_time = None
    
    cursor_x = 0
    cursor_y = 0


##### exit game
    
def exit_game():
    display.set_pen(BLACK)
    display.clear()
    display.set_pen(GREEN)
    display.text("Exiting...", 100, 110, scale=3)
    display.update()
    time.sleep(0.7)
    machine.reset()




    

##### main loop

while True:
    if state == STATE_INIT:
        state = instructions()
        
    if state == STATE_PLAY:
        
        if ask_grid_q:
            dim = grid_q()
            
            if dim == "small":
                GRID_W = 8
                GRID_H = 8
                MINES = 10
                CELL = 29 # size of each cell. H = 8×29 = 232 px (< 240), W = 8*29 = 232 px (< 320)
                GAP = 2 # gap between tiles
                x_buffer = 7 # to place numbers at center of tiles 
                y_buffer = 2
                OFFSET_X = (WIDTH  - GRID_W * CELL) // 2 # how far from the left edge of the screen to start drawing the grid
                OFFSET_Y = (HEIGHT - GRID_H * CELL) // 2 # how far from the top edge ...
                cursor_x = 0
                cursor_y = 0
                revealed = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]
                mines = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]
                numbers = [[0 for _ in range(GRID_W)] for _ in range(GRID_H)]
                flags = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]
            elif dim == "medium":
                GRID_W = 10
                GRID_H = 8
                MINES = 15
                CELL = 29 # size of each cell. H = 8×29 = 232 px (< 240), W = 10*29 = 290 px (< 320)
                GAP = 2 # gap between tiles
                x_buffer = 7 # to place numbers at center of tiles 
                y_buffer = 2
                OFFSET_X = (WIDTH  - GRID_W * CELL) // 2 # how far from the left edge of the screen to start drawing the grid
                OFFSET_Y = (HEIGHT - GRID_H * CELL) // 2 # how far from the top edge ...
                cursor_x = 0
                cursor_y = 0
                revealed = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]
                mines = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]
                numbers = [[0 for _ in range(GRID_W)] for _ in range(GRID_H)]
                flags = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]
            elif dim == "large":
                GRID_W = 13
                GRID_H = 10
                MINES = 20
                CELL = 24 # size of each cell. H = 10×24 = 240 px (the max), W = 13*24 = 312 px (< 320)
                GAP = 2 # gap between tiles
                x_buffer = 7 # to place numbers at center of tiles 
                y_buffer = 0
                OFFSET_X = (WIDTH  - GRID_W * CELL) // 2 # how far from the left edge of the screen to start drawing the grid
                OFFSET_Y = 1 # how far from the top edge ...
                cursor_x = 0
                cursor_y = 0
                revealed = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]
                mines = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]
                numbers = [[0 for _ in range(GRID_W)] for _ in range(GRID_H)]
                flags = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]
                
            ask_grid_q = False
            time.sleep(0.1)
                
        if ask_solver_q:
            use_solver = use_solver_q()
            ask_solver_q = False
            time.sleep(0.1)
            
        if use_solver and ask_difficulty_q:
            difficulty = difficulty_q_solver()
            ask_difficulty_q = False
            time.sleep(0.1)
            
        if ask_flood_q:
            use_flood = use_flood_q()
            ask_flood_q = False
        
        if button_left.read():
            cursor_x = max(0, cursor_x - 1)

        if button_right.read():
            cursor_x = min(GRID_W - 1, cursor_x + 1)

        if button_up.read():
            cursor_y = max(0, cursor_y - 1)
            
        if button_down.read():
            cursor_y = min(GRID_H - 1, cursor_y + 1)
            
        if game_start_time is not None:
            elapsed_time = time.ticks_diff(time.ticks_ms(), game_start_time)

        if button_reveal.is_pressed:
            
            if first_click:
                
                if use_solver:
                    display.set_pen(BLACK)
                    display.clear()
                    display.set_pen(GREEN)
                    display.set_font("bitmap8")
                    display.text("Making sure the game is solvable.", 5, 40, scale=2)
                    display.text(f"please wait a sec...", 70, 80, scale=2)
                    display.text(f"Difficulty {difficulty}", 80, 140, scale=2)
                    display.update()
                    
                    solver_count = 0
                    
                    while True:
                        solver_count += 1
                        
                        mines = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]
                        place_mines_avoiding(cursor_x, cursor_y)
                        compute_numbers()
                        
                        if difficulty == "easy":
                            display.set_pen(BLACK)
                            display.rectangle(4, 199, WIDTH, 100)
                            display.set_pen(ORANGE)
                            display.text(f"solver attempts {solver_count}", 5, 200, scale=2)
                            display.update()
                            if solver_basic(cursor_x, cursor_y):
                                break
                            
                        elif difficulty == "medium":
                            display.set_pen(BLACK)
                            display.rectangle(4, 199, WIDTH, 100)
                            display.set_pen(ORANGE)
                            display.text(f"solver attempts {solver_count}", 5, 200, scale=2)
                            display.update()
                            if not solver_basic(cursor_x, cursor_y) and solver_medium(cursor_x, cursor_y):
                                break
                            
                        elif difficulty == "difficult":
                            display.set_pen(BLACK)
                            display.rectangle(4, 199, WIDTH, 100)
                            display.set_pen(ORANGE)
                            display.text(f"solver attempts {solver_count}", 5, 200, scale=2)
                            display.update()
                            
                            # Must fail easy & medium, but pass advanced
                            if (not solver_basic(cursor_x, cursor_y)
                                and not solver_medium(cursor_x, cursor_y)
                                and solver_advanced(cursor_x, cursor_y)):
                                break
                        
                if not use_solver:
                    mines = [[False for _ in range(GRID_W)] for _ in range(GRID_H)]
                    place_mines_avoiding(cursor_x, cursor_y)
                    compute_numbers()
                    
                if game_start_time is None:
                    game_start_time = time.ticks_ms()
                    paused_time_total = 0
                        
                first_click = False
                
                if use_flood:
                    auto_reveal(cursor_x, cursor_y)
                elif not use_flood:
                     revealed[cursor_y][cursor_x] = True   
                
            else:
                if press_start is None:
                    # button just pressed
                    press_start = time.ticks_ms()
                    #press_start = time.time()
                    long_press_used = False
                else:
                    # button still being held
                    if not long_press_used and time.ticks_diff(time.ticks_ms(), press_start) >= FLAG_HOLD_TIME:
                        # long press, plants/removes flag
                        flags[cursor_y][cursor_x] = not flags[cursor_y][cursor_x]
                        long_press_used = True
        else:
            # button released
            if press_start is not None:
                if not long_press_used:
                    # short press, reveals tile (if not already flagged)
                    if not flags[cursor_y][cursor_x] and not revealed[cursor_y][cursor_x]:
                        if use_flood:
                            if not mines[cursor_y][cursor_x]:
                                auto_reveal(cursor_x, cursor_y)
                            else:
                                revealed[cursor_y][cursor_x] = True
                        elif not use_flood:
                            revealed[cursor_y][cursor_x] = True

            press_start = None
            long_press_used = False                
        
        # draw updated grid + cursor
        display.set_pen(BLACK)
        display.clear()
        
        # cursor
        cx = OFFSET_X + cursor_x * CELL
        cy = OFFSET_Y + cursor_y * CELL
        display.set_pen(YELLOW)
        display.rectangle(cx - GAP, cy - GAP, CELL + GAP, CELL + GAP)
        
        # grid
        for y in range(GRID_H):
            for x in range(GRID_W):
                px = OFFSET_X + x * CELL
                py = OFFSET_Y + y * CELL

                if revealed[y][x]:
                    if mines[y][x]:
                        display.set_pen(RED) 
                        display.rectangle(px, py, CELL - GAP, CELL - GAP)
                    else:
                        display.set_pen(WHITE)
                        display.rectangle(px, py, CELL - GAP, CELL - GAP)
                        
                        if use_flood:
                            if numbers[y][x] > 0:
                                display.set_pen(BLACK)
                                display.text(str(numbers[y][x]), px + x_buffer, py + y_buffer, scale=3)
                        elif not use_flood:
                            if numbers[y][x] >= 0:
                                display.set_pen(BLACK)
                                display.text(str(numbers[y][x]), px + x_buffer, py + y_buffer, scale=3)
                        
                else:
                    if flags[y][x]:
                        display.set_pen(ORANGE)
                        display.rectangle(px, py, CELL - GAP, CELL - GAP)
                    else:
                        display.set_pen(GREY)
                        display.rectangle(px, py, CELL - GAP, CELL - GAP)
                
                ## to make question about mistakes appear first mistake only:
                if mines[y][x] and revealed[y][x]:
                    mistakes = True
                ## to make question about mistakes appear after each mistake:
                #if mines[y][x] and revealed[y][x] and (x,y) not in list_mistakes:
                #    list_mistakes.append((x, y))
                #    ask_mistakes_q_v2 = True
                #    mistakes = True    
        
        display.set_pen(YELLOW)
        display.set_font("bitmap6")
        text = format_time((elapsed_time - paused_time_total) // 1000)
        if cx < WIDTH // 2 and cy < HEIGHT // 2:
            display.text(text, WIDTH - len(text) * 12, HEIGHT - OFFSET_Y - 14, scale=2)
        if cx >= WIDTH // 2 and cy < HEIGHT // 2:
            display.text(text, 1, HEIGHT - OFFSET_Y - 14, scale=2)
        if cx < WIDTH // 2 and cy >= HEIGHT // 2:
            display.text(text, WIDTH - len(text) * 12, OFFSET_Y, scale=2)
        if cx >= WIDTH // 2 and cy >= HEIGHT // 2:
            display.text(text, 1, OFFSET_Y, scale=2)
        display.set_font("bitmap8")
        
        
#        frontier_groups = build_frontier_groups(revealed, flags)

#        for i, group in enumerate(frontier_groups):
#            colour = FRONTIER_COLOURS[i % len(FRONTIER_COLOURS)]
#            display.set_pen(colour)
            
#            for x, y in group:
#                px = OFFSET_X + x * CELL
#                py = OFFSET_Y + y * CELL
#                display.rectangle(px + 4, py + 4, CELL - 8, CELL - 8)
        
        
        display.update()
        
        ## to make question about mistakes appear after first mistake only:
        if mistakes and ask_mistakes_q:
            pause_start_ticks = time.ticks_ms()
            time.sleep(0.5)
            state = mistakes_q()
            ask_mistakes_q = False
            paused_time_total += time.ticks_diff(time.ticks_ms(), pause_start_ticks)
        ## to make question about mistakes appear after each mistake:
        #if ask_mistakes_q_v2:
        #    pause_start_ticks = time.ticks_ms()
        #    time.sleep(0.5)
        #    state = mistakes_q()
        #    ask_mistakes_q_v2 = False
        #    paused_time_total += time.ticks_diff(time.ticks_ms(), pause_start_ticks)
        
        if check_win() and not mistakes:
            game_end_time = time.ticks_ms()
            elapsed_time = time.ticks_diff(game_end_time, game_start_time)
            state = STATE_WIN
                        
        if check_win() and mistakes:
            game_end_time = time.ticks_ms()
            elapsed_time = time.ticks_diff(game_end_time, game_start_time)
            state = STATE_COMPLETE
        
        if state == STATE_WIN or state == STATE_COMPLETE:
            time.sleep(0.5)
        
    if state == STATE_WIN:
        if congratulations():
            reset_game()
            state = STATE_PLAY
        else:
            exit_game()
            
    if state == STATE_COMPLETE:
        if complete():
            reset_game()
            state = STATE_PLAY
        else:
            exit_game()
             
    if state == STATE_ANEW:
        reset_game()
        state = STATE_PLAY
        
