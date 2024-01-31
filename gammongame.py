from tkinter import *
from tkinter import ttk
from screeninfo import get_monitors
from collections import deque
from time import sleep
import threading
import math
import copy
import sys
import traceback

#will use a fixed size Canvas object to represent the dice
#will expose a public method for drawing the desired die
class Dice(Canvas):
    def __init__(self, parent):
        super().__init__(parent, background='white')
        self['height'] = 60
        self['width'] = 60
        self._die_value = None
        self.dot_size = 3
    #is passed the value of die to display   
    def drawDie(self, val):
        self.set(val)
        HEIGHT = int(self['height'])
        WIDTH = int(self['width'])
        DOT_SIZE = self.dot_size
        UPPER_LEFT_COORDS = HEIGHT/4-DOT_SIZE, WIDTH/4-DOT_SIZE, HEIGHT/4+DOT_SIZE, WIDTH/4+DOT_SIZE
        UPPER_RIGHT_COORDS = HEIGHT/4-DOT_SIZE, WIDTH*(3/4)-DOT_SIZE, HEIGHT/4+DOT_SIZE, WIDTH*(3/4)+DOT_SIZE 
        LOWER_LEFT_COORDS = HEIGHT*(3/4)-DOT_SIZE, WIDTH/4-DOT_SIZE, HEIGHT*(3/4)+DOT_SIZE, WIDTH/4+DOT_SIZE
        LOWER_RIGHT_COORDS = HEIGHT*(3/4)-DOT_SIZE, WIDTH*(3/4)-DOT_SIZE, HEIGHT*(3/4)+DOT_SIZE, WIDTH*(3/4)+DOT_SIZE
        CENTER_COORDS = HEIGHT/2-DOT_SIZE, WIDTH/2-DOT_SIZE, HEIGHT/2+DOT_SIZE, WIDTH/2+DOT_SIZE
        if val == 1:
            self.create_oval(*CENTER_COORDS, fill='black', tags=('dot'))
        elif val == 2:
            self.create_oval(*UPPER_LEFT_COORDS, fill='black', tags=('dot'))
            self.create_oval(*LOWER_RIGHT_COORDS, fill='black', tags=('dot'))
        elif val == 3:
            self.create_oval(*UPPER_LEFT_COORDS, fill='black', tags=('dot'))
            self.create_oval(*CENTER_COORDS, fill='black', tags=('dot'))
            self.create_oval(*LOWER_RIGHT_COORDS, fill='black', tags=('dot'))
        elif val == 4:
            self.create_oval(*UPPER_LEFT_COORDS, fill='black', tags=('dot'))
            self.create_oval(*UPPER_RIGHT_COORDS, fill='black', tags=('dot'))
            self.create_oval(*LOWER_LEFT_COORDS, fill='black', tags=('dot'))
            self.create_oval(*LOWER_RIGHT_COORDS, fill='black', tags=('dot'))
        elif val == 5:
            self.drawDie(4)
            self.set(5)
            self.create_oval(*CENTER_COORDS, fill='black', tags=('dot'))
        elif val == 6:
            self.drawDie(4)
            self.set(6)
            self.create_oval(WIDTH/4-DOT_SIZE, HEIGHT/2-DOT_SIZE, WIDTH/4+DOT_SIZE, HEIGHT/2+DOT_SIZE, fill='black', tags=('dot'))
            self.create_oval(WIDTH*(3/4)-DOT_SIZE, HEIGHT/2-DOT_SIZE, WIDTH*(3/4)+DOT_SIZE, HEIGHT/2+DOT_SIZE, fill='black', tags=('dot'))
            
    def clearDice(self):
        self.delete('dot')
        
    def set(self, num):
        self._die_value = num
        
        
    def get(self):
        return self._die_value
            


#custom Exceptions BackgammonBoard and game scripts will use
class GackError(Exception):
    pass

class PieceError(GackError):
    pass

#draw backgammon board using Canvas facilities
#all clicks and event handlings occur in event loop (Tkinter)  
#adjusts it's own size depending on user's screen resolution using third party module (screeninfo)
#will click on piece or spot and will highlight everywhere piece(s) from that spot can go with dice data
#userClickSpot--->highlightSpot--->movePiece--->highlightSpot--->movePiece is basic loop, is restarted when user clicks on a different spot/piece or no more moves to be made
class BackgammonBoard(Canvas):
    #instantiate BackgammonBoard with parent, colors of board, and client's Confirm move button, forced move button, and doubling method
    def __init__(self, parent, colors, b, b2, doubling_method, lock, animate=True):
        #create a Canvas object with super() call
        super().__init__(parent, background=colors[0])
        self.root = parent
        #save colors as instance variable for future configuration
        self._colors = list(colors)
        #save client confirm and forced move buttons as instance variables
        self.button = b
        self.button_2 = b2
        #save client's doubling method
        self.client_method = doubling_method
        #will notify client after every move is performed
        self.game_lock = lock
        #internal lock board will use to put all bar pieces on bar before original move is performed
        self.board_lock = threading.Condition()
        #create dictionary to hold spot number and pieces currently occupying it
        self._piece_locations = {i:[] for i in range(0,27)}
        #create the dice instance data, will have mutator method (setDice())
        #dice 3 and 4 in case user rolls doubles
        self._dice_1 = None
        self._dice_2 = None
        self._dice_3 = None
        self._dice_4 = None
        #set up list containing all moves a player will make during their turn
        self._last_move = []
        self.forced_moves = []
        #initialize pipcount variables as strings (for Tkinter)
        self.team_pipcount = '167'
        self.opp_pipcount = '167'
        #detirmine if a drawing thread is running and make other moves wait to ensure animation of one piece at a time
        self.active_thread = False
        self.draw_cond = threading.Condition()
        self._animate = animate
        self.is_forced_move = None
        #draw an empty backgammon board
        self._drawBoard()
        
    def _drawBoard(self):
        #extract height and width of user monitor
        #consider just using winfo built-in calculations for max height and max width
        for m in get_monitors():
            self.minfo = (m.height, m.width)
        MAX_HEIGHT = self.minfo[0]
        MAX_WIDTH = self.minfo[1]
        #adjust height of Canvas to 77% of user's screen height and 59% of screen width
        #adjust these local constants to change size of entire board, everything is calculated from HEIGHT and WIDTH
        self['height'] = round(MAX_HEIGHT*0.70)
        HEIGHT = int(self['height'])
        WIDTH = round(MAX_WIDTH*0.55)
        #constants representing coordinates the spots will be drawn
        #sizes of spots proportional to calculated size of Canvas
        X_TROUGH_DISTANCE = round(WIDTH*0.08)
        X_START = round(WIDTH*0.01) + X_TROUGH_DISTANCE
        X_INCREMENT = round(WIDTH*0.03)
        X_BAR_DISTANCE = round(WIDTH*0.08)
        #generate coordinates of spots based upon above sizes
        x_coords = []
        x_coords.append(X_START)
        for i in range(1,25):
            if i <= 13:
                if i != 13:
                    x_coords.append(X_START + (X_INCREMENT*i))
                else:
                    x_coords.append(x_coords[len(x_coords)-1] + X_BAR_DISTANCE)
                    
            if i >= 13:
                x_coords.append(X_START + (X_INCREMENT*i + X_BAR_DISTANCE))
                        
           
        #adjust width of Canvas to match size of spots
        self['width'] = x_coords[len(x_coords)-1] + X_START
        WIDTH = int(self['width'])
        
        #generate y coordinates for spots
        BOTTOM_BORDER = HEIGHT
        BOTTOM_HEIGHT = round(HEIGHT - (HEIGHT * 0.42))
        TOP_BORDER = 0
        TOP_HEIGHT = round(HEIGHT * 0.42)
        
        #save coordinates of spots as an instance variable for future drawing of pieces(tuples of bottom of each spot x-y coordinates as well as tip of spots)
        _spot_x_coords = [(x_coords[i-2], x_coords[i]) for i in range(25,13,-2)] + [(x_coords[i-2], x_coords[i]) for i in range(12,0,-2)]
        self._coords = [(x1, BOTTOM_BORDER, x2, BOTTOM_BORDER, (x2-x1)//2+x1, BOTTOM_HEIGHT) for x1, x2 in _spot_x_coords] + [(x1, TOP_BORDER, x2, TOP_BORDER, (x2-x1)//2+x1, TOP_HEIGHT) for x1, x2 in reversed(_spot_x_coords)]
        self._diameter = x_coords[2] - x_coords[0]
        self._trough_distance = X_TROUGH_DISTANCE
        
        colors = self._colors
        #id numbers of all spots reflect actual numbering on backgammon board (from bottom-right homeboard perspective)
        #bottom row spots
        id = self.create_polygon(x_coords[23],BOTTOM_BORDER,x_coords[24],BOTTOM_HEIGHT,x_coords[25],BOTTOM_BORDER, fill=colors[1], outline='black', tags=('spot', colors[1]))
        id = self.create_polygon(x_coords[21],BOTTOM_BORDER,x_coords[22],BOTTOM_HEIGHT,x_coords[23],BOTTOM_BORDER, fill=colors[2], outline='black', tags=('spot', colors[2]))
        id = self.create_polygon(x_coords[19],BOTTOM_BORDER,x_coords[20],BOTTOM_HEIGHT,x_coords[21],BOTTOM_BORDER, fill=colors[1], outline='black', tags=('spot', colors[1]))
        id = self.create_polygon(x_coords[17],BOTTOM_BORDER,x_coords[18],BOTTOM_HEIGHT,x_coords[19],BOTTOM_BORDER, fill=colors[2], outline='black', tags=('spot', colors[2]))
        id = self.create_polygon(x_coords[15],BOTTOM_BORDER,x_coords[16],BOTTOM_HEIGHT,x_coords[17],BOTTOM_BORDER, fill=colors[1], outline='black', tags=('spot', colors[1]))
        id = self.create_polygon(x_coords[13],BOTTOM_BORDER,x_coords[14],BOTTOM_HEIGHT,x_coords[15],BOTTOM_BORDER, fill=colors[2], outline='black', tags=('spot', colors[2]))
        id = self.create_polygon(x_coords[10],BOTTOM_BORDER,x_coords[11],BOTTOM_HEIGHT,x_coords[12],BOTTOM_BORDER, fill=colors[1], outline='black', tags=('spot', colors[1]))
        id = self.create_polygon(x_coords[8],BOTTOM_BORDER,x_coords[9],BOTTOM_HEIGHT,x_coords[10],BOTTOM_BORDER, fill=colors[2], outline='black', tags=('spot', colors[2]))
        id = self.create_polygon(x_coords[6],BOTTOM_BORDER,x_coords[7],BOTTOM_HEIGHT,x_coords[8],BOTTOM_BORDER, fill=colors[1], outline='black', tags=('spot', colors[1]))
        id = self.create_polygon(x_coords[4],BOTTOM_BORDER,x_coords[5],BOTTOM_HEIGHT,x_coords[6],BOTTOM_BORDER, fill=colors[2], outline='black', tags=('spot', colors[2]))
        id = self.create_polygon(x_coords[2],BOTTOM_BORDER,x_coords[3],BOTTOM_HEIGHT,x_coords[4],BOTTOM_BORDER, fill=colors[1], outline='black', tags=('spot', colors[1]))
        id = self.create_polygon(x_coords[0] ,BOTTOM_BORDER, x_coords[1] ,BOTTOM_HEIGHT,x_coords[2],BOTTOM_BORDER, fill=colors[2], outline='black', tags=('spot', colors[2]))
        
        #top row spots
        id = self.create_polygon(x_coords[0],TOP_BORDER,x_coords[1],TOP_HEIGHT,x_coords[2],TOP_BORDER, fill=colors[1],outline='black', tags=('spot', colors[1]))
        id = self.create_polygon(x_coords[2],TOP_BORDER,x_coords[3],TOP_HEIGHT,x_coords[4],TOP_BORDER, fill=colors[2], outline='black', tags=('spot',colors[2]))
        id = self.create_polygon(x_coords[4],TOP_BORDER,x_coords[5],TOP_HEIGHT,x_coords[6],TOP_BORDER, fill=colors[1], outline='black', tags=('spot', colors[1]))
        id = self.create_polygon(x_coords[6],TOP_BORDER,x_coords[7],TOP_HEIGHT,x_coords[8],TOP_BORDER, fill=colors[2], outline='black', tags=('spot', colors[2]))
        id = self.create_polygon(x_coords[8],TOP_BORDER,x_coords[9],TOP_HEIGHT,x_coords[10],TOP_BORDER, fill=colors[1], outline='black', tags=('spot', colors[1]))
        id = self.create_polygon(x_coords[10],TOP_BORDER,x_coords[11],TOP_HEIGHT,x_coords[12],TOP_BORDER, fill=colors[2], outline='black', tags=('spot', colors[2]))
        id = self.create_polygon(x_coords[13],TOP_BORDER,x_coords[14],TOP_HEIGHT,x_coords[15],TOP_BORDER, fill=colors[1], outline='black', tags=('spot', colors[1]))
        id = self.create_polygon(x_coords[15],TOP_BORDER,x_coords[16],TOP_HEIGHT,x_coords[17],TOP_BORDER, fill=colors[2], outline='black', tags=('spot', colors[2]))
        id = self.create_polygon(x_coords[17],TOP_BORDER,x_coords[18],TOP_HEIGHT,x_coords[19],TOP_BORDER, fill=colors[1], outline='black', tags=('spot', colors[1]))
        id = self.create_polygon(x_coords[19],TOP_BORDER,x_coords[20],TOP_HEIGHT,x_coords[21],TOP_BORDER, fill=colors[2], outline='black', tags=('spot', colors[2]))
        id = self.create_polygon(x_coords[21],TOP_BORDER,x_coords[22],TOP_HEIGHT,x_coords[23],TOP_BORDER, fill=colors[1], outline='black', tags=('spot', colors[1]))
        id = self.create_polygon(x_coords[23],TOP_BORDER,x_coords[24],TOP_HEIGHT,x_coords[25],TOP_BORDER, fill=colors[2], outline='black', tags=('spot', colors[2])) 
        
        #lines representing troughs on each side
        id = self.create_line(X_TROUGH_DISTANCE/2, TOP_BORDER, X_TROUGH_DISTANCE/2, BOTTOM_BORDER, fill=colors[5], width=X_TROUGH_DISTANCE, tags=('trough'))
        id = self.create_line((WIDTH-(X_TROUGH_DISTANCE/2)), TOP_BORDER, (WIDTH-(X_TROUGH_DISTANCE/2)), BOTTOM_BORDER, fill=colors[5], width=X_TROUGH_DISTANCE, tags=('trough'))
        #rectangles inside of the trough that the user will click (and will be yellow-outlined when moving pieces into the trough)
        id = self.create_rectangle(WIDTH-X_TROUGH_DISTANCE+5, HEIGHT-5, WIDTH-5, (HEIGHT/2)+5, fill=colors[5], outline='black', tags=('trough'))
        id = self.create_rectangle(5, HEIGHT-5, X_TROUGH_DISTANCE-5, (HEIGHT/2)+5, fill=colors[5], outline='black', tags=('trough'))
        
        #solid black line that represents the bar
        id = self.create_line(WIDTH//2,TOP_BORDER,WIDTH//2,BOTTOM_BORDER, fill=colors[6], width=X_BAR_DISTANCE-10, tags=('bar'))
        
        #create event binding for the spots and trough
        self.tag_bind('spot', '<1>', self._userClickSpot)
        self.tag_bind('trough', '<1>', self._userClickSpot)
        #right-clicking anywhere on Canvas will call our undo() method which undoes previous move
        self.bind('<3>', lambda e: self._undo())
    
        #add labels right above every spot to display amount of pieces over 5 occupying that spot
        self.labels = []
        for i in range(0,24):
            d = (self._coords[i][2]-self._coords[i][0])/3
            l = ttk.Label(self, background=colors[0])
            self.create_window(self._coords[i][4], self._coords[i][5]-d if i < 12 else self._coords[i][5]+d ,window=l, tags=('window'))
            self.labels.append(l)
            
                
            
    #unhighlight any actively highlighted (validspot tagged) spot or piece
    #anytime a user clicks on a spot or moves a piece, this method will be called to unhighlight 
    #is called by userClickSpot and movePiece at start of both methods  
    def _clearSpots(self):
        #take away yellow outline, give regular black outline back
        #give those previously yellow-outlined spots their spot status back
        #give previously yellow-outlined piece it's piece status back 
        if self.actual_idx_1 is not None:
            idx = self._spotid.index(self.actual_idx_1) 
            self.dtag('all', 'validspot1')
            self.addtag('spot', 'withtag', self.actual_idx_1)
            self.itemconfigure(self.actual_idx_1, outline='black')
            pieces = len(self._piece_locations[idx]) if idx <= 25 else 0 
            if pieces > 1 and pieces < 6:
                self.itemconfigure(self._piece_locations[idx][pieces-1][0], outline='black')
                self.addtag('piece'+str(idx), 'withtag', self._piece_locations[idx][pieces-1][0])
            elif pieces > 5:
                self.itemconfigure(self._piece_locations[idx][4][0], outline='black')
                self.addtag('piece'+str(idx), 'withtag', self._piece_locations[idx][4][0])
                
        
        if self.actual_idx_2 is not None:
            idx = self._spotid.index(self.actual_idx_2) 
            self.dtag('all', 'validspot2')
            self.addtag('spot', 'withtag', self.actual_idx_2)
            self.itemconfigure(self.actual_idx_2, outline='black')
            pieces = len(self._piece_locations[idx]) if idx <= 25 else 0 
            if pieces > 1 and pieces < 6:
                self.itemconfigure(self._piece_locations[idx][pieces-1][0], outline='black')
                self.addtag('piece'+str(idx), 'withtag', self._piece_locations[idx][pieces-1][0])
            elif pieces > 5:
                self.itemconfigure(self._piece_locations[idx][4][0], outline='black')
                self.addtag('piece'+str(idx), 'withtag', self._piece_locations[idx][4][0])
                
                        
        if self.actual_idx_3 is not None:
            idx = self._spotid.index(self.actual_idx_3) 
            self.dtag('all', 'validspot3')
            self.addtag('spot', 'withtag', self.actual_idx_3)
            self.itemconfigure(self.actual_idx_3, outline='black')
            pieces = len(self._piece_locations[idx]) if idx <= 25 else 0 
            if pieces > 1 and pieces < 6:
                self.itemconfigure(self._piece_locations[idx][pieces-1][0], outline='black')
                self.addtag('piece'+str(idx), 'withtag', self._piece_locations[idx][pieces-1][0])
            elif pieces > 5:
                self.itemconfigure(self._piece_locations[idx][4][0], outline='black')
                self.addtag('piece'+str(idx), 'withtag', self._piece_locations[idx][4][0])
                
                
        if self.actual_idx_4 is not None:
            idx = self._spotid.index(self.actual_idx_4) 
            self.dtag('all', 'validspot4')
            self.addtag('spot', 'withtag', self.actual_idx_4)
            self.itemconfigure(self.actual_idx_4, outline='black')
            pieces = len(self._piece_locations[idx]) if idx <= 25 else 0 
            if pieces > 1 and pieces < 6:
                self.itemconfigure(self._piece_locations[idx][pieces-1][0], outline='black')
                self.addtag('piece'+str(idx), 'withtag', self._piece_locations[idx][pieces-1][0])
            elif pieces > 5:
                self.itemconfigure(self._piece_locations[idx][4][0], outline='black')
                self.addtag('piece'+str(idx), 'withtag', self._piece_locations[idx][4][0])
                
        if self.actual_idx_5 is not None:
            idx = self._spotid.index(self.actual_idx_5) 
            self.dtag('all', 'validspot5')
            self.addtag('spot', 'withtag', self.actual_idx_5)
            self.itemconfigure(self.actual_idx_5, outline='black')
            pieces = len(self._piece_locations[idx]) if idx <= 25 else 0 
            if pieces > 1 and pieces < 6:
                self.itemconfigure(self._piece_locations[idx][pieces-1][0], outline='black')
                self.addtag('piece'+str(idx), 'withtag', self._piece_locations[idx][pieces-1][0])
            elif pieces > 5:
                self.itemconfigure(self._piece_locations[idx][4][0], outline='black')
                self.addtag('piece'+str(idx), 'withtag', self._piece_locations[idx][4][0])
           
    
    #event handling method for user clicking on a spot or a piece
    #detirmine what piece was clicked (i.e from which spot) and handle the event (calling highlightSpot() with correct arg)
    #if team piece on bar or all pieces in homeboard, this method will detect those conditions and handle accordingly
    #unhighlight all current active spots/pieces (clearSpots()) and highlight new spots/pieces by calling highlightSpot()
    def _userClickSpot(self, event):
        self._clearSpots()
        
        spot_idx = None
        #detirmine which spot user has clicked using _coords instance variable
        #only traverses half of _coords max, deduces exact spot from y event value 
        for idx, coords in enumerate(self._coords, 1):
            #if user clicks on a spot or a piece on a spot
            if (event.x >= coords[0] and event.x <= coords[2]):
                if event.y >= float(self['height'])/2:
                    spot_idx = idx if self._homeboard == 'br' else 25 - idx
                    break
                else:
                    spot_idx = 25 - idx if self._homeboard == 'br' else idx
                    break
                    
        #if user clicked on a piece on the bar or clicked on their trough
        color = None
        if spot_idx is None and event.x >= float(self['width'])/2-(self._diameter/2) and event.x <= float(self['width'])/2+(self._diameter/2):
            #detirmine color of piece clicked on the bar (team pieces always higher than opponenet pieces on the bar)
            color = self._team if event.y < float(self['height'])/2 else self._opponent
            print('color on bar:', color)
            spot_idx = 26
        elif spot_idx is None:
            if event.x >= float(self['width'])-self._trough_distance and event.y > float(self['height'])/2 and self._homeboard == 'br':
                spot_idx = 0
            elif event.x <= self._trough_distance and event.y > float(self['height'])/2 and self._homeboard == 'bl':
                spot_idx = 25
            else:
                return
                        
        print(spot_idx)
        
        #iterate through bar pieces and count our team pieces currently on the bar
        bar_count = 0    
        for p, c in self._piece_locations[26]:
            if c == self._team:
                bar_count += 1
        
        #check if any team pieces on the bar and set the flag accordingly
        _is_bar = True if bar_count > 0 else False
        #if user clicks an empty spot or a spot occupied by opponent pieces or there are team pieces on bar AND user did not click on a bar pieces, do nothing
        if len(self._piece_locations[spot_idx]) == 0 or (self._piece_locations[spot_idx][0][1] == self._opponent and spot_idx != 26) or (_is_bar is True and spot_idx != 26) or color == self._opponent:
            print('here, my theory is correct')
            return
        
        #do nothing if user clicks on a trough to start a move
        if spot_idx == 0 or spot_idx == 25:
            print('clicked on trough')
            return
        
        #give highlight calls same amount of lag as the call in movePiece    
        self._highlightSpot(spot_idx, bar_count)
            
                             
    #highlight spots your pieces can move based upon which dice are active and which spot/piece the user clicked
    #tags spots with our movePiece() method
    #is passed index that piece moves from and optional arg for amount of team pieces on the bar
    #bar_pieces arg will implment correct placement of pieces from bar back to the board 
    #is_counting optional arg will indicate whether _highlightSpot is just being used to count number of available moves       
    def _highlightSpot(self, idx, bar_pieces=None, is_counting=False):
                    
        self._clearSpots()
        #if no pieces remain on spot, do nothing or game is over
        if len(self._piece_locations[idx]) == 0 or (bar_pieces == 0 and idx == 26) or self.isGameOver():
            return None, None, None, None, None
        #check if all team pieces are in homeboard
        #iterate through _piece_locations depending on orientation of homeboard (bl or br) and count all team pieces outside of user's homeboard
        #start the count at how many pieces user already has in their trough! very important for correct count of pieces in homeboard
        self._homeboard_count = len(self._piece_locations[0]) if self._homeboard == 'br' else len(self._piece_locations[25])
        for i in range(1,7) if self._homeboard == 'br' else range(19,25):
            pieces = len(self._piece_locations[i])
            if pieces > 0:
                if self._piece_locations[i][0][1] == self._team:
                    self._homeboard_count += pieces
        
        #reused condition if all user's pieces are home or just one piece is out and that's the piece they clicked
        home_condition = self._homeboard_count == 15 or (self._homeboard_count == 14 and ((idx > 6) if self._homeboard == 'br' else idx < 19))
        #highlights all places user can move after they click on a piece
        #assumes all pieces/spots are unhighlighted
        light_idx_1, light_idx_2, light_idx_3, light_idx_4, light_idx_5 = None, None, None, None, None
        #if trough can potentially be highlighed or not
        home_check = True if home_condition else None
        #assign light indicies with current dice data
        #light_idx will be True if it can potentially be beared off (will check that next)
        #uses bar_count variable to detirmine highlighting if pieces are coming from bar
        if self._dice_1 is not None:
            if idx < 25:
                light_idx_1 = (idx - self._dice_1 if idx-self._dice_1 >= 1 else home_check) if self._homeboard == 'br' else (idx + self._dice_1 if idx+self._dice_1 <= 24 else home_check)
            elif idx == 26:
                light_idx_1 = self._dice_1 if self._homeboard == 'bl' else (25 - self._dice_1)
                
            
        if self._dice_2 is not None:
            if idx < 25:
                light_idx_2 = (idx - self._dice_2 if idx-self._dice_2 >= 1 else home_check) if self._homeboard == 'br' else (idx + self._dice_2 if idx+self._dice_2 <= 24 else home_check)
            elif idx == 26:
                light_idx_2 = self._dice_2 if self._homeboard == 'bl' else (25 - self._dice_2)
                   
        
        #two dice combined
        if self._dice_1 is not None and self._dice_2 is not None:
            if idx < 25:
                light_idx_3 = (idx - self._dice_1 - self._dice_2 if idx-self._dice_1-self._dice_2 >= 1 else home_check) if self._homeboard == 'br' else \
                (idx + self._dice_1 + self._dice_2 if idx+self._dice_1+self._dice_2 <= 24 else home_check)
            elif idx == 26:
                light_idx_3 = (self._dice_1 + self._dice_2 if self._homeboard == 'bl' else (25 - self._dice_1 - self._dice_2)) if bar_pieces == 1 else None
                
            
        #next two suites are in case user rolls doubles
        if self._dice_3 is not None:
            if idx < 25:
                light_idx_4 = (idx - self._dice_1 - self._dice_2 - self._dice_3 if idx-self._dice_1-self._dice_2-self._dice_3 >= 1 else home_check) if self._homeboard == 'br' else \
                (idx + self._dice_1 + self._dice_2 + self._dice_3 if idx+self._dice_1+self._dice_2+self._dice_3 <= 24 else home_check)
            elif idx == 26:
                light_idx_4 = (self._dice_1 + self._dice_2 + self._dice_3 if self._homeboard == 'bl' else (25 - self._dice_1 - self._dice_2 - self._dice_3)) if bar_pieces == 1 else None
                
            
        if self._dice_4 is not None:
            if idx < 25:
                light_idx_5 = (idx - self._dice_1 - self._dice_2 - self._dice_3 - self._dice_4 if idx-self._dice_1-self._dice_2-self._dice_3-self._dice_4 >= 1 else home_check) if self._homeboard == 'br' else \
                (idx + self._dice_1 + self._dice_2 + self._dice_3 + self._dice_4 if idx+self._dice_1+self._dice_2+self._dice_3+self._dice_4 <= 24 else home_check)
            elif idx == 26:
               light_idx_5 = (self._dice_1 + self._dice_2 + self._dice_3 + self._dice_4 if self._homeboard == 'bl' else (25 - self._dice_1 - self._dice_2 - self._dice_3 - self._dice_4)) if bar_pieces == 1 else None
                
            
            
        #if trough can be potentially highlighted
        #if user can simply bear off or that no piece is a higher index than the die that was rolled (light_idx will be True for the check)
        if home_condition:
            if light_idx_1 is True:
                if idx == self._dice_1 or 25 - idx == self._dice_1:
                    light_idx_1 = 0 if self._homeboard == 'br' else 25
                else:
                    for i in range(6, idx, -1) if self._homeboard == 'br' else range(19, idx):
                        if len(self._piece_locations[i]) > 0 and self._piece_locations[i][0][1] == self._team:
                            light_idx_1 = None
                            break
                        
                    if light_idx_1 is True:
                        light_idx_1 = 0 if self._homeboard == 'br' else 25
                
            if light_idx_2 is True:
                if idx == self._dice_2 or 25 - idx == self._dice_2:
                    light_idx_2 = 0 if self._homeboard == 'br' else 25
                else:
                    for i in range(6, idx, -1) if self._homeboard == 'br' else range(19, idx):
                        if len(self._piece_locations[i]) > 0 and self._piece_locations[i][0][1] == self._team:
                            light_idx_2 = None
                            break
                    
                if light_idx_2 is True:
                    light_idx_2 = 0 if self._homeboard == 'br' else 25
            
            
            elif light_idx_3 is True:
                if idx == self._dice_1 + self._dice_2 or 25 - idx == self._dice_1 + self._dice_2:
                    light_idx_3 = 0 if self._homeboard == 'br' else 25
                else:
                    idx_check = light_idx_2 if light_idx_2 is not None else light_idx_1
                    for i in range(6, idx_check, -1) if self._homeboard == 'br' else range(19, idx_check):
                        size = len(self._piece_locations[i])
                        if size > 0 and self._piece_locations[i][0][1] == self._team:
                            #check that the idx does not have more than one piece!!!
                            light_idx_3 = True if i == idx and size == 1 else None
                            if light_idx_3 is None:
                                break
                    
                    if light_idx_3 is True:
                        light_idx_3 = 0 if self._homeboard == 'br' else 25
            
            
            elif light_idx_4 is True:
                if idx == self._dice_1 + self._dice_2 + self._dice_3 or 25 - idx == self._dice_1 + self._dice_2 + self._dice_3:
                    light_idx_4 = 0 if self._homeboard == 'br' else 25
                else:
                    for i in range(6, light_idx_3, -1) if self._homeboard == 'br' else range(19, light_idx_3):
                        size = len(self._piece_locations[i])
                        if size > 0 and self._piece_locations[i][0][1] == self._team:
                            light_idx_4 = True if i == idx and size == 1 else None
                            if light_idx_4 is None:
                                break
                        
                    if light_idx_4 is True:
                        light_idx_4 = 0 if self._homeboard == 'br' else 25           

            
            elif light_idx_5 is True:
                if idx == self._dice_1 + self._dice_2 + self._dice_3 + self._dice_4 or 25 - idx == self._dice_1 + self._dice_2 + self._dice_3 + self._dice_4:
                    light_idx_5 = 0 if self._homeboard == 'br' else 25
                else:
                    for i in range(6, light_idx_4 , -1) if self._homeboard == 'br' else range(19, light_idx_4):
                        size = len(self._piece_locations[i])
                        if size > 0 and self._piece_locations[i][0][1] == self._team:
                            light_idx_5 = True if i == idx and size == 1 else None
                            if light_idx_5 is None:
                                break
                        
                    if light_idx_5 is True:
                        light_idx_5 = 0 if self._homeboard == 'br' else 25
                     
                    
                    
                        
        #count amount of pieces on a spot if it can potentially be highlighted
        #other code working with these variables need to make sure of color using self._piece_location variable
        opp_pieces_1 = len(self._piece_locations[light_idx_1]) if light_idx_1 is not None else 0
        opp_pieces_2 = len(self._piece_locations[light_idx_2]) if light_idx_2 is not None else 0
        opp_pieces_3 = len(self._piece_locations[light_idx_3]) if light_idx_3 is not None else 0
        opp_pieces_4 = len(self._piece_locations[light_idx_4]) if light_idx_4 is not None else 0
        opp_pieces_5 = len(self._piece_locations[light_idx_5]) if light_idx_5 is not None else 0
        #if dice roll will take us to a spot occupied by more than one opponent piece, that die cannot be used on that piece
        if opp_pieces_1 > 1:
            if self._piece_locations[light_idx_1][0][1] != self._team:
                light_idx_1 = None
                
        if opp_pieces_2 > 1:
            if self._piece_locations[light_idx_2][0][1] != self._team:
                light_idx_2 = None
              
        if opp_pieces_3 > 1:
            if self._piece_locations[light_idx_3][0][1] != self._team:
                light_idx_3 = None
                
        if opp_pieces_4 > 1:
            if self._piece_locations[light_idx_4][0][1] != self._team:
                light_idx_4 = None
                
        if opp_pieces_5 > 1:
            if self._piece_locations[light_idx_5][0][1] != self._team:
                light_idx_5 = None 
        
                   
        #translate piece location numbers to actual id numbers of the spots (for highlighting of spots) 
        #only set actual_idx_1 and actual_idx_2 at same time if not a double to avoid erronous double event handling     
        self.actual_idx_1 = self._spotid[light_idx_1] if (light_idx_1 is not None and light_idx_1 is not True) else None
        self.actual_idx_2 = self._spotid[light_idx_2] if (light_idx_2 is not None and light_idx_2 is not True) and light_idx_1 != light_idx_2 else None
        self.actual_idx_3 = self._spotid[light_idx_3] if (light_idx_3 is not None and light_idx_3 is not True) and (light_idx_1 is not None or light_idx_2 is not None) else None
        self.actual_idx_4 = self._spotid[light_idx_4] if (light_idx_4 is not None and light_idx_4 is not True) and self.actual_idx_3 is not None else None
        self.actual_idx_5 = self._spotid[light_idx_5] if (light_idx_5 is not None and light_idx_5 is not True) and self.actual_idx_4 is not None else None
        
        #for counting number of available moves for the player, will return before any pieces/spots are highlighted
        #return light indices, will tell us how many moves/dice are available for a piece
        if is_counting is True:
            return self.actual_idx_1, self.actual_idx_2, self.actual_idx_3, self.actual_idx_4, self.actual_idx_5
        
        #check for duplicate results for actual_idx_3 to actual_idx_5 to avoid double tagging trough
        self.actual_idx_3 = self.actual_idx_3 if self.actual_idx_3 != self.actual_idx_1 and self.actual_idx_3 != self.actual_idx_2 else None
        self.actual_idx_4 = self.actual_idx_4 if self.actual_idx_4 != self.actual_idx_3 else None
        self.actual_idx_5 = self.actual_idx_5 if self.actual_idx_5 != self.actual_idx_4 else None
        
        #flag any opponent pieces if user clicks on higher light_idx with an intermediate move that must send a piece to the bar
        #will tell movePiece() which pieces to send to bar with _goToBar list
        #if user does not have to take an enemy piece with a multiple dice roll, using multiple dice click will avoid moving opp. piece to bar
        #if user cannot move without getting a piece and user uses multiple dice roll, will automatically move furthest opp. piece to bar
        _goToBar = [-1,-1,-1,-1,-1]     
        if self.actual_idx_1 is not None or self.actual_idx_2 is not None:
            if self.actual_idx_1 is None and (opp_pieces_2 == 1 and self._piece_locations[light_idx_2][0][1] == self._opponent):
                _goToBar[1] = light_idx_2
            elif self.actual_idx_2 is None and (opp_pieces_1 == 1 and self._piece_locations[light_idx_1][0][1] == self._opponent):
                _goToBar[0] = light_idx_1
            elif (opp_pieces_1 == 1 and self._piece_locations[light_idx_1][0][1] == self._opponent) and\
             (opp_pieces_2 == 1 and self._piece_locations[light_idx_2][0][1] == self._opponent):
                 _goToBar[1] = light_idx_1
                   
        
        if opp_pieces_3 == 1 and self._piece_locations[light_idx_3][0][1] == self._opponent:
             _goToBar[2] = light_idx_3
            
        if opp_pieces_4 == 1 and self._piece_locations[light_idx_4][0][1] == self._opponent:
             _goToBar[3] = light_idx_4
                
        if opp_pieces_5 == 1 and self._piece_locations[light_idx_5][0][1] == self._opponent:
             _goToBar[4] = light_idx_5
                
            
            
        #outline the valid spots to move with yellow  
        #tag the valid spot (tagging it with movePiece method)
        #strip spot of it's spot status until user moves piece, clicks on another spot, or clicks on another piece to move 
        #strip top piece on the valid spot of it's piece status, tag with valid spot so movePiece will be called 
        bar_cond = True if _goToBar.count(-1) < 5 else False
        ol = 'light yellow'
        if self.actual_idx_1 is not None:
            self.addtag('validspot1', 'withtag', self.actual_idx_1)
            self.tag_bind('validspot1', '<1>', lambda e: self.movePiece(idx, light_idx_1, dice=1, col=None if idx != 26 else self._team))
            self.dtag(self.actual_idx_1, 'spot')
            self.itemconfigure(self.actual_idx_1, outline=ol)
            #avoid highlighting pieces with movePiece action if trough is being highlighted
            if light_idx_1 != 25 and light_idx_1 != 0:
                pieces = len(self._piece_locations[light_idx_1]) if light_idx_1 <= 25 else 0
                if pieces > 1 and pieces < 6:
                    self.addtag('validspot1', 'withtag', self._piece_locations[light_idx_1][pieces-1][0])
                    self.dtag(self._piece_locations[light_idx_1][pieces-1][0], 'piece'+str(light_idx_1))
                    self.itemconfigure(self._piece_locations[light_idx_1][pieces-1][0], outline=ol)
                elif pieces >= 6:
                    self.addtag('validspot1', 'withtag', self._piece_locations[light_idx_1][4][0])
                    self.dtag(self._piece_locations[light_idx_1][4][0], 'piece'+str(light_idx_1))
                    self.itemconfigure(self._piece_locations[light_idx_1][4][0], outline=ol)
                
        if self.actual_idx_2 is not None:
            self.addtag('validspot2', 'withtag', self.actual_idx_2)
            self.tag_bind('validspot2', '<1>', lambda e: self.movePiece(idx, light_idx_2, dice=2, col=None if idx != 26 else self._team))
            self.dtag(self.actual_idx_2, 'spot')
            self.itemconfigure(self.actual_idx_2, outline=ol)
            if light_idx_2 != 25 and light_idx_2 != 0:
                pieces = len(self._piece_locations[light_idx_2]) if light_idx_2 <= 25 else 0
                if pieces > 1 and pieces < 6:
                    self.addtag('validspot2', 'withtag', self._piece_locations[light_idx_2][pieces-1][0])
                    self.dtag(self._piece_locations[light_idx_2][pieces-1][0], 'piece'+str(light_idx_2))
                    self.itemconfigure(self._piece_locations[light_idx_2][pieces-1][0], outline=ol)
                elif pieces >= 6:
                    self.addtag('validspot2', 'withtag', self._piece_locations[light_idx_2][4][0])
                    self.dtag(self._piece_locations[light_idx_2][4][0], 'piece'+str(light_idx_2))
                    self.itemconfigure(self._piece_locations[light_idx_2][4][0], outline=ol)
                
        if self.actual_idx_3 is not None:
            self.addtag('validspot3', 'withtag', self.actual_idx_3)
            self.tag_bind('validspot3', '<1>', lambda e: self.movePiece(idx, light_idx_3, dice=3, col=None if idx != 26 else self._team,\
                                                                         barPieces=_goToBar[0:3] if bar_cond else None))
            self.dtag(self.actual_idx_3, 'spot')
            self.itemconfigure(self.actual_idx_3, outline=ol)
            if light_idx_3 != 25 and light_idx_3 != 0:
                pieces = len(self._piece_locations[light_idx_3]) if light_idx_3 <= 25 else 0
                if pieces > 1 and pieces < 6:
                    self.addtag('validspot3', 'withtag', self._piece_locations[light_idx_3][pieces-1][0])
                    self.dtag(self._piece_locations[light_idx_3][pieces-1][0], 'piece'+str(light_idx_3))
                    self.itemconfigure(self._piece_locations[light_idx_3][pieces-1][0], outline=ol)
                elif pieces >= 6:
                    self.addtag('validspot3', 'withtag', self._piece_locations[light_idx_3][4][0])
                    self.dtag(self._piece_locations[light_idx_3][4][0], 'piece'+str(light_idx_3))
                    self.itemconfigure(self._piece_locations[light_idx_3][4][0], outline=ol)
                
        if self.actual_idx_4 is not None:
            self.addtag('validspot4', 'withtag', self.actual_idx_4)
            self.tag_bind('validspot4', '<1>', lambda e: self.movePiece(idx, light_idx_4, dice=4, col=None if idx != 26 else self._team, \
                                                                        barPieces=_goToBar[0:4] if bar_cond else None))
            self.dtag(self.actual_idx_4, 'spot')
            self.itemconfigure(self.actual_idx_4, outline=ol)
            if light_idx_4 != 25 and light_idx_4 != 0:
                pieces = len(self._piece_locations[light_idx_4]) if light_idx_4 <= 25 else 0
                if pieces > 1 and pieces < 6:
                    self.addtag('validspot4', 'withtag', self._piece_locations[light_idx_4][pieces-1][0])
                    self.dtag(self._piece_locations[light_idx_4][pieces-1][0], 'piece'+str(light_idx_4))
                    self.itemconfigure(self._piece_locations[light_idx_4][pieces-1][0], outline=ol)
                elif pieces >= 6:
                    self.addtag('validspot4', 'withtag', self._piece_locations[light_idx_4][4][0])
                    self.dtag(self._piece_locations[light_idx_4][4][0], 'piece'+str(light_idx_4))
                    self.itemconfigure(self._piece_locations[light_idx_4][4][0], outline=ol)
                
        if self.actual_idx_5 is not None:
            self.addtag('validspot5', 'withtag', self.actual_idx_5)
            self.tag_bind('validspot5', '<1>', lambda e: self.movePiece(idx, light_idx_5, dice=5, col=None if idx != 26 else self._team, \
                                                                        barPieces=_goToBar[0:5] if bar_cond else None))
            self.dtag(self.actual_idx_5, 'spot')
            self.itemconfigure(self.actual_idx_5, outline=ol)
            if light_idx_5 != 25 and light_idx_5 != 0:
                pieces = len(self._piece_locations[light_idx_5]) if light_idx_5 <= 25 else 0
                if pieces > 1 and pieces < 6:
                    self.addtag('validspot5', 'withtag', self._piece_locations[light_idx_5][pieces-1][0])
                    self.dtag(self._piece_locations[light_idx_5][pieces-1][0], 'piece'+str(light_idx_5))
                    self.itemconfigure(self._piece_locations[light_idx_5][pieces-1][0], outline=ol)
                elif pieces >= 6:
                    self.addtag('validspot5', 'withtag', self._piece_locations[light_idx_5][4][0])
                    self.dtag(self._piece_locations[light_idx_5][4][0], 'piece'+str(light_idx_5))
                    self.itemconfigure(self._piece_locations[light_idx_5][4][0], outline=ol)
                            
                    
               
    #change color of board elements, represented by _colors instance variable
    def changeColor(self, idx, newcolor):
        if idx == 0:
            for label in self.labels:
                label['background'] = newcolor
                
            self.configure(background=newcolor)
        elif idx == 5:
            self.itemconfigure('trough', fill=newcolor)
        elif idx == 6:
            self.itemconfigure('bar', fill=newcolor)
        #everything tagged with their color will be adjusted here
        #must be elements that have a unique color
        else:
            old_color = self._colors[idx]
            self.itemconfigure(f'{old_color}', fill=newcolor)
            #update _piece_locations instance variable with new color of pieces 
            #potential update: no need to traverse _piece_locations if idx is not one of the pieces
            for key, value in self._piece_locations.items():
                for num, pc in enumerate(value):
                    if pc[1] == old_color:
                        self._piece_locations[key].remove(pc)
                        self._piece_locations[key].insert(num, (pc[0], newcolor))
            
            #adjust team and opponent color instance variables to newly selected color           
            if (idx == 3 and self._homeboard == 'br') or (idx == 4 and self._homeboard == 'bl'):
                self._team = newcolor
            
            if (idx == 3 and self._homeboard == 'bl') or (idx == 4 and self._homeboard == 'br'):
                self._opponent = newcolor            
                       
        self._colors[idx] = newcolor
        
    #generator that yields tuples representing all moves that can be made with current dice data
    def countMoves(self, bar_count=0):
        #yield moves from pieces on bar one at a time until no more team pieces on bar detected
        if bar_count != 0:
            yield 26, self._highlightSpot(26, is_counting=True)
        else:
            for key, value in self._piece_locations.items():
                if len(value) > 0 and value[0][1] == self._team:
                    yield key, self._highlightSpot(key,is_counting=True)
                    
    #count number of dice currently active           
    def countDice(self):
        count = 0
        for d in (self._dice_1, self._dice_2, self._dice_3, self._dice_4):
            if d is not None:
                count += 1 
                
        return count
             
    #mutator method for setting current dice roll data into BackgammonBoard
    #always assigns the higher die to self._dice_1 variable
    #will detect if roll results in a forced move
    #forced move detection will also implement rule of having to use larger die if only one die can be used
    def setDice(self, d1, d2, test=False):
        is_doubles = False
        if d1 != d2:
            self._dice_1, self._dice_2 = (d2,d1) if d1 < d2 else (d1,d2)
            self._dice_3 = None
            self._dice_4 = None
        else:
            self._dice_1, self._dice_2, self._dice_3, self._dice_4 = d1, d1, d1, d1
            is_doubles = True
        
        print('dice values has been set to:', self._dice_1, self._dice_2, self._dice_3, self._dice_4)   
        #turn off animation for the duration of the method if it was on in the first place
        turn_back_on = False
        if self._animate is True:
            self._animate = False
            turn_back_on = True

        #look at all possible moves with this roll
        loop_counter = 0
        move_count = 0
        loop_count = 0
        _is_forced_move = None
        _already_tried = False
        current_fork = None
        popped_fork = None
        idx_adjust_l = 1
        fork_list = deque()
        mult_fork_lists = deque()
        prev_fork = None
        search_fork = None
        search_loop = None
        _is_alternatives = False
        two_indices_cond = False
        set_to_null = None
        move_list = []
        while(True):
            #testing code (for breaking erronous infinite loop)
            if loop_counter == 200:
                print('too much loop break')
                break
            
            bar_p = 0
            for p, c in self._piece_locations[26]:
                if c == self._team:
                    bar_p += 1
                  
            #step through our generator and store all moves that can be made with current dice data
            active_dice = self.countDice()
            for f, ml in self.countMoves(bar_p):
                for d, m in enumerate(ml, 1):
                    if m is not None:
                        #turn our actual_idx into light_idx value
                        real_m = self._spotid.index(m)
                        #store possible move as args for movePiece() method
                        move_list.append((f,real_m,1,d))
                        size = len(self._piece_locations[f]) if f != 26 else bar_p
                        #try to find out how many 'extra' pieces can be moved because of doubles
                        extra_pieces = active_dice if active_dice <= size else size
                        #more than one piece cannot go more than two light indices away from it's origin
                        #will only apply to a double roll
                        if d > 3:
                            extra_pieces = 1
                        elif d == 3:
                            if extra_pieces > 2:
                                extra_pieces = 2
                        move_count += (1 if is_doubles is False else extra_pieces)
                        
            if move_count > 0:
                loop_count += 1
                #if just a test, tell caller we can move
                if test is True:
                    if turn_back_on is True:
                        self._animate = True
                    return True
                
            loop_counter += 1  
            print('move_count, move_list:', move_count, move_list)
            print('loop_count', loop_count)
            #if these conditions are met, is possibly a forced move
            #will move every possible combination of choices to see if it really is a forced move
            
            #move will be considered forced until proven otherwise
            _is_forced_move = True
            moves = len(move_list)
            #analyze time zero conditions if more moves than dice, see if we know move isn't forced, analyze further if could still be a forced move
            if active_dice < move_count and loop_count == 1:
                #check that all dice are used in the move_list (for non-double rolls)
                all_dice = None
                if is_doubles is False:
                    d1, d2 = False, False
                    for m in move_list:
                        if m[3] == 1:
                            d1 = True
                        elif m[3] == 2:
                            d2 = True
                            
                    if d1 is True and d2 is True:
                        all_dice = True
                    else:
                        all_dice = False
                
                #many indices use one die, analyze further to make sure we can't find way to use other die, and flag potential unusable die       
                if all_dice is False:
                    print('non-forced move because lots indices can move one die')
                    two_indices_cond = True
                    set_to_null = 1 if move_list[0][3] == 2 else 2       
                #if only one piece can be moved with all moves of a non-double roll, is only forced if there are no potential opponent pieces
                #to put on the bar
                elif move_count == 3 and is_doubles is False and move_list[0][0] == move_list[1][0] and \
                move_list[1][0] == move_list[2][0]:
                    if (len(self._piece_locations[move_list[0][1]]) == 1 and self._piece_locations[move_list[0][1]][0][1] == self._opponent)\
                     or (len(self._piece_locations[move_list[1][1]]) == 1 and self._piece_locations[move_list[1][1]][0][1] == self._opponent):
                        print('our choice detection suite!')
                        _is_forced_move = False
                        break
                #three moves with no double could still be forced, only from first loop_count
                elif move_count == 3 and is_doubles is False:
                    print('must analyze for potential forced moves')
                    pass  
                #make sure all dice can be used if move_count is greater than 3, or doubles is True
                elif is_doubles is True or all_dice is True:   
                    _is_forced_move = False
                    break 
                else:
                    print('none of the criteria was met, must analyze for potential forced moves')
            #if we get past time zero and still have more moves than dice, and also doubles is active or multiple piece-one die is not active     
            elif active_dice < move_count:
                if is_doubles is True or two_indices_cond is False:
                    _is_forced_move = False
                    break 
            
            #two indices can only move one die, set our flag so if second move not found, we will set unusable die to null   
            elif loop_count == 1 and is_doubles is False and moves == 2 and move_list[0][3] == move_list[1][3]:
                print('non-forced move because two indices can move one die')
                two_indices_cond = True
                set_to_null = 1 if move_list[0][3] == 2 else 2
                    
            #no more moves detected, look for previous 'forks', and restore data back to that point        
            if moves == 0:
                print('no move_list break')
                #these suites will detect alternate forced moves (non-double rolls) 
                if is_doubles is False and self.countDice() == 0 and len(self._last_move) > 1:   
                    if _is_alternatives is False:
                        _is_alternatives = None
                    elif _is_alternatives is None:
                        #if two same moves are performed in reverse order, or one piece goes two different ways to one index
                        if (self._last_move[0][:2], self._last_move[1][:2]) == (self.forced_moves[1][:2], self.forced_moves[0][:2]) or \
                        (self.forced_moves[0][0] == self.forced_moves[1][1] and self._last_move[0][0] == self._last_move[1][1]):
                            print('not actually alternative forced move')
                        else:
                            print('alternative forced moves have been detected')
                            _is_alternatives = True
                        
                
                #if all dice are used, store this sequence of moves, which will implement all dice must be used       
                if self.countDice() == 0:
                    self.forced_moves = self._last_move
                    self.forced_moves = copy.deepcopy(self.forced_moves)
                     
                print('len(fork_list):', len(fork_list))
                if len(fork_list) > 0:
                    idx_adjust_l += 1
                    move_count = 0
                    #restore data back to first detected fork
                    fork_data = fork_list[0]
                    current_fork = fork_data[2]
                    copy_fork_size = fork_data[1]
                    lc = loop_count
                    if _already_tried is False: 
                        print('fork_list before pop:')
                        for data in fork_list:
                            print(data, end=' ')
                        print('\n')
                        popped_fork = fork_list[0][0]  
                        for i in range(lc, fork_list.popleft()[0]-1, -1):
                             self._undo() 
                             loop_count -= 1    
                    #we've searched through all roads in fork, time to look for previous forks (if any) and store extra forks in our mult_fork_lists for future analysis
                    if _already_tried is True:
                        print('here within the _already_tried suite')
                        lc = loop_count 

                        if len(fork_list) > 0:
                            for i in range(lc, prev_fork[0]-1, -1):
                                self._undo()
                                loop_count -= 1 
                            data = fork_list.popleft()    
                            idx_adjust_l = data[3]
                            search_fork = data[2]
                            search_loop = data[0]
                            current_fork = prev_fork[2]
                            popped_fork = prev_fork[0]
                            if len(fork_list) > 0:
                                print('adding to our mult_fork_list now')
                                mult_fork_lists.append((prev_fork, fork_list.copy()))
                        else:   
                            idx_adjust_l = 1
                        fork_list.clear()
                    elif idx_adjust_l == copy_fork_size:
                        _already_tried = True
                        prev_fork = fork_data
                        
                elif len(mult_fork_lists) > 0:
                    print('mult_fork_lists:', mult_fork_lists)
                    lc = loop_count
                    data = mult_fork_lists.popleft()
                    data2 = data[1].popleft()
                    for i in range(lc, data[0][0]-1, -1):
                        self._undo()
                        loop_count -= 1
                    idx_adjust_l = data2[3]
                    search_fork = data2[2]
                    search_loop = data2[0]
                    current_fork = data[0][2]
                    popped_fork = data[0][0]
                    if len(data[1]) > 0:
                        mult_fork_lists.append((data[0], data[1]))
                    
                           
                else:
                    print('no alternative break')
                    #if multiple forced moves detected, then move is not actually forced
                    if _is_alternatives is True:
                        _is_forced_move = False 
                        
                    break
            #moves can be made
            elif moves > 0:
                #adjuster will change depending if we are analyzing a different index in current fork
                adjuster = 1
                #more than one option, store in fork_list for future analysis (if necessary)
                if moves > 1:
                    print('current_fork:', current_fork)
                    print('search_fork:', search_fork, search_loop)
                    #if this is fork we are currently analyzing, then use our index adjuster
                    fork_exception = False
                    if move_list == current_fork:
                        if loop_count == popped_fork:
                            adjuster = idx_adjust_l
                        if _already_tried is False:
                            if loop_count == popped_fork:
                                fork_list.appendleft((loop_count, moves, move_list, idx_adjust_l))
                            else:
                                if search_loop is None or loop_count > search_loop:
                                    print('exception1')
                                    fork_exception = True
                        elif loop_count != popped_fork and (search_loop is None or loop_count > search_loop):
                            print('exception2')
                            fork_exception = True
                        
                    if current_fork is None or (move_list == search_fork and loop_count == search_loop):
                        idx_adjust_l = 2 if move_list == search_fork else 1
                        adjuster = idx_adjust_l
                        _already_tried = True if idx_adjust_l == len(move_list) else False
                        search_fork = None
                        current_fork = move_list
                        if _already_tried is False:
                            fork_list.appendleft((loop_count, moves, move_list, idx_adjust_l))
                        else:
                            prev_fork = (loop_count, moves, move_list, idx_adjust_l) 
                    elif (current_fork != move_list and search_fork is None) or fork_exception is True:
                        print('here my theory is true')
                        fork_list.append((loop_count, moves, move_list, idx_adjust_l))
                    
        
                #make the move to see if any other options open up afterwards
                print('idx_adjust_l:', idx_adjust_l) 
                print('adjuster:', adjuster)
                index = len(move_list)-adjuster
                print('movePiece args:', move_list[index])
                self.movePiece(*move_list[index], col=self._team, pipcount=False, highlight=False)
                move_count = 0
            
            #clear this list after every iteration
            move_list.clear()
        
        #put all previous moves used into an instance variable if roll results in a forced move 
        if _is_forced_move is True: 
            #if only one die can be used and is not actually a forced move, then we will set die we cannot use to null
            if two_indices_cond is True:
                if len(self.forced_moves) == 2:
                    print('we found a way to use the other die after declaring two piece, one die')
                    set_to_null = None
                else:
                    _is_forced_move = False
                    print('null dice data:', self._dice_1, self._dice_2)
               
            if _is_forced_move is True:    
                #save forced move as a copy of our _last_move variable (client will use this data)
                self.is_forced_move = True
                #this suite implments all dice must be used, a single forced move can never override a full forced move (all dice used)
                if len(self.forced_moves) == 0:
                    #make a deep copy so (hopefully) forced_move list gets transferred reliably to end of function everytime
                    self.forced_moves = self._last_move
                self._dice_1, self._dice_2, self._dice_3, self._dice_4 = None, None, None, None
                if test is False:
                    self._forcedMove()
                    print('performed _forcedMove()')
                else:
                    if turn_back_on is True:
                        self._animate = True
                    return False
                
                self.forced_moves = copy.deepcopy(self.forced_moves)
                print('forced moves:', self.forced_moves)
            
        if _is_forced_move is False:
            self.is_forced_move = False 
            #save list of all possible moves if move is not forced
            self.potentials = move_list.copy()
            #save list of moves we used to arrive to this point (if any)
            self.before_potentials = copy.deepcopy(self._last_move)
        
        #undo any moves made while looking for forced moves  
        while len(self._last_move) > 0:
            self._undo()
        
        #if move is not forced but only one die can be used, we set the unusable die to null because confirm button is enabled
        #from all dice being null   
        if set_to_null is not None:
            print('setting unusable die to null')
            self._dice_3, self._dice_4 = None, None
            if set_to_null == 1:
                self._dice_1 = None
            else:
                self._dice_2 = None
        
        if turn_back_on is True:
            self._animate = True
        self.is_double = is_doubles       
        dice_data = self._dice_1, self._dice_2, self._dice_3, self._dice_4     
        print('current dice data:', dice_data)
        print('is forced move?:', self.is_forced_move)
        print('forced move list:', self.forced_moves)
        print('last_move variable', self._last_move)
            
    #add a piece(s) to the specified spot index
    #put canvas ids representing the pieces and their color into _piece_locations variable 
    def _addPiece(self, idx, color, count=1):
        #throw an Exception if color arg does not match color of pieces currently occupying that spot
        if len(self._piece_locations[idx]) > 0:
            if self._piece_locations[idx][0][1] != color:
                raise PieceError('Cannot add wrong color piece to a spot')
        coords = self._coords[idx-1]
        diameter = coords[2]-coords[0]
        for i in range(0,count):
            piece_count = len(self._piece_locations[idx])
            if piece_count < 5:
                #drawing coordinates depend on which side user's homeboard is on and how many pieces are located at that spot
                if self._homeboard == 'br':
                    drawCoords = (coords[0], coords[1]-(diameter*piece_count), coords[2], coords[3]-diameter-(diameter*piece_count)) if idx < 13 else \
                                  (coords[0], coords[1]+(diameter*piece_count), coords[2], coords[3]+diameter+(diameter*piece_count))
                elif self._homeboard == 'bl':
                    drawCoords = (coords[0], coords[1]-(diameter*piece_count), coords[2], coords[3]-diameter-(diameter*piece_count)) if idx >= 13 else \
                                  (coords[0], coords[1]+(diameter*piece_count), coords[2], coords[3]+diameter+(diameter*piece_count))
                
                #piece tags will be their color and piece+idx                 
                piece = self.create_oval(*drawCoords, fill=color, outline='black', tags=(color, 'piece'+str(idx)))
                self.tag_bind('piece'+str(idx), '<1>', self._userClickSpot)
                self._piece_locations[idx].append((piece, color))
            #update label above spot if amount of pieces is 5 or more
            else:
                self.labels[idx-1]['text'] = f'+{len(self._piece_locations[idx]) - 4}'
                #0 will represent extra pieces on a spot (over 5)
                self._piece_locations[idx].append(('0', '0')) 
    
    #remove piece(s) from the specified spot index
    #remove the pieces from self._piece_locations, delete from canvas if it is an item (not a label)
    #optional color arg to indciate which color piece to remove from the bar       
    def _removePiece(self, idx, color=None):
        #function will return what color pieces on the spot are
        col = self._piece_locations[idx][0][1] if color is None else color
        #throw an Exception if spot has no pieces occupying it
        if len(self._piece_locations[idx]) == 0:
            raise PieceError('No pieces located at this index:', idx)
        #handling removing a piece from a spot
        if idx < 25 and idx > 0:
            if len(self._piece_locations[idx]) > 5:
                if len(self._piece_locations[idx]) == 6:
                    self.labels[idx-1]['text'] = ''
                    self._piece_locations[idx].pop()
                else:
                    self._piece_locations[idx].pop()
                    self.labels[idx-1]['text'] = f'+{len(self._piece_locations[idx]) - 5}'
            else:
                self.delete(self._piece_locations[idx].pop()[0])
        #removing a piece from the bar or trough
        elif idx >= 25 or idx == 0:
            #order of list is reversed in this loop, which removes piece most recently placed onto bar/into trough
            for piece, c in reversed(self._piece_locations[idx]):
                if col == c:
                    self.delete(piece)
                    self._piece_locations[idx].remove((piece, c))
                    break
                
        
        return col
    
    #move a piece to the bar (just one piece)
    #only one argument for color of piece to put on bar      
    def _moveToBar(self, color):
        TEAM_PIECES = 0
        for p, c in self._piece_locations[26]:
            if c == self._team:
                TEAM_PIECES += 1
           
        OPP_PIECES = len(self._piece_locations[26]) - TEAM_PIECES 
        X_COORD = float(self['width'])/2
        Y_COORD = float(self['height'])/2
        DIAMETER = self._diameter
        drawCoords = ((X_COORD-(DIAMETER//2)), (Y_COORD+(DIAMETER*OPP_PIECES)) if color == self._opponent else \
                      (Y_COORD-(DIAMETER*TEAM_PIECES)), (X_COORD+(DIAMETER//2)), (Y_COORD+(DIAMETER*OPP_PIECES))+DIAMETER if color == self._opponent  else \
                      (Y_COORD-(DIAMETER*TEAM_PIECES))-DIAMETER)
        id = self.create_oval(*drawCoords, fill=color, outline='yellow', tags=(color, 'piece25'+str(len(self._piece_locations[26]))))
        self.tag_bind('piece25'+str(len(self._piece_locations[26])), '<1>', self._userClickSpot)
        self._piece_locations[26].append((id, color))
        
    #move a piece(s) to a trough
    #trough arg will signify which trough to place the piece into (br or bl) and color of piece must be supplied as arg
    def _moveToTrough(self, color, trough):
        print('moving to trough, args:', color, trough)
        if color == self._opponent and trough == self._homeboard:
            raise PieceError('cannot wrong team piece into trough')
        
        #draw pieces in trough as rectangles, depending on which view of the board is active
        #idx 0 is always the 'br' view homeboard, 27 will be 'bl' homeboard
        idx = 0 if trough == 'br' else 25
        total_pieces = len(self._piece_locations[idx])
        width = float(self['width'])
        height = float(self['height'])
        piece_diameter = self._diameter
        piece_height = height*0.023 
        x_start1 = self._coords[11][0]-self._trough_distance
        x_start2 = self._coords[0][0]-self._trough_distance
        drawCoords = None
        if trough == 'br' and color == self._team:
            X_COORD = width-self._trough_distance+x_start1
            Y_COORD = height-x_start1-(total_pieces*piece_height)
            drawCoords = (X_COORD, Y_COORD, X_COORD+piece_diameter, Y_COORD-piece_height)
        elif trough == 'br' and color == self._opponent:
            X_COORD = x_start2
            Y_COORD = x_start2+(total_pieces*piece_height)
            drawCoords = (X_COORD, Y_COORD, X_COORD+piece_diameter, Y_COORD+piece_height)
        elif trough == 'bl' and color == self._opponent:
            X_COORD = width-self._trough_distance+x_start1
            Y_COORD = x_start1+(total_pieces*piece_height)
            drawCoords = (X_COORD, Y_COORD, X_COORD+piece_diameter, Y_COORD+piece_height)
        elif trough == 'bl' and color == self._team:
            X_COORD = x_start2
            Y_COORD = height-x_start2-(total_pieces*piece_height)
            drawCoords = (X_COORD, Y_COORD, X_COORD+piece_diameter, Y_COORD-piece_height)
        
        #draw the rectangle and update _piece_locations with the item   
        id = self.create_rectangle(*drawCoords, fill=color, outline='black', tags=(color))
        self._piece_locations[idx].append((id, color))
   
                
    #set up a fresh game, specifying where user's homeboard will be located on the board 
    #this method MUST be called on a board before pieces are added/moved/etc. 
    #subsequent arg should be True if it is NOT first game since application is launched         
    def setUpGame(self, hblocation, subsequent=False):
        teamcolor = self._colors[3]
        ocolor = self._colors[4]
        #save orientation of homeboard as an instance variable
        if hblocation != 'br' and hblocation != 'bl':
            raise ValueError('must specify homeboard location as br or bl')
        self._homeboard = hblocation
        #save location of doubling cube
        self.cube_location = 'mid'
        #save initial stakes of game (1)
        self.stakes = 1
        #save team color and opponent colors
        self._team = teamcolor if hblocation == 'br' else ocolor
        self._opponent = ocolor if hblocation == 'br' else teamcolor
        if subsequent is False:
            #create list for id numbers of spots (is different order for 'bl' orientation!)
            self._spotid = [27] + [i for i in range(1, 25)] + [28,29]
            if hblocation == 'bl':
                #rearrange spot coordinate list to stay consistant with 'br' setup
                #also rearrange labels array
                new_coords = [self._coords[i] for i in range(12, 24)] + [self._coords[i] for i in range(0, 12)]
                self._coords = new_coords
                new_labels = [self.labels[i] for i in range(12, 24)] + [self.labels[i] for i in range(0, 12)]
                self.labels = new_labels  
                self._spotid = [27] + [i for i in range(13, 25)] + [i for i in range(1, 13)] + [28,29]
        
        print(self._coords)   
        #set up variables for highlighting our spots/pieces in the game
        self.actual_idx_1 = None
        self.actual_idx_2 = None
        self.actual_idx_3 = None
        self.actual_idx_4 = None
        self.actual_idx_5 = None
        
        #put pieces in starting spots for fresh game    
        self._addPiece(1, ocolor, 2)
        self._addPiece(6, teamcolor, 5)
        self._addPiece(8, teamcolor, 3)
        self._addPiece(12, ocolor, 5)
        self._addPiece(13, teamcolor, 5)
        self._addPiece(17, ocolor, 3)
        self._addPiece(19, ocolor, 5)
        self._addPiece(24, teamcolor, 2) 
        
        #draw doubling cube on corresponding side (left for 'br', right for 'bl')
        #cube will consist of a white rectangle with a label on top displaying the current stakes of the match
        #label will also get an event binding so user can actually click entire surface to fire event!
        width = float(self['width'])
        height = float(self['height'])
        side = (1/18)*height
        trough = self._trough_distance
        drawCoords = (trough/2-(side/2), height/2+(side/2), trough/2+(side/2), height/2-(side/2)) if self._homeboard == 'br' else \
        (width-(trough/2)-(side/2), height/2+(side/2), width-(trough/2)+(side/2), height/2-(side/2))
        self.create_rectangle(*drawCoords, fill='white', outline='black', tags=('cube'))
        textLocation = (trough/2, height/2) if self._homeboard == 'br' else (width-(trough/2), height/2)
        self._doubling_label = self.create_text(*textLocation, text='2', font=('TkDefaultFont','30','bold'))
        self.tag_bind('cube', '<1>', lambda e: self._wantsToDouble())
        self.tag_bind(self._doubling_label, '<1>', lambda e: self._wantsToDouble())
        
    #redraw the doubling cube lower or higher on the board (depending on who owner of cube will be)
    #this method will be called by server if player accepts a doubling offer
    #only two valid args; 'team' or 'opp' which will draw cube lower or higher, respectively
    def redrawCube(self, location):
        if self.stakes == 64:
            return
        if location != 'team' and location != 'opp':
            raise ValueError('arg for location must be team or opp')
        self.cube_location = location
        self.stakes = int(self.stakes * 2)
        self.delete('cube', self._doubling_label)
        width = float(self['width'])
        height = float(self['height'])
        side = (1/18)*height
        trough = self._trough_distance
        Y1 = 0 if location == 'opp' else height-side 
        Y2 = side if location == 'opp' else height
        drawCoords = (trough/2-(side/2), Y1, trough/2+(side/2), Y2) if self._homeboard == 'br' else \
        (width-(trough/2)-(side/2), Y1, width-(trough/2)+(side/2), Y2)
        self.create_rectangle(*drawCoords, fill='white', outline='black', tags=('cube'))
        textLocation = (trough/2 if self._homeboard == 'br' else width-(trough/2), Y2-(side/2))
        self._doubling_label = self.create_text(*textLocation, text=str(self.stakes), font=('TkDefaultFont','30','bold'))
        #only make the cube clickable if the cube is redrawn onto their side
        if location == 'team':
            self.tag_bind(self._doubling_label, '<1>', lambda e: self._wantsToDouble())
            
    #reset state of board to a fresh game
    #will delete every item and redraw the board
    def restartGame(self, end=False):
        self.delete('cube', self._doubling_label)
        for i in range(0,27):
            while(len(self._piece_locations[i]) > 0):
                self._removePiece(i)
            
        self._last_move.clear()
        self.forced_moves.clear()
        #reset data for 'bl' setup to prevent corruption of data 
        if end is True and self._homeboard == 'bl':
            self._coords = [self._coords[i] for i in range(12, 24)] + [self._coords[i] for i in range(0, 12)]
            self.labels = [self.labels[i] for i in range(12, 24)] + [self.labels[i] for i in range(0, 12)]
        
    #move a piece(s) from one spot to another
    #all methods used inside this method adjusts _piece_locations
    #optional color arg to indicate which color to remove from the bar 
    #will throw a PieceError if moving to invalid spot
    def movePiece(self, f, t, count=1, dice=None, col=None, barPieces=None, pipcount=True, highlight=True, barAnalysis=True):
        def doMove(fr=f, to=t, cou=count, d=dice, co=col, bar=barPieces, pip=pipcount, high=highlight, barAna=barAnalysis):
            if self.active_thread is True:
                with self.board_lock:
                    self.board_lock.wait()
                    
            if self._animate is True:
                self.active_thread = True
            #unhighlight all pieces/spots before a piece is moved
            if d is not None:
                self._clearSpots() 
            #move piece from one index to another(f to t)
            #every method movePiece uses adjusts self._piece_locations accordingly
            #function will return what color pieces on the spot are
            operation, piece_count, bar_cond, end_coord = None, None, None, None
            for i in range(0,cou):
                c = self._piece_locations[fr][0][1] if co is None else co
                if self._animate is True:   
                    operation, piece_count, bar_cond, end_coord = self._animateMove(fr,to,pc=c,hl=high)
                else:
                    self._removePiece(fr,c)
                    if to == 26:
                        self._moveToBar(c)
                    elif to == 0 or to == 25:
                        self._moveToTrough(c, 'br' if to == 0 else 'bl')
                            
                      
                if to > 0 and to < 25:
                    #if one opponent piece on destination spot, move enemy piece to bar 
                    found_piece = False
                    opp_color = self._opponent if c == self._team else self._team
                    #these conditions reflect that a non animated move can absolutely not have a wrong colored piece on a spot that _addPiece is called on
                    print('here at pertinent data:', len(self._piece_locations[to]), c)
                    if len(self._piece_locations[to]) == 1 and (self._piece_locations[to][0][1] != c) and barAna is True:
                        #store pieces that user moves to bar when no barPieces variable is present (so it can potentially be undone)
                        if bar is None:
                            bar = []
                            bar.append(to)
                        #move the piece to bar right away for non-animated version of board or _addPiece call will throw a PieceException
                        if self._animate is False:
                            self.movePiece(to,26, pipcount=False)
                            
                    if self._animate is False:
                        self._addPiece(to, c) 
                        
                if operation == 'addPiece' or operation == 'moveToBar':
                    if piece_count < 5 or operation == 'moveToBar':
                        piece = self.create_oval(*end_coord, fill=c, outline='black', tags=(c, 'piece'+str(to)))
                        self.tag_bind('piece'+str(to), '<1>', self._userClickSpot)
                        print('bar_cond:', bar_cond)
                        if bar_cond is False:
                            self._piece_locations[to].append((piece, c))
                        else:
                            self._piece_locations[to].insert(0,(piece,c))
                    #update label above spot if amount of pieces is 5 or more
                    else:
                        self.labels[to-1]['text'] = f'+{len(self._piece_locations[to]) - 4}'
                        #0 will represent extra pieces on a spot (over 5)
                        self._piece_locations[to].append(('0', '0')) 
                        
                elif operation == 'moveToTrough':
                    id = self.create_rectangle(*end_coord, fill=c, outline='black', tags=(c))
                    self._piece_locations[to].append((id, c))                        
                    print('barPieces:', bar, 'move:', fr, to)      
                     
                #move forced intermediate opponent pieces to bar if multiple dice are used
                if bar is not None:
                    bar.reverse()
                    for idx in bar:
                        if idx != -1:
                            #if animation is False, then we won't move piece to bar if it's on the place we landed since we already removed it in previous suite
                            if self._animate is True or (self._animate is False and idx != to):
                                self.movePiece(idx, 26, col=opp_color, pipcount=False)
                                if self._animate is True:
                                    #will wait here until bar piece animations are done
                                    with self.board_lock:
                                        self.board_lock.notify()
                                        self.board_lock.wait()
                                        
            #store dice data before altering it in next suites so move can potentially be undone
            dice_state = self._dice_1, self._dice_2, self._dice_3, self._dice_4
            #movePiece has to know which die is being used so it can be set to null for next user click 
            #these conditions work for regular rolls and doubles
            if d == 1:
                if self._dice_4 is None and self._dice_3 is not None:
                    self._dice_1 = self._dice_3
                    self._dice_3 = None
                elif self._dice_3 is None and (self._dice_1 == self._dice_2):
                    self._dice_1 = self._dice_2
                    self._dice_2 = None
                else:
                    self._dice_1 = self._dice_4
                    self._dice_4 = None
            elif d == 2:
                if self._dice_2 is not None:
                    self._dice_2 = None
                else:
                    self._dice_1 = None
            elif d == 3:
                self._dice_1 = self._dice_3
                self._dice_2 = self._dice_4
                self._dice_4 = None
                self._dice_3 = None
            #for doubles
            elif d == 4:
                if self._dice_4 is not None:
                    self._dice_2 = None
                    self._dice_3 = None
                    self._dice_4 = None
                else:
                    self._dice_1 = None
                    self._dice_2 = None
                    self._dice_3 = None
                    
            elif d == 5:
                self._dice_1 = None
                self._dice_2 = None
                self._dice_3 = None
                self._dice_4 = None
                
            #adjust user and opponent pip counts only if our flag to perform calculation is True
            if pip is True:
                #only perform calculation on last move to prevent unneccessary pip calculations
                if (self._dice_1, self._dice_2, self._dice_3, self._dice_4) == (None, None, None, None) or self.is_forced_move is True:
                    self.team_pipcount, self.opp_pipcount = self._pipCount()
                    print('new pip counts:', self.team_pipcount, self.opp_pipcount)
        
            
            #when movePiece is called recursively or called to programmatically move a piece, it just returns  
            if d is None: 
                if to != 26:
                    #alert client application that an opponent move has been performed
                    with self.game_lock:
                        self.game_lock.notify()
                
                self.active_thread = False
                with self.board_lock:
                    self.board_lock.notify()
                        
                return   
            
            print('d:', d)
            print(self._dice_1, self._dice_2, self._dice_3, self._dice_4)
            #store player's move into our instance variable for _undo method to use
            self._last_move.append((to,fr,dice_state,bar)) 
            
            #iterate through bar pieces and count our team pieces currently on the bar to pass to _highlightSpot
            bar_count = 0 
            if fr == 26:   
                for p, c in self._piece_locations[26]:
                    if c == self._team:
                        bar_count += 1  
            
            
            if high is True:
                #give some time before calling highlightSpot to allow our mutations to take effect (avoid race conditions between threads)
                self._highlightSpot(fr, bar_count)
                
            if self._dice_1 is None and self._dice_2 is None and self._dice_3 is None and self._dice_4 is None:
                self._confirm()
                
            self.active_thread = False       
            with self.board_lock:
                self.board_lock.notify()
            return
                    
        #will need to actually call addPiece, addToTrough, etc, here instead of movePiece or some variation of this solution
        if self._animate is True:
            draw_thread = threading.Thread(target=doMove)
            draw_thread.daemon = False
            draw_thread.start()
        else:
            doMove()
            
            
    #return True if game is over        
    def isGameOver(self):
        if len(self._piece_locations[0]) == 15 or len(self._piece_locations[25]) == 15:
            return True
        else:
            return False
        
    #check to see if a player has been gammoned or backgammoned
    #will return 1, 2, or 3 if no gammon, gammon, or backgammon, respectively (multiplier)
    def isGammon(self):
        br_trough = len(self._piece_locations[0]) 
        bl_trough = len(self._piece_locations[25])
        #should not factor in a gammon calculation if game ends as the result of a doubling proposal
        if br_trough != 15 and bl_trough != 15:
            return 1
        bl_color = self._team if self._homeboard == 'bl' else self._opponent
        br_color = self._team if self._homeboard == 'br' else self._opponent
        #if we get to this point, an entire game has been played out and the gammon calcaultion will execute
        if br_trough == 0 or bl_trough == 0:
            losing_team = bl_color if bl_trough == 0 else br_color
            for i in range(19,25) if br_trough == 0 else range(1,7):
                if len(self._piece_locations[i]) > 0 and self._piece_locations[i][0][1] == losing_team:
                    return 3
                
            return 2
        else:
            return 1
        
    #detirmine if a race is active on our board   
    def is_racing(self):
        #race is not on if any pieces are on the bar
        if len(self._piece_locations[26]) > 0:
            return False
        #if we find any of our pieces past an enemy piece, is not race, otherwise it is a race
        found_enemy = False
        for i in range(1,25) if self._homeboard == 'br' else range(24,0,-1):
            if found_enemy is False and len(self._piece_locations[i]) > 0 and self._piece_locations[i][0][1] == self._opponent:
                found_enemy = True
            elif found_enemy is True and len(self._piece_locations[i]) > 0 and self._piece_locations[i][0][1] == self._team:
                return False
            
        return True
            
        
    #set dice to every possible number and if every iteration results in a 0 move forced move, then will return False, otherwise True
    def canRoll(self):
        all_rolls = ((1,2), (3,4), (5,6))
        can_roll = True
        for num, roll in enumerate(all_rolls):
            result = self.setDice(*roll, test=True) 
            if result is False:
                if num == 2:
                    can_roll = False  
            else:
                break
        
        self._dice_1, self._dice_2 = None, None  
        print('canRoll:', can_roll)   
        return can_roll 
    
    #animate a piece going from one index to another
    def _animateMove(self, f, t, pc=None, hl=True):
        try:
            self.bind('<3>', lambda e:print('do nothing callback'))
            self.configure(state='disabled')
            #find first and last coordinates of piece in the animation 
            start_coord = None
            end_coord = None
            #if we find a piece to move to bar, insert into our _piece_locations list at the beginning to make animation look right
            bar_cond = False
            pcolor = self._removePiece(f, color=pc)
            for i in range(0,2):
                chosen_idx = f if i == 0 else t
                piece_count = len(self._piece_locations[chosen_idx])
                p_coord = None
                operation = None
                if chosen_idx > 0 and chosen_idx < 25:
                    coords = self._coords[chosen_idx-1]
                    piece_count = piece_count if piece_count < 6 else 5
                    #when we move a piece to an opposing player's blot
                    if piece_count == 1 and chosen_idx == t and self._piece_locations[chosen_idx][0][1] != pcolor:
                        bar_cond = True
                        piece_count = 0
                    #drawing coordinates depend on which side user's homeboard is on and how many pieces are located at that spot
                    if self._homeboard == 'br':
                        p_coord = (coords[0], coords[1]-(self._diameter*piece_count), coords[2], coords[3]-self._diameter-(self._diameter*piece_count)) if chosen_idx < 13 else \
                                      (coords[0], coords[1]+(self._diameter*piece_count), coords[2], coords[3]+self._diameter+(self._diameter*piece_count))
                    elif self._homeboard == 'bl':
                        p_coord = (coords[0], coords[1]-(self._diameter*piece_count), coords[2], coords[3]-self._diameter-(self._diameter*piece_count)) if chosen_idx >= 13 else \
                                      (coords[0], coords[1]+(self._diameter*piece_count), coords[2], coords[3]+self._diameter+(self._diameter*piece_count))
                    operation = 'addPiece'
                elif chosen_idx == 26:
                    TEAM_PIECES = 0
                    for p, c in self._piece_locations[26]:
                        if c == self._team:
                            TEAM_PIECES += 1
                       
                    OPP_PIECES = len(self._piece_locations[26]) - TEAM_PIECES 
                    X_COORD = float(self['width'])/2
                    Y_COORD = float(self['height'])/2
                    DIAMETER = self._diameter
                    p_coord = ((X_COORD-(DIAMETER//2)), (Y_COORD+(DIAMETER*OPP_PIECES)) if pcolor == self._opponent else \
                                  (Y_COORD-(DIAMETER*TEAM_PIECES)), (X_COORD+(DIAMETER//2)), (Y_COORD+(DIAMETER*OPP_PIECES))+DIAMETER if pcolor == self._opponent  else \
                                  (Y_COORD-(DIAMETER*TEAM_PIECES))-DIAMETER)
                    operation = 'moveToBar'
                else:
                    width = float(self['width'])
                    height = float(self['height'])
                    piece_diameter = self._diameter
                    piece_height = height*0.023 
                    x_start1 = self._coords[11][0]-self._trough_distance
                    x_start2 = self._coords[0][0]-self._trough_distance
                    if self._homeboard == 'br' and pcolor == self._team:
                        X_COORD = width-self._trough_distance+x_start1
                        Y_COORD = height-x_start1-(piece_count*piece_height)
                        p_coord = (X_COORD, Y_COORD, X_COORD+piece_diameter, Y_COORD-piece_height)
                    elif self._homeboard == 'br' and pcolor == self._opponent:
                        X_COORD = width-self._trough_distance+x_start1
                        Y_COORD = x_start1+(piece_count*piece_height)
                        p_coord = (X_COORD, Y_COORD, X_COORD+piece_diameter, Y_COORD+piece_height)
                    elif self._homeboard == 'bl' and pcolor == self._team:
                        X_COORD = x_start2
                        Y_COORD = height-x_start2-(piece_count*piece_height)
                        p_coord = (X_COORD, Y_COORD, X_COORD+piece_diameter, Y_COORD-piece_height)
                    elif self._homeboard == 'bl' and pcolor == self._opponent:
                        X_COORD = x_start2
                        Y_COORD = x_start2+(piece_count*piece_height)
                        p_coord = (X_COORD, Y_COORD, X_COORD+piece_diameter, Y_COORD+piece_height)
                    operation = 'moveToTrough'
                                  
                if chosen_idx == f:
                    start_coord = list(p_coord)
                else:
                    end_coord = p_coord
            
            #calculate distance between start and end of both lines and use a formula to deduce the coordinates at each point of line in the animation
            l1_x2, l1_x1, l1_y2, l1_y1 = end_coord[0], start_coord[0], end_coord[1], start_coord[1]
            l2_x2, l2_x1, l2_y2, l2_y1 = end_coord[2], start_coord[2], end_coord[3], start_coord[3]
            d1 = math.sqrt((l1_x2 - l1_x1)**2 + (l1_y2 - l1_y1)**2)
            d2 = math.sqrt((l2_x2 - l2_x1)**2 + (l2_y2 - l2_y1)**2)
            larger_distance = d1 if d1 > d2 else d2 
            traversed_dist = 0
            while(traversed_dist < larger_distance):
                l1_new_x = l1_x1 - ((traversed_dist*(l1_x1-l1_x2))/d1)
                l1_new_y = l1_y1 - ((traversed_dist*(l1_y1-l1_y2))/d1)
                l2_new_x = l2_x1 - ((traversed_dist*(l2_x1-l2_x2))/d1)
                l2_new_y = l2_y1 - ((traversed_dist*(l2_y1-l2_y2))/d1) 
                self.delete('animation')
                self.create_oval(l1_new_x, l1_new_y, l2_new_x, l2_new_y, fill=pcolor, outline='black', tags=('animation'))
                sleep(0.035)
                traversed_dist += 30
            
                   
            self.delete('animation')
            self.configure(state='normal')
            self.bind('<3>', lambda e: self._undo())
            return operation, piece_count, bar_cond, end_coord
        except Exception as ce:
            print(type(ce))
            print(traceback.format_exc())
            sys.exit(0)
         
        
    
    #return pip count as a tuple representing team and opponent pip counts, respectively
    def _pipCount(self):
        pips_team = 0
        pips_opp = 0
        #check bar pieces first
        for p, c in self._piece_locations[26]:
            if c == self._team:
                pips_team += 25
            else:
                pips_opp += 25
                
        for i in range(1, 25):
            size = len(self._piece_locations[i])
            if size > 0:
                color = self._piece_locations[i][0][1]
                if self._homeboard == 'br' and color == self._team:
                    pips_team += size * i 
                elif self._homeboard == 'bl' and color == self._opponent:
                    pips_opp += size * i 
                elif self._homeboard == 'br' and color == self._opponent:
                    pips_opp += (25 - i) * size
                elif self._homeboard == 'bl' and color == self._team:
                    pips_team += (25 - i) * size
                
        return str(pips_team), str(pips_opp)
             
    #this method will be called when player clicks on doubling cube in correct position
    def _wantsToDouble(self):
        print('here at _wantsToDouble()')
        print(self._dice_1, self._dice_2, self._dice_3, self._dice_4)
        if self._dice_1 is None and self._dice_2 is None and self._dice_3 is None and self._dice_4 is None \
        and self.button.instate(['disabled']) and (self.cube_location == 'mid' or self.cube_location == 'team') and self.stakes < 64:
            print('user wants to double')
            self.client_method()
        
        
    
    #if user right-clicks on the board, this method will be called and will undo previous move 
    def _undo(self):
        self._clearSpots()
        self.button.state(['disabled'])
        if len(self._last_move) > 0:
            prev = self._last_move.pop()
            #restore dice data back to previous state
            self._dice_1, self._dice_2, self._dice_3, self._dice_4 = prev[2]
            print('undo move:', prev)
             #move last piece moved back to it's original place
            #for non-animation mode, this move must be done first or barPieces suite will try to send it to bar with movePiece call!!
            self.movePiece(*prev[0:2], pipcount=False, highlight=False)    
            #move any opponent pieces that were taken to the bar back to their original places
            if prev[3] is not None:
                loop_count = 0
                for idx in prev[3]:
                    loop_count += 1
                    print('iter in _undo:', loop_count)
                    if idx != -1:
                        self.movePiece(26,idx,col=self._opponent,pipcount=False,highlight=False, barAnalysis=False)
                        
                            
    
    
    #forced move has been detected, enable client's forced move button and disable the whole Backgammon board object      
    def _forcedMove(self):
        self.configure(state='disabled')
        self.button_2.state(['!disabled'])
        #if no moves can be made, we will programmatically 'click' the forced move button
        if len(self.forced_moves) == 0:
            print('invoking button')
            self.button_2.invoke()
        
    #when all dice are null, board will call this to enable client's Confirm button
    def _confirm(self):
        self.button.state(['!disabled'])
    
    #client will use this method to refresh board to fresh state after player has performed their move   
    def confirm(self):
        self._last_move.clear()
        self.forced_moves.clear()
        self.before_potentials.clear()
        
    
