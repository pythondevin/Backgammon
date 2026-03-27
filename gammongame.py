from tkinter import *
from tkinter import ttk
from screeninfo import get_monitors
import threading
import math
from copy import deepcopy
import sys
import traceback
from random import randint
from time import time
from queue import Queue
NUMBER_OF_PIECES = 15

#will use a fixed size Canvas object to represent a die
#can be rolled with rollDie()
class Dice(Canvas):
    def __init__(self, parent):
        super().__init__(parent, background='white')
        self['height'] = 60
        self['width'] = 60
        self.die_value = None
        self.dot_size = 3
        self.animation_lock = threading.Condition()
    #is passed the value of die to display   
    def drawDie(self, val):
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
            self.create_oval(*CENTER_COORDS, fill='black', tags=('dot'))
        elif val == 6:
            self.drawDie(4)
            self.create_oval(WIDTH/4-DOT_SIZE, HEIGHT/2-DOT_SIZE, WIDTH/4+DOT_SIZE, HEIGHT/2+DOT_SIZE, fill='black', tags=('dot'))
            self.create_oval(WIDTH*(3/4)-DOT_SIZE, HEIGHT/2-DOT_SIZE, WIDTH*(3/4)+DOT_SIZE, HEIGHT/2+DOT_SIZE, fill='black', tags=('dot'))

        return val
            
    def clearDie(self):
        self.delete('dot')
        
    def get(self):
        return self.die_value

    #animation for 'rolling' a die, flash random numbers quickly, slow down incrementally, then stop on final number
    #if finalNum is None, we generate random number during this function. If not None, we can essentially 'set' the die using this function and this arg
    #finalRoll True will halt thread that called the rolling function until rolling is complete. Otherwise will thread will continue immediatley after beginning the roll
    #optional duration arg controls how long animation is
    def rollDie(self, finalNum=None, finalRoll=True, duration=1.0):
        #do a series of quick flashes, medium speed flashes, and slow flashes
        #how many flashes and amount of time between flashes is controlled here
        def roll(quickFlashCount, mediumFlashCount, slowFlashCount, quickDelay, mediumDelay, slowDelay, quickFlashMax, mediumFlashMax, slowFlashMax):
            val = randint(1,6)
            self.drawDie(val)
            if quickFlashCount < quickFlashMax*duration:
                quickFlashCount += 1
                self.after(quickDelay, roll, quickFlashCount, mediumFlashCount, slowFlashCount, quickDelay, mediumDelay, slowDelay, quickFlashMax, mediumFlashMax, slowFlashMax)
                chosenDelay = quickDelay
            elif mediumFlashCount < mediumFlashMax*duration:
                mediumFlashCount += 1
                self.after(mediumDelay, roll, quickFlashCount, mediumFlashCount, slowFlashCount, quickDelay, mediumDelay, slowDelay, quickFlashMax, mediumFlashMax, slowFlashMax)
                chosenDelay = mediumDelay
            elif slowFlashCount < slowFlashMax*duration:
                slowFlashCount += 1
                self.after(slowDelay, roll, quickFlashCount, mediumFlashCount, slowFlashCount, quickDelay, mediumDelay, slowDelay, quickFlashMax, mediumFlashMax, slowFlashMax)
                chosenDelay=slowDelay
            else:
                if finalNum is not None:
                    self.clearDie()
                    self.drawDie(finalNum)
                    self.die_value = finalNum
                else:
                    self.die_value = val

                with self.animation_lock:
                    self.animation_lock.notify()

                return

            #clear die for a small amount of time between flashes, make sure always lower than the chosenDelay variable!
            self.after(int(chosenDelay-(0.15*quickDelay)), self.clearDie)

        animation_thread = threading.Thread(target=roll, args=(0,0,0,50,100,150,15,7,3), daemon=True)
        animation_thread.start()

        if finalRoll is True:
            with self.animation_lock:
                self.animation_lock.wait()

#class representing two Dice a client will use for their game interface
class DiceSet():
    def __init__(self, d1, d2):
        if type(d1) is not Dice or type(d2) is not Dice:
            raise ValueError('must pass DiceSet Dice objects')

        self._d1 = d1
        self._d2 = d2 

    #roll both dice in our set, have second die finish shortly after our first
    #finalNum arg for 'setting' the dice but still using the rolling animation
    def rollDice(self, finalNum1=None, finalNum2=None):
        self._d1.rollDie(finalNum=finalNum1, finalRoll=False)
        self._d2.rollDie(finalNum=finalNum2, duration=1.4)

    def getDice(self):
        return self._d1.get(), self._d2.get()

    def clearDice(self):
        self._d1.clearDie()
        self._d2.clearDie()
       

#custom Exceptions BackgammonBoard and game scripts will use
class GackError(Exception):
    pass

class PieceError(GackError):
    pass

#draw backgammon board using Canvas facilities
#adjusts it's own size depending on user's screen resolution using third party module (screeninfo)
#will click on piece or spot and will highlight everywhere piece(s) from that spot can go with dice data
#userClickSpot--->highlightSpot--->movePiece--->highlightSpot--->movePiece is basic flow, is restarted when user clicks on a different spot/piece or no more moves to be made
class BackgammonBoard(Canvas):
    #instantiate BackgammonBoard with parent, colors of board, and client's Confirm move button, forced move button, client's thread lock(for notifying client), and doubling method
    def __init__(self, parent, colors, b, b2, doubling_method, animate=True):
        #create a Canvas object with super() call
        super().__init__(parent, background=colors[0])
        self.root = parent
        #save colors as instance variable for future configuration, will be same order for both players in game!!
        self._colors = list(colors)
        #save client confirm and forced move buttons as instance variables
        self.button = b
        self.button_2 = b2
        #save client's doubling method
        self.client_method = doubling_method
        #animation method needs to wait while a recursive animation function is being executed
        self.animation_lock = threading.Condition()
        #create dictionary to hold spot number and pieces currently occupying it
        self._piece_locations = {i:[] for i in range(0,28)}
        #create the dice instance data, will have mutator method (setDice())
        #dice 3 and 4 in case user rolls doubles
        self._dice_1 = None
        self._dice_2 = None
        self._dice_3 = None
        self._dice_4 = None
        #set up list containing all moves a player will make during their turn
        self._last_move = []
        self._last_move_copy = []
        self.forced_moves = []
        self.move_history = set()
        self.availableMoves = []
        self.alt_move_lists = []
        #instance variables for analyzing every potential move (GameStrategy classes will use these)
        self.blot_list = []
        self.blot_indices = []
        self.blot_odds = {}
        self.clog_list = []
        self.clog_indices = []
        self.unclog_list = []
        self.unclog_indices = []
        self.bar_list = []
        self.bar_indices = []
        self.opponent_pips = []
        self.safe_moves = []
        self.safe_move_indices = []
        self.piecesBehind = 0
        self.behindSpots = []
        #initialize pipcount variables as strings (for Tkinter)
        self.team_pipcount = '167'
        self.opp_pipcount = '167'
        self._animate = animate
        self.isForcedMove = None
        #Queue class is thread safe, we use it for our synchonization among threads for moving pieces and propogating Exceptions across threads
        self.synchQueue = Queue()
        self.activeThread = False
        #draw an empty backgammon board
        self._drawBoard()
        
    def _drawBoard(self):
        #extract height and width of user monitor
        #consider just using winfo built-in calculations for max height and max width
        for m in get_monitors():
            self.minfo = (m.height, m.width)
        MAX_HEIGHT = self.minfo[0]
        MAX_WIDTH = self.minfo[1]
        #adjust height of Canvas to 70% of user's screen height and 55% of screen width
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
        id = self.create_rectangle(WIDTH-X_TROUGH_DISTANCE+5, HEIGHT-5, WIDTH-5, (HEIGHT/2)+5, fill=colors[5], outline='black', tags=('troughbr'))
        id = self.create_rectangle(5, HEIGHT-5, X_TROUGH_DISTANCE-5, (HEIGHT/2)+5, fill=colors[5], outline='black', tags=('troughbl'))
        
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
            id = self.create_window(self._coords[i][4], self._coords[i][5]-d if i < 12 else self._coords[i][5]+d ,window=l, tags=(f'window{i}'))
            #hide our label for now, will unhide when we need it
            self.itemconfigure(f'window{i}', state='hidden')
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
            if pieces > 1:
                self.itemconfigure(self._piece_locations[idx][-1][0], outline='black')
                
        if self.actual_idx_2 is not None:
            idx = self._spotid.index(self.actual_idx_2) 
            self.dtag('all', 'validspot2')
            self.addtag('spot', 'withtag', self.actual_idx_2)
            self.itemconfigure(self.actual_idx_2, outline='black')
            pieces = len(self._piece_locations[idx]) if idx <= 25 else 0 
            if pieces > 1:
                self.itemconfigure(self._piece_locations[idx][-1][0], outline='black')
                
        if self.actual_idx_3 is not None:
            idx = self._spotid.index(self.actual_idx_3) 
            self.dtag('all', 'validspot3')
            self.addtag('spot', 'withtag', self.actual_idx_3)
            self.itemconfigure(self.actual_idx_3, outline='black')
            pieces = len(self._piece_locations[idx]) if idx <= 25 else 0 
            if pieces > 1:
                self.itemconfigure(self._piece_locations[idx][-1][0], outline='black')

        if self.actual_idx_4 is not None:
            idx = self._spotid.index(self.actual_idx_4) 
            self.dtag('all', 'validspot4')
            self.addtag('spot', 'withtag', self.actual_idx_4)
            self.itemconfigure(self.actual_idx_4, outline='black')
            pieces = len(self._piece_locations[idx]) if idx <= 25 else 0 
            if pieces > 1:
                self.itemconfigure(self._piece_locations[idx][-1][0], outline='black')
                
        if self.actual_idx_5 is not None:
            idx = self._spotid.index(self.actual_idx_5) 
            self.dtag('all', 'validspot5')
            self.addtag('spot', 'withtag', self.actual_idx_5)
            self.itemconfigure(self.actual_idx_5, outline='black')
            pieces = len(self._piece_locations[idx]) if idx <= 25 else 0 
            if pieces > 1:
                self.itemconfigure(self._piece_locations[idx][-1][0], outline='black')
    
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
            spot_idx = 26
        elif spot_idx is None:
            if event.x >= float(self['width'])-self._trough_distance and event.y > float(self['height'])/2 and self._homeboard == 'br':
                spot_idx = 0
            elif event.x <= self._trough_distance and event.y > float(self['height'])/2 and self._homeboard == 'bl':
                spot_idx = 25
            else:
                return
                        
        print('user click spot ', spot_idx)
        
        #iterate through bar pieces and count our team pieces currently on the bar
        bar_count = 0    
        for p, c in self._piece_locations[26]:
            if c == self._team:
                bar_count += 1
        
        #check if any team pieces on the bar and set the flag accordingly
        _is_bar = True if bar_count > 0 else False
        #if user clicks an empty spot or a spot occupied by opponent pieces or there are team pieces on bar AND user did not click on a bar pieces, do nothing
        if len(self._piece_locations[spot_idx]) == 0 or (self._piece_locations[spot_idx][0][1] == self._opponent and spot_idx != 26) or (_is_bar is True and spot_idx != 26) or color == self._opponent:
            return
        
        #do nothing if user clicks on a trough to start a move
        if spot_idx == 0 or spot_idx == 25:
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
        homeboardCount = self.countHomeboardPieces(self._homeboard, self._team)
        #reused condition if all user's pieces are home or just one piece is out and that's the piece they clicked
        home_condition = homeboardCount == NUMBER_OF_PIECES or (homeboardCount == 14 and ((idx > 6) if self._homeboard == 'br' else idx < 19))
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
                
            
        #next suites are in case user rolls doubles
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
        
        
        #check for duplicate results for actual_idx_3 to actual_idx_5 to avoid double tagging trough
        self.actual_idx_3 = self.actual_idx_3 if self.actual_idx_3 != self.actual_idx_1 and self.actual_idx_3 != self.actual_idx_2 else None
        self.actual_idx_4 = self.actual_idx_4 if self.actual_idx_4 != self.actual_idx_3 else None
        self.actual_idx_5 = self.actual_idx_5 if self.actual_idx_5 != self.actual_idx_4 else None

        #if counting arg is True, will return move data now and avoid any highlighting
        #board's generator function (self.countMoves()) uses this to yield all available move data
        if is_counting is True:
            return light_idx_1 if self.actual_idx_1 is not None else None, light_idx_2 if self.actual_idx_2 is not None else None, \
                light_idx_3 if self.actual_idx_3 is not None else None, light_idx_4 if self.actual_idx_4 is not None else None, \
                light_idx_5 if self.actual_idx_5 is not None else None
        
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
            self.tag_bind('validspot1', '<1>', lambda e: self.movePiece(idx, light_idx_1, dice=1, col=None if idx != 26 else self._team, highlight=True).start())
            self.dtag(self.actual_idx_1, 'spot')
            self.itemconfigure(self.actual_idx_1, outline=ol)
            #avoid highlighting pieces with movePiece action if trough is being highlighted
            if light_idx_1 != 25 and light_idx_1 != 0:
                pieces = len(self._piece_locations[light_idx_1]) if light_idx_1 <= 25 else 0
                if pieces > 1:
                    self.addtag('validspot1', 'withtag', self._piece_locations[light_idx_1][-1][0])
                    self.itemconfigure(self._piece_locations[light_idx_1][-1][0], outline=ol)
                    self.tag_raise(self._piece_locations[light_idx_1][-1][0])
                
        if self.actual_idx_2 is not None:
            self.addtag('validspot2', 'withtag', self.actual_idx_2)
            self.tag_bind('validspot2', '<1>', lambda e: self.movePiece(idx, light_idx_2, dice=2, col=None if idx != 26 else self._team, highlight=True).start())
            self.dtag(self.actual_idx_2, 'spot')
            self.itemconfigure(self.actual_idx_2, outline=ol)
            if light_idx_2 != 25 and light_idx_2 != 0:
                pieces = len(self._piece_locations[light_idx_2]) if light_idx_2 <= 25 else 0
                if pieces > 1:
                    self.addtag('validspot2', 'withtag', self._piece_locations[light_idx_2][-1][0])
                    self.itemconfigure(self._piece_locations[light_idx_2][-1][0], outline=ol)
                    self.tag_raise(self._piece_locations[light_idx_2][-1][0])
                
        if self.actual_idx_3 is not None:
            self.addtag('validspot3', 'withtag', self.actual_idx_3)
            self.tag_bind('validspot3', '<1>', lambda e: self.movePiece(idx, light_idx_3, dice=3, col=None if idx != 26 else self._team,\
                                                                         barPieces=_goToBar[0:3] if bar_cond else None, highlight=True).start())
            self.dtag(self.actual_idx_3, 'spot')
            self.itemconfigure(self.actual_idx_3, outline=ol)
            if light_idx_3 != 25 and light_idx_3 != 0:
                pieces = len(self._piece_locations[light_idx_3]) if light_idx_3 <= 25 else 0
                if pieces > 1:
                    self.addtag('validspot3', 'withtag', self._piece_locations[light_idx_3][-1][0])
                    self.itemconfigure(self._piece_locations[light_idx_3][-1][0], outline=ol)
                    self.tag_raise(self._piece_locations[light_idx_3][-1][0])
                
        if self.actual_idx_4 is not None:
            self.addtag('validspot4', 'withtag', self.actual_idx_4)
            self.tag_bind('validspot4', '<1>', lambda e: self.movePiece(idx, light_idx_4, dice=4, col=None if idx != 26 else self._team, \
                                                                        barPieces=_goToBar[0:4] if bar_cond else None, highlight=True).start())
            self.dtag(self.actual_idx_4, 'spot')
            self.itemconfigure(self.actual_idx_4, outline=ol)
            if light_idx_4 != 25 and light_idx_4 != 0:
                pieces = len(self._piece_locations[light_idx_4]) if light_idx_4 <= 25 else 0
                if pieces > 1:
                    self.addtag('validspot4', 'withtag', self._piece_locations[light_idx_4][-1][0])
                    self.itemconfigure(self._piece_locations[light_idx_4][-1][0], outline=ol)
                    self.tag_raise(self._piece_locations[light_idx_4][-1][0])
                
        if self.actual_idx_5 is not None:
            self.addtag('validspot5', 'withtag', self.actual_idx_5)
            self.tag_bind('validspot5', '<1>', lambda e: self.movePiece(idx, light_idx_5, dice=5, col=None if idx != 26 else self._team, \
                                                                        barPieces=_goToBar[0:5] if bar_cond else None, highlight=True).start())
            self.dtag(self.actual_idx_5, 'spot')
            self.itemconfigure(self.actual_idx_5, outline=ol)
            if light_idx_5 != 25 and light_idx_5 != 0:
                pieces = len(self._piece_locations[light_idx_5]) if light_idx_5 <= 25 else 0
                if pieces > 1:
                    self.addtag('validspot5', 'withtag', self._piece_locations[light_idx_5][-1][0])
                    self.itemconfigure(self._piece_locations[light_idx_5][-1][0], outline=ol)
                    self.tag_raise(self._piece_locations[light_idx_5][-1][0])        
                    
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
    
    #count pieces we have in homeboard
    def countHomeboardPieces(self, homeboard, color):
        hbCount = len(self._piece_locations[0]) if homeboard == 'br' else len(self._piece_locations[25]) #start with counting trough pieces
        for i in range(1,7) if homeboard == 'br' else range(19,25):
            if len(self._piece_locations[i]) > 0 and self._piece_locations[i][0][1] == color:
                hbCount += len(self._piece_locations[i])
        return hbCount
    #generator that yields tuples representing all moves that can be made with current dice data
    def countMoves(self, bar_count, reverse=False):
        #yield moves from pieces on bar one at a time until no more team pieces on bar detected
        if bar_count != 0:
             yield 26, self._highlightSpot(26, is_counting=True)
        else:
            for key, value in self._piece_locations.items() if reverse is False else reversed(self._piece_locations.items()):
                if len(value) > 0 and value[0][1] == self._team:
                    yield key, self._highlightSpot(key,is_counting=True)
    
    #count number of dice currently active           
    def countDice(self):
        count = 0
        for d in (self._dice_1, self._dice_2, self._dice_3, self._dice_4):
            if d is not None:
                count += 1 
                
        return count

    #count number of pieces of bar (team, opponent, or all pieces)
    def _countBarPieces(self, count=None):
        counter = 0
        for piece, col in self._piece_locations[26]:
            if count == 'team':
                if col == self._team:
                    counter += 1
            elif count == 'opp':
                if col == self._opponent:
                    counter += 1
            else:
                counter += 1

        return counter

    #return tuple representing how many pieces we have in opp homeboard, and how many pieces opponent has in our homeboard
    def countPiecesInOpp(self):
        homeCount = 0
        oppCount = 0
        for homeSpot, oppSpot in zip(self.hb_indices, self.opp_hb_indices):
            if len(self._piece_locations[oppSpot]) > 0 and self._piece_locations[oppSpot][0][1] == self._team:
                homeCount += len(self._piece_locations[oppSpot])
            if len(self._piece_locations[homeSpot]) > 0 and self._piece_locations[homeSpot][0][1] == self._opponent:
                oppCount += len(self._piece_locations[homeSpot])
        #don't forget to add in pieces on the bar
        homeCount += self._countBarPieces('team')
        oppCount += self._countBarPieces('opp')
        return homeCount, oppCount

    #return how many spots on enemy or our homeboard are clogged
    #optionally return how many blots are on specified homeboard
    def cloggedHomeboard(self, team, criteria='clog'):
        count = 0
        if team == self._team:
            for spot in self.hb_indices:
                if criteria == 'clog':
                    if len(self._piece_locations[spot]) > 1 and self._piece_locations[spot][0][1] == self._team:
                        count += 1
                elif criteria == 'blot':
                    if len(self._piece_locations[spot]) == 1 and self._piece_locations[spot][0][1] == self._team:
                        count += 1

        elif team == self._opponent:
            for spot in self.opp_hb_indices:
                if criteria == 'clog':
                    if len(self._piece_locations[spot]) > 1 and self._piece_locations[spot][0][1] == self._opponent:
                        count += 1
                elif criteria == 'blot':
                    if len(self._piece_locations[spot]) == 1 and self._piece_locations[spot][0][1] == self._opponent:
                        count += 1

        return count

    #get a copy of all dice values
    def getDice(self):
        return (self._dice_1, self._dice_2, self._dice_3, self._dice_4)

    #function for detirming moves available to use based on current dice data
    #puts all moves into list
    def countCompletedMoves(self, nm):
        #countMoves is a generator function that yields move data
        for idx, move in self.countMoves(self._countBarPieces(count='team')):
            if move != (None, None, None, None, None):
                nm.append((idx,move))
             
    #mutator method for setting current dice roll data into BackgammonBoard
    #always assigns the higher die to self._dice_1 variable
    #will check for forced moves by calling forcedMoveDetection()
    #count being True will look for every possible move, False will stop looking for moves once detirmined not to be a forced move
    def setDice(self, d1, d2):
        is_doubles = False
        if d1 != d2:
            self._dice_1, self._dice_2 = (d2,d1) if d1 < d2 else (d1,d2)
            self._dice_3 = None
            self._dice_4 = None
        else:
            self._dice_1, self._dice_2, self._dice_3, self._dice_4 = d1, d1, d1, d1
            is_doubles = True
        
        self.is_double = is_doubles

    #make a copy of our board, do move analyzing on the board copy, and assign our instance variables from the board copy's data
    #do forced move detection on our board
    def analyzeMoves(self, count):
        if count is not True and count is not False:
            raise ValueError('count must be a Boolean')
        
        board_copy = self.createCopy('team')
        board_copy._analyzeMoves(board_copy._countBarPieces(count='team'), counting=count)
        self.move_history, self.availableMoves, self._last_move_copy, self.blot_list, self.blot_indices, self.unclog_list, self.unclog_indices, self.clog_list, self.clog_indices, self.bar_list, self.bar_indices, self.opponent_pips, self.safe_moves, self.safe_move_indices, self.ex_count \
            = board_copy.move_history, board_copy.availableMoves, board_copy._last_move_copy, board_copy.blot_list, board_copy.blot_indices, board_copy.unclog_list, board_copy.unclog_indices, board_copy.clog_list, board_copy.clog_indices, board_copy.bar_list, board_copy.bar_indices, board_copy.opponent_pips, board_copy.safe_moves, board_copy.safe_move_indices, board_copy.ex_count 
        self._forcedMoveDetection()
     
    #detect forced moves, inner function recursively calls itself to keep track of number of moves available to player
    #must pass number of team pieces currently on bar
    #if counting arg is True, this function will put all possible moves into self.move_history variable and other various lists for further analyzisation 
    #if counting arg is False, will halt as soon (or if) move is detirmined not to be forced
    def _analyzeMoves(self, bar_pieces, counting=False):
        back_on = False
        if self._animate is True:
            #turn off animation at start of method, turn it back on at end
            self._animate = False
            back_on = True
       
        move_list = []
        #keep track of how many times we exhaust all of our dice looking for moves
        self.ex_count = 0
        #analyze which moves leave blot, clogs a spot, etc
        if counting is True:
            #keep track of every move that leaves a blot
            self.blot_list.clear()
            self.blot_indices.clear()
            #keep track of every spot we can potentially clog
            self.clog_list.clear()
            self.clog_indices.clear()
            #keep track of every spot we leave empty
            self.unclog_list.clear()
            self.unclog_indices.clear()
            #keep track of every move that can put opponent on the bar and the opponent's pipcount after sending piece(s) to bar
            self.bar_list.clear()
            self.bar_indices.clear()
            self.opponent_pips.clear()
            #moves that aren't in blot list will be considered safe
            self.safe_moves.clear()
            self.safe_move_indices.clear()
            #make a deep copy of _piece_locations variable before any moves are made
            self._piece_loc_copy = deepcopy(self._piece_locations)
        #perform moves in move list (ml) and put this list in alt_move_lists if we discover new moves as a result and analyze rest of list later 
        #if count is True, will perform move analysis such as which moves leave blots, clogs a spot, and will always return all possible moves
        def doMoves(ml, start=0,count = False):
            ct = count
            for idx, (fr, moves) in enumerate(ml[start:]):
                if self.ex_count > 1 and count is False:
                    break
                for die, to in enumerate(moves[:2], 1):
                    #if we can use our dice in more than one way, move is not forced
                    #we will break out of loop if move is not forced and count arg is false
                    if to is not None:
                        dice_count = self.countDice()
                        #after move is performed, we might have new set of moves to explore
                        new_move_list = []
                        self.movePiece(fr, to, dice=die, col=self._team)
                        #look to see if new moves opened up as a result
                        self.countCompletedMoves(new_move_list)
                        #we will save dice data to explore rest of current move list later if new moves were detected
                        if len(new_move_list) > 0:
                            self.alt_move_lists.append(dice_count)
                            doMoves(new_move_list, count=ct)
                            continue
                            
                        #we don't want to undo moves if new moves were detected in last suite, will already be undone by recursive doMoves calls
                        #put our moves into cache before we undo them
                        self._last_move_copy.append(self._last_move.copy())
                        #keep track of every move we make before we undo our moves
                        new_moves = []
                        move_indices = set()
                        for move in self._last_move:
                            #fix mysterious bug of player leaving bar with only one option, a copy of move list is somehow appended to end of new_moves (sometimes)
                            if isinstance(move,tuple):
                                #we don't want program to think it clogged or unclogged spot 26, which is the bar
                                if move[1] != 26:
                                    move_indices.add(move[1])
                                if move[0] != 25 and move[0] != 0:
                                    move_indices.add(move[0])
                                new_moves.append((move[1], move[0]))

                        old_len = len(self.move_history)
                        #sort new moves for duplicate move detection
                        self.move_history.add(tuple(sorted(new_moves)))
                        new_len = len(self.move_history)
                        dice_count = self.countDice()
                        #only perform analyzation if is a unique move
                        if new_len > old_len:
                            #this list will be used for analysis
                            self.availableMoves.append(tuple(new_moves))
                            #count how many times we use all our dice
                            if dice_count == 0:
                                self.ex_count += 1
                            #analyze the result of our move before we _undo() any moves
                            if count is True:
                                if self._piece_loc_copy == self._piece_locations:
                                    raise ValueError('piece_locations copy is exact match of original')
                                #booleans to prevent duplicates
                                unclog_found = False
                                clog_found = False
                                blot_found = False
                                bar_found = False
                                safe_found = False
                                bar_pieces = set()
                                for idx in move_indices:
                                    #see if spot was unclogged
                                    if len(self._piece_loc_copy[idx]) >= 2 and len(self._piece_locations[idx]) < 2:
                                        if unclog_found is False:
                                            unclog_found = True
                                            self.unclog_list.append(tuple(new_moves))
                                            self.unclog_indices.append({spot for spot in move_indices if len(self._piece_loc_copy[spot]) > 2 and len(self._piece_locations[spot]) < 2})
                                    #see if spot was clogged
                                    if len(self._piece_loc_copy[idx]) < 2 and len(self._piece_locations[idx]) > 1:
                                        if clog_found is False:
                                            clog_found = True
                                            self.clog_list.append(tuple(new_moves))
                                            self.clog_indices.append({spot for spot in move_indices if len(self._piece_loc_copy[spot]) < 2 and len(self._piece_locations[spot]) >= 2})
                                    #see if we left blot from where we moved
                                    if len(self._piece_locations[idx]) == 1:
                                        if blot_found is False:
                                            blot_found = True
                                            self.blot_list.append(tuple(new_moves))
                                            #keep track of all indices that will be left with a blot (set comprehension)
                                            #blot_indices is congruent with blot_list!!
                                            self.blot_indices.append({spot for spot in move_indices if len(self._piece_loc_copy[spot]) != 1 and len(self._piece_locations[spot]) == 1})
                                    #see if we moved an opponent piece to bar
                                    if len(self._piece_loc_copy[idx]) == 1 and self._piece_loc_copy[idx][0][1] == self._opponent:
                                        bar_pieces.add(idx)
                                        if bar_found is False:
                                            bar_found = True
                                            self.bar_list.append(tuple(new_moves))
                                            self.pipCount()
                                            self.opponent_pips.append(int(self.opp_pipcount))

                                if len(bar_pieces) > 0:
                                    self.bar_indices.append(bar_pieces)
                                #if no blots left behind, move will be considered safe
                                if blot_found is False:
                                    if safe_found is False:
                                        safe_found = True
                                        self.safe_moves.append(tuple(new_moves))
                                        self.safe_move_indices.append({idx for moveset in new_moves for idx in moveset})
                          
                        self._undo()
                            
                        if self.ex_count > 1 and count is False:
                            break
                        
            #explore our alternate options if we have any and restore state of our board back to that point
            if len(self.alt_move_lists) > 0:
                data = self.alt_move_lists.pop()
                #restore dice data to move we popped from list
                self.last_move = self._last_move[len(self._last_move)-1]
                for _ in self._last_move:
                    if self.countDice() == data:
                        break
                    self._undo()

        self.countCompletedMoves(move_list)
        doMoves(move_list,count=counting)
        #restore pieces back to original position
        for _ in range(0,len(self._last_move)):
            self._undo()

        for idx, move in enumerate(sorted(self.availableMoves)):
            print(idx, move, '\n')
        print(f'we have {self.ex_count} ways of using all of our dice')
        if counting is True:
            print('blot list: ', self.blot_list, '\n')
            print('blot_indices: ', self.blot_indices, '\n')
            print('unclog list: ', self.unclog_list, '\n')
            print('unclog indices: ', self.unclog_indices, '\n')
            print('clog list: ', self.clog_list, '\n')
            print('clog indices : ', self.clog_indices, '\n')
            print('bar list: ', self.bar_list, '\n')
            print('opponent_pips: ', self.opponent_pips, '\n')
            print('bar indices: ', self.bar_indices, '\n')
            print('safe moves: ', self.safe_moves, '\n')
            print('safe move indices: ', self.safe_move_indices, '\n')
        if back_on is True:
            self._animate = True

    def _forcedMoveDetection(self):
        #assume move is forced until proven otherwise
        self.isForcedMove = False
        #cannot use all of our dice, time to investigate why
        if self.ex_count == 0: 
            #if we can use either die but not both, must use larger die
            #will search through moves and if only one occurence of larger die found, then must perform that move
            if self.is_double is False and len(self.move_history) > 1:
                large_die_count = 0
                small_die_count = 0
                for moveset in self.move_history:
                    for move in moveset[:2]:
                        if max(move)-min(move) == self._dice_1:
                            large_die_count += 1
                        else:
                            small_die_count += 1
                #we only have one way of using our larger die, must do that move
                if large_die_count == 1:
                    self.isForcedMove = True
                    for moveset in self._last_move_copy:
                        for item in moveset:
                            move = (item[0], item[1])
                            if max(move)-min(move) == self._dice_1:
                                self.forced_moves.append(moveset)
                #there's only one die we can use, but we have choices where we can use that die, must set the other die to null in order for move to finish
                elif large_die_count > 1 and small_die_count == 0:
                    self._dice_2 = None
                elif large_die_count == 0 and small_die_count > 1:
                    self._dice_1 = None

            #if we can't use all dice (or none), must do the only move(s) available to us
            if ((len(self.move_history) == 1 and self.is_double is False) or len(self.move_history) == 0) or (len(self.move_history) < 4 and self.is_double is True):
                self.isForcedMove = True
                if len(self.move_history) != 0:
                    self.forced_moves.append(self._last_move_copy.pop())
                else:
                    self.forced_moves.append([])

        #if there is only one way to use all of our dice
        elif self.ex_count == 1:
            self.isForcedMove = True
            #find where we used all of our dice if there is more than one move in history, must do that move in this case
            if len(self.move_history) > 1:
                largest_set = self._last_move_copy[0]
                for moveset in self._last_move_copy[1:]:
                    if len(moveset) > len(largest_set):
                        largest_set = moveset
                self.forced_moves.append(largest_set)
            else:
                self.forced_moves.append(self._last_move_copy.pop())
        #if the only two ways to use our dice involve moving the same piece all the way, is only a forced move if both spots for first move choices are empty
        elif self.ex_count == 2:
            if self.is_double is False:
                print('can only use two dice on one piece, see if forced because no blots')
                if self.availableMoves[0][0][1] == self.availableMoves[0][1][0] and self.availableMoves[1][0][1] == self.availableMoves[1][1][0] and \
                self.availableMoves[0][1][1] == self.availableMoves[1][1][1]:
                    if len(self._piece_locations[self.availableMoves[0][0][1]]) == 0 and len(self._piece_locations[self.availableMoves[1][0][1]]) == 0:
                        self.isForcedMove = True
                        self.forced_moves.append(self._last_move_copy.pop())
        #no forced moves have been detected and have two or more complete options, clean up our available moves by removing incomplete moves (if any present)
        if self.ex_count >= 2 and self.isForcedMove is False:
            for moveset in self.availableMoves.copy():
                if self.is_double is False:
                    if len(moveset) < 2:
                        self.availableMoves.remove(moveset)
                else:
                    if len(moveset) < 4:
                        self.availableMoves.remove(moveset)
        if self.isForcedMove is True:
            print('forced move detected: ', self.forced_moves)
            #reset board's _last_move variable to forced moves so confirm can send the forced move to server
            self._last_move = self.forced_moves.pop()
            self.configure(state='disabled')
            #enable client's forced move button
            self.button_2.state(['!disabled'])
            #if no moves can be made, we will programmatically 'click' the forced move button
            if len(self._last_move) == 0:
                print('invoking button')
                self.button_2.invoke()


    #create copy of board from team or opponent perspective
    def createCopy(self, perspective):
        if type(perspective) is not str or (perspective != 'team' and perspective != 'opp'):
            raise ValueError(f'perspective arg must be team or opp(string), not {perspective}')

        board_copy = BackgammonBoard(self.root, self._colors, ttk.Button(self.root), ttk.Button(self.root), self.client_method, animate=False)
        if perspective == 'opp':
            board_copy.setUpGame('bl' if self._homeboard == 'br' else 'br', addPieces=False)
        else:
            board_copy.setUpGame('bl' if self._homeboard == 'bl' else 'br', addPieces=False)

        for i in range(0,27):
            for data in self._piece_locations[i]:
                board_copy._addPiece(i,data[1])
        
        if len(board_copy._piece_locations) != len(self._piece_locations):
            raise ValueError('copy board is corrupted')

        board_copy._dice_1, board_copy._dice_2, board_copy._dice_3, board_copy._dice_4 = \
            self._dice_1, self._dice_2, self._dice_3, self._dice_4

        return board_copy

         
    #add a piece(s) to the specified spot index
    #if pieceID is none, a new piece is created a placed at specified index. Otherwise the piece is moved 
    #if coordinates arg is True, _addPiece will just return coordinates of piece in spot at idx
    #put canvas ids representing the pieces and their color into _piece_locations variable 
    def _addPiece(self, idx, color, count=1, pieceID=None, coordinates=False):
        #pieceID will be None if new piece is being created for setting up game
        piece = pieceID
        #call helper functions for moving pieces to bar or trough
        if idx == 26 or idx == 27:
            drawCoords = self._moveToBar(color, piece, coordinates=coordinates)
        elif idx == 0 or idx == 25:
            drawCoords = self._moveToTrough(color, 'br' if idx == 0 else 'bl', pieceID=piece, coordinates=coordinates)
        else:
            #do not need to check for wrong color error when we are just getting coordinates for an animation
            if coordinates is False:
                #throw an Exception if color arg does not match color of pieces currently occupying that spot
                if len(self._piece_locations[idx]) > 0:
                    if self._piece_locations[idx][0][1] != color:
                        print('team who threw exception: ', self._team)
                        print('board data associated with exception: ', self._piece_locations)
                        raise PieceError(f'Cannot add wrong color piece to a spot: {color} to idx {idx}')
            coords = self._coords[idx-1]
            diameter = coords[2]-coords[0]
            for i in range(0,count):
                piece_count = len(self._piece_locations[idx])
                if piece_count >= 5:
                    #unhide and update label above spot if amount of pieces is 5 or more 
                    self.itemconfigure(f'window{idx-1}', state='normal')
                    self.labels[idx-1]['text'] = f'+{len(self._piece_locations[idx]) - 4}'
                    piece_count = 4
                #drawing coordinates depend on which side user's homeboard is on and how many pieces are located at that spot
                if self._homeboard == 'br':
                    drawCoords = (coords[0], coords[1]-(diameter*piece_count), coords[2], coords[3]-diameter-(diameter*piece_count)) if idx < 13 else \
                                    (coords[0], coords[1]+(diameter*piece_count), coords[2], coords[3]+diameter+(diameter*piece_count))
                elif self._homeboard == 'bl':
                    drawCoords = (coords[0], coords[1]-(diameter*piece_count), coords[2], coords[3]-diameter-(diameter*piece_count)) if idx >= 13 else \
                                    (coords[0], coords[1]+(diameter*piece_count), coords[2], coords[3]+diameter+(diameter*piece_count))
                
                #if coordinates argument is True, this method is being used to retrieve coordinates of spot piece will be added to
                if coordinates is True:
                    return drawCoords

                #a new piece will be added to spot if pieceID arg is None
                if pieceID is None:
                    #piece tags will be their color and piece+idx                 
                    piece = self.create_oval(*drawCoords, fill=color, outline='black', tags=(color, f'piece'))
                else:
                    self.coords(pieceID, *drawCoords)

                self._piece_locations[idx].append((piece, color)) 

        return drawCoords
    #remove piece(s) from the specified spot index
    #remove the pieces from self._piece_locations, delete from canvas if it is an item (not a label)
    #optional color arg to indciate which color piece to remove from the bar       
    def _removePiece(self, idx, color):
        #throw an Exception if spot has no pieces occupying it
        if len(self._piece_locations[idx]) == 0:
            print('team who threw exception, ', self._team)
            raise PieceError('No pieces located at this index:', idx)
        #retrieve piece ID before we remove it
        pieceRemoved = None
        #handling removing a piece from a spot, updating the label if the spot had 6 or more pieces
        if idx < 25 and idx > 0:
            pieceRemoved = self._piece_locations[idx].pop()[0]
            if len(self._piece_locations[idx]) > 5:
                self.labels[idx-1]['text'] = f'+{len(self._piece_locations[idx]) - 5}'
            if len(self._piece_locations[idx]) == 5:
                self.labels[idx-1]['text'] = ''
                #hide the label again when we do not need it
                self.itemconfigure(f'window{idx-1}', state='hidden')
            
        #removing a piece from the bar
        elif idx == 26 or idx == 27:
            #order of list is reversed in this loop, which traversed list by most recently placed pieces
            for piece, c in reversed(self._piece_locations[idx]):
                if color == c:
                    try:
                        pieceRemoved = piece
                        self._piece_locations[idx].remove((piece, c))
                        break
                    except Exception as ce:
                        print(type(ce))
                        print(self._piece_locations)
                        print(traceback.format_exc())
        #removing a piece from trough, delete rectangle and replace with oval
        elif idx == 25 or idx == 0:
            pieceRemoved = self._piece_locations[idx].pop()[0]
            
        #return piece we removed from board
        return pieceRemoved
    
    #move a piece to the bar (just one piece)
    #only one argument for color of piece to put on bar      
    def _moveToBar(self, color, pieceID=None, coordinates=False):
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
        #if coordinates argument is True, this method is being used to retrieve coordinates of spot piece will be added to
        if coordinates is True:
            return drawCoords

         #a new piece will be added to spot if pieceID arg is None
        if pieceID is None:
            #piece tags will be their color and piece+idx                 
            pieceID = self.create_oval(*drawCoords, fill=color, outline='black', tags=(color, f'piece'))
        self.coords(pieceID, *drawCoords)
        self._piece_locations[26].append((pieceID, color))
        return drawCoords
        
    #move a piece(s) to a trough
    #trough arg will signify which trough to place the piece into (br or bl) and color of piece must be supplied as arg
    def _moveToTrough(self, color, trough, pieceID=None, coordinates=False):
        if color == self._opponent and trough == self._homeboard:
            raise PieceError('cannot place wrong color piece into trough')
        
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
        #if coordinates argument is True, this method is being used to retrieve coordinates of spot piece will be added to
        if coordinates is True:
            return drawCoords

        if pieceID is None:
            pieceID = self.create_rectangle(*drawCoords, fill=color, outline='black', tags=(color, 'rect'+str(total_pieces), 'piece'))
            self._piece_locations[idx].append((pieceID, color))
            return drawCoords
        #replace our circular piece for rectangular shaped piece
        if self._animate is True:
            self.delete(pieceID)
            #draw the rectangle and update _piece_locations with our new rectangle object   
            pieceID = self.create_rectangle(*drawCoords, fill=color, outline='black', tags=(color, 'rect'+str(total_pieces), 'piece'))
        else:
            self.coords(pieceID, *drawCoords)
        self._piece_locations[idx].append((pieceID, color))
        return drawCoords
                
    #set up a fresh game, specifying where user's homeboard will be located on the board 
    #this method MUST be called on a board before pieces are added/moved/etc. 
    #subsequent arg should be True if it is NOT first game since application is launched  
    #addPieces being False won't set up initial pieces    
    def setUpGame(self, hblocation, subsequent=False, addPieces=True):
        teamcolor = self._colors[3]
        ocolor = self._colors[4]
        #save orientation of homeboard as an instance variable
        if hblocation != 'br' and hblocation != 'bl':
            raise ValueError('must specify homeboard location as br or bl')
        self._homeboard = hblocation
        self.oppHomeboard = 'bl' if hblocation == 'br' else 'br'
        self.hb_indices = (6,5,4,3,2,1) if hblocation == 'br' else (19,20,21,22,23,24)
        self.opp_hb_indices = (6,5,4,3,2,1) if hblocation == 'bl' else (19,20,21,22,23,24)
        self.homeTrough = 0 if hblocation == 'br' else 25
        self.prime_spots = (7,6,5,19,4,20,21,18) if hblocation == 'br' else (18,19,20,6,21,5,4,7)
        self.closeToHomeboard = (12,11,10,9,8,7) if hblocation == 'br' else (13,14,15,16,17,18)
        self.closeToOppHomeboard = (12,11,10,9,8,7) if hblocation == 'bl' else (13,14,15,16,17,18)
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
         
        #set up variables for highlighting our spots/pieces in the game
        self.actual_idx_1 = None
        self.actual_idx_2 = None
        self.actual_idx_3 = None
        self.actual_idx_4 = None
        self.actual_idx_5 = None
        
        #save location of doubling cube
        self.cube_location = 'mid'
        #save initial stakes of game (1)
        self.stakes = 1
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
        self._doubling_label = self.create_text(*textLocation, text='2', font=('TkDefaultFont','30','bold'), tags=('cube'))
        self.tag_bind('cube', '<1>', lambda e: self._wantsToDouble())
        
        if addPieces is True:
            #put pieces in starting spots for fresh game    
            self._addPiece(1, ocolor, 2)
            self._addPiece(6, teamcolor, 5)
            self._addPiece(8, teamcolor, 3)
            self._addPiece(12, ocolor, 5)
            self._addPiece(13, teamcolor, 5)
            self._addPiece(17, ocolor, 3)
            self._addPiece(19, ocolor, 5)
            self._addPiece(24, teamcolor, 2) 

        #every piece will be tagged with our _userClickSpot method
        self.tag_bind('piece', '<1>', self._userClickSpot)
        
    #redraw the doubling cube lower, higher, or middle on the board (depending on who owner of cube will be)
    #this method will be called by server if player accepts a doubling offer
    #only two valid args; 'team' or 'opp' which will draw cube lower or higher, respectively
    def redrawCube(self, location):
        if self.stakes == 64:
            return
        if location != 'team' and location != 'opp' and location != 'mid':
            raise ValueError('arg for location must be mid, team or opp')
        self.cube_location = location
        self.delete('cube')
        width = float(self['width'])
        height = float(self['height'])
        side = (1/18)*height
        trough = self._trough_distance
        if location == 'opp' or location =='team':
            self.stakes = int(self.stakes * 2)
            Y1 = 0 if location == 'opp' else height-side 
            Y2 = side if location == 'opp' else height
        else:
            self.stakes = 1
            Y1 = height/2+(side/2)
            Y2 = height/2-(side/2)
        drawCoords = (trough/2-(side/2), Y1, trough/2+(side/2), Y2) if self._homeboard == 'br' else \
        (width-(trough/2)-(side/2), Y1, width-(trough/2)+(side/2), Y2)
        self.create_rectangle(*drawCoords, fill='white', outline='black', tags=('cube'))
        #put text directly in middle of rectangle
        textLocation = (((drawCoords[0] + drawCoords[2])/2), ((drawCoords[1] + drawCoords[3])/2))
        self._doubling_label = self.create_text(*textLocation, text='2' if location == 'mid' else str(self.stakes), font=('TkDefaultFont','30','bold'), tags=('cube'))
        #only make the cube clickable if the cube is redrawn onto their side
        if location == 'team':
            self.tag_bind('cube', '<1>', lambda e: self._wantsToDouble())
            
    #reset state of board to a fresh game
    #will move every piece to it's rightful place for a fresh game using recursive restart function
    #move doubling cube back to middle of board
    def restartGame(self, end=False, animationSpeed=4.0):
        try:
            print('here at restartGame')
            self.confirm()
            self.redrawCube('mid')
            self.team_pipcount = '167'
            self.opp_pipcount = '167'
           #if other player left game, clear every piece and reset data for 'bl' setup to prevent corruption of data for fresh game
            if end is True:
                self.delete('piece')
                self.delete('cube')
                if self._homeboard == 'bl':
                    self._coords = [self._coords[i] for i in range(12, 24)] + [self._coords[i] for i in range(0, 12)]
                    self.labels = [self.labels[i] for i in range(12, 24)] + [self.labels[i] for i in range(0, 12)]
            else:
                #see how many pieces are in each of our starting spots
                #negative number means we need to remove pieces from spot
                def currentConditions(locations, color):
                    for idx, (spot, _) in enumerate(locations):
                        if len(self._piece_locations[spot]) > 0 and self._piece_locations[spot][0][1] == color:
                            locations[idx][1] = locations[idx][1] - len(self._piece_locations[spot])
                #our counters, a list of lists representing all spots to move to and how many pieces we still need to place there
                br_locations = [[6,5], [8,3], [13,5], [24,2]]
                bl_locations = [[19,5], [17,3], [12,5], [1,2]]
                teamPieces = br_locations if self._homeboard == 'br' else bl_locations
                oppPieces = bl_locations if self._homeboard == 'br' else br_locations
                currentConditions(teamPieces, self._team)
                currentConditions(oppPieces, self._opponent)
                def restart(start, homeboard, animSpeed=animationSpeed):
                    try:
                        #check that our location piece counters aren't all zero and target next data with positive, or nonzero counter
                        def nextData(locations, fr):
                            firstPositive = None
                            for idx, (spot, counter) in enumerate(locations):
                                    foundNegative = False
                                    if counter < 0:
                                        foundNegative = idx
                                        if spot == fr:
                                            return idx
                                    elif counter > 0:
                                        if firstPositive is None:
                                            firstPositive = idx

                            if firstPositive is None:
                                if foundNegative is not False:
                                    return foundNegative
                                return None
                            else:
                                return firstPositive

                        teamPieceLoc = teamPieces if self._homeboard == homeboard else oppPieces
                        #start by emptying our trough and putting our pieces on board starting with homeboard
                        #if we run into enemy piece(s) on a spot, move them to their correct places starting with their homeboard
                        teamIndices = (tuple(spot for spot, _ in teamPieceLoc))
                        for i in range(start,28) if self._homeboard == 'br' else range(start,-1,-1):
                            fromSpotLen = len(self._piece_locations[i])
                            while(fromSpotLen > 0):
                                data = nextData(teamPieceLoc, i)
                                #if spot to move from is not empty and has enemy pieces occupying it
                                if (len(self._piece_locations[i]) > 0 and self._piece_locations[i][-1][1] == self._opponent):
                                    self._team, self._opponent = self._opponent, self._team
                                    restart(i, 'br' if homeboard == 'bl' else 'bl')
                                    self._team, self._opponent = self._opponent, self._team
                                    return
                                #if spot to move to is not empty and has enemy pieces occupying it
                                elif data is not None and (len(self._piece_locations[teamPieceLoc[data][0]]) > 0 and self._piece_locations[teamPieceLoc[data][0]][0][1] == self._opponent):
                                    self._team, self._opponent = self._opponent, self._team
                                    restart(teamPieceLoc[data][0], 'br' if homeboard == 'bl' else 'bl')
                                    self._team, self._opponent = self._opponent, self._team
                                elif data is None:
                                    break
                                #if the spot to move from is same spot to move to, and too many of our pieces are currently occupying it
                                #move extras to other spots that need pieces
                                elif teamPieceLoc[data][0] == i and teamPieceLoc[data][1] < 0:
                                    fromSpotLen = int(teamPieceLoc[data][1] * -1)
                                    teamPieceLoc[data][1] = 0
                                    for _ in range(0, fromSpotLen):
                                        for idx, (_,count) in enumerate(teamPieceLoc):
                                            if count > 0:
                                                data = idx
                                                break
                                        if len(self._piece_locations[teamPieceLoc[data][0]]) > 0 and self._piece_locations[teamPieceLoc[data][0]][0][1] == self._opponent:
                                            self._team, self._opponent = self._opponent, self._team
                                            restart(teamPieceLoc[data][0], 'br' if homeboard == 'bl' else 'bl')
                                            self._team, self._opponent = self._opponent, self._team
                                        if self._animate is True:
                                            self.movePiece(i, teamPieceLoc[data][0], col=self._team, animationSpeed=animSpeed).start()
                                            result = self.synchQueue.get()
                                            if isinstance(result, Exception):
                                                print('caught in restartGame')
                                                print(traceback.format_exc())
                                                raise result
                                        else:
                                            self.movePiece(i, teamPieceLoc[data][0], col=self._team, animationSpeed=animSpeed)
                                        teamPieceLoc[data][1] -= 1
                                        fromSpotLen -= 1
                                        if fromSpotLen == 0:
                                            break
                       
                                #if too many of our pieces are currently occupying spot to move to 
                                #continue and wait until we deal with the extras (see suite above)
                                elif teamPieceLoc[data][1] < 0:
                                    break
                        
                                #if spot to move to is empty or occupied by less than required amount of our pieces and we move from a non critical spot
                                elif i not in teamIndices and teamPieceLoc[data][1] > 0:
                                    for _ in range(0, teamPieceLoc[data][1]):
                                        for idx, (_,count) in enumerate(teamPieceLoc[data:], data):
                                            if count > 0:
                                                data = idx
                                                break
                                        if self._animate is True:
                                            self.movePiece(i, teamPieceLoc[data][0], col=self._team, animationSpeed=animSpeed).start()
                                            result = self.synchQueue.get()
                                            if isinstance(result, Exception):
                                                print('caught in restartGame')
                                                print(traceback.format_exc())
                                                raise result
                                        else:
                                            self.movePiece(i, teamPieceLoc[data][0], col=self._team, animationSpeed=animSpeed)
                                        teamPieceLoc[data][1] -= 1
                                        fromSpotLen -= 1
                                        if fromSpotLen == 0:
                                            break
                                else:
                                    break
                                
                    except Exception as ex:
                        print('caught ', type(ex), 'in restart')
                        raise
            
                #this function will use the 'extra' spot in our piece locations list to seperate team and opponent pieces on bar, for convenience purposes
                for piece, col in deepcopy(self._piece_locations[26]):
                    if col == self._team:
                        self._piece_locations[26].remove((piece, col))
                        self._piece_locations[27].append((piece, col))

                restart(0 if self._homeboard == 'br' else 27, 'br' if self._homeboard == 'br' else 'bl')
            print('end of restartGame')
        #something went wrong, print traceback and just reset pieces manually, keeps the game playable
        except Exception as ce:
            print(type(ce))
            print(traceback.format_exc())
            print('reseting pieces manually')
            self.restartGame(end=True)
            self.setUpGame(self._homeboard)

    #move a piece(s) from one spot to another
    #all methods used inside this method adjusts _piece_locations
    #optional color arg to indicate which color to remove from the bar 
    #will throw a PieceError if moving to invalid spot
    #barPieces represents pieces moved to bar during this move, stored in cache so it can potentially be undone
    def movePiece(self, f, t, count=1, col=None, dice=None, barPieces=None, highlight=False, barAnalysis=True, animationSpeed=1.0):
        def doMove(fr=f, to=t, c=col, cou=count, d=dice, bar=barPieces, high=highlight, barAna=barAnalysis, animSpeed=animationSpeed, exQueue=self.synchQueue):
            try:
                #move piece from one index to another(f to t)
                #will call _addPiece for mutation of piece data and final drawing of stationary piece object
                for i in range(0,cou):
                    #unhighlight all pieces/spots before a piece is moved
                    if d is not None:
                        self._clearSpots() 
                    if self._animate is True:
                        self._animateMove(fr,to,c,animSpeed)
                    #move to a regular spot (not a trough or bar)
                    if to > 0 and to < 25:
                        #if one opponent piece on destination spot, move enemy piece to bar 
                        if len(self._piece_locations[to]) == 1 and self._piece_locations[to][0][1] != c and barAna is True:
                            doMove(fr=t, to=26, c=self._opponent if c == self._team else self._team, cou=count, d=False, bar=None, barAna=False)
                            #put spot in bar list so undo() can potentially reverse putting piece on bar
                            if bar is None:
                                bar = []
                                bar.append(to)
                            else:
                                if to not in bar:
                                    bar.append(to)
                    #change our piece location state to reflect our move and snap piece into it's place
                    self._addPiece(to, c, pieceID=self._removePiece(fr, c))
                    #move intermediate pieces to bar(if user uses multiple dice in one move and is forced to put enemy pieces on bar along the way)
                    if bar is not None:
                        for idx in bar:
                            #send intermediate pieces to bar if not null and not on spot we're landing, since we've already moved that piece to the bar
                            if idx != -1 and idx != to:
                                print('doing intermediate bar move: ', idx, 26)
                                doMove(fr=idx, to=26, c=self._opponent if c == self._team else self._team, cou=count, d=False, bar=None, barAna=False)
                
                    #if d is None, movePiece is being called to perform opponent's move on client's board object
                    if d is None: 
                        exQueue.put(None)
                        #if d is None, do not execute rest of method, which will not put the move we just performed into cache
                        continue
                    #if d is False, is a recursive call for moving opponent pieces to the bar
                    elif d is False:
                        continue  
                    #when dice arg is not none, move is saved in cache for _undo() to use 
                    else:
                        self._last_move.append((to, fr, self.getDice(), bar))
                
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
                            if self._dice_4 is not None:
                                self._dice_4 = None
                            elif self._dice_3 is not None:
                                self._dice_3 = None
                            else:
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

            
                if high is True:
                    self._highlightSpot(fr, self._countBarPieces(count='team'))
            
                #make player's Confirm button clickable if all dice are null and player just moved
                if self._dice_1 is None and self._dice_2 is None and self._dice_3 is None and self._dice_4 is None and len(self._last_move) > 0:
                    self._confirm()

                self.configure(state='normal')

            except Exception as ce:
                print('caught in doMove')
                print(type(ce))
                if self._animate is False:
                    print(traceback.format_exc())
                exQueue.put(ce)
           
        #launch animation thread if _animate is True
        if col is None:
            col = self._piece_locations[f][0][1]
        if self._animate is True:
            self.configure(state='disabled')
            drawThread = threading.Thread(target=lambda:doMove(c=col), daemon=True)
            return drawThread
        else:
            doMove(c=col)

    #set our pipcount variables
    def pipCount(self):
        self.team_pipcount, self.opp_pipcount = self._pipCount()

    #return True if game is over        
    def isGameOver(self):
        if len(self._piece_locations[0]) == NUMBER_OF_PIECES or len(self._piece_locations[25]) == NUMBER_OF_PIECES:
            return True
        else:
            return False

        
    #check to see if a player has been gammoned or backgammoned
    #will return 1, 2, or 3 if no gammon, gammon, or backgammon, respectively (multiplier value)
    def isGammon(self):
        br_trough = len(self._piece_locations[0]) 
        bl_trough = len(self._piece_locations[25])
        #should not factor in a gammon calculation if game ends as the result of a doubling proposal
        if br_trough != NUMBER_OF_PIECES and bl_trough != NUMBER_OF_PIECES:
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
    def isRacing(self):
        #race is not on if any pieces are on the bar
        if len(self._piece_locations[26]) > 0:
            return False
        #keep track of pieces we still have behind enemy lines
        self.piecesBehind = 0
        self.behindSpots = []
        oppPieces = 0
        #count our pieces as pieces behind enemy lines if we have not accounted for all of enemy pieces
        for i in range(25,0,-1) if self._homeboard == 'br' else range(0,25):
            if len(self._piece_locations[i]) > 0 and self._piece_locations[i][0][1] == self._opponent:
                oppPieces += len(self._piece_locations[i])
            elif len(self._piece_locations[i]) > 0 and self._piece_locations[i][0][1] == self._team:
                if oppPieces < NUMBER_OF_PIECES:
                    self.piecesBehind += len(self._piece_locations[i])
                    self.behindSpots.append(i)
        
        #True or False for racing and pieces behind enemy lines
        if self.piecesBehind > 0:
            return False
        else:
            return True
    #just get pieces in and bear off as fast as possible with a board parameter, most likely a copy of our current board in canWin algorithm
    def _racingLogic(self, board):
        #will 'slice' our _piece_locations dictionary to get just our homeboard data (spot and how many pieces occupying it)
        hb_slice = {spot:len(board._piece_locations[spot]) for spot in board.hb_indices}
        #will create a new move history that will be sorted by how many pieces we can bear off, get into homeboard, or move internally
        new_move_history = []
        totalBearOff = 0
        totalInHomeboard = 0
        print('available moves in RacingStrategy: ', board.availableMoves)
        for moveset in board.availableMoves:
            #within each moveset, we will count how many moves get a piece into homeboard, and how many moves are moving pieces within homeboard
            beared_off = 0
            pieces_in = 0
            internals = 0
            for fr, to in moveset:
                if fr not in hb_slice and to in hb_slice:
                    pieces_in += 1
                elif fr in hb_slice and to in hb_slice:
                    internals += 1
                elif to == 25 or to == 0:
                    beared_off += 1
                
            totalBearOff += beared_off
            totalInHomeboard += pieces_in
            new_move_history.append((moveset, beared_off, pieces_in, internals))

        #perform multisort on our new_move_history, based on how many pieces we can bear off, get into homeboard, and move internally
        new_move_history.sort(key=lambda x:(x[1], x[2], -x[3]), reverse=True)
        #return move that bears off maximum amount of pieces and gets most pieces in
        return new_move_history[0][0]
    #return if it's still possible to win (True or False)
    #client object MUST call isRacing() before calling this for logic to make sense
    def canWin(self):
        print('doing canWin')
        #don't assume we can't win unless the opponent and us have all our pieces in homeboard first, could be a gammon or backgammon situation
        if self.countHomeboardPieces(self._homeboard, self._team) < NUMBER_OF_PIECES or \
            self.countHomeboardPieces(self.oppHomeboard, self._opponent) < NUMBER_OF_PIECES:
            return True
        try:
            teamCopy = self.createCopy('team')
            oppCopy = self.createCopy('opp')
            loopCount = 0
            #give our team board copy double 6's and opp copy acey deucy repeatedly, if we can still win, will return True, otherwise False
            while(True):
                loopCount += 1
                if loopCount == 30:
                    raise Exception
                teamCopy.setDice(6,6)
                teamCopy._analyzeMoves(teamCopy._countBarPieces('team'), True)
                teamCopy._forcedMoveDetection()
                oppCopy.setDice(1,2)
                oppCopy._analyzeMoves(oppCopy._countBarPieces('team'), True)
                oppCopy._forcedMoveDetection()
                if teamCopy.isForcedMove is True:
                    for num, move in enumerate(teamCopy._last_move):
                        teamCopy.movePiece(move[1], move[0], 1, col=teamCopy._team)
                else:
                    for move in teamCopy._racingLogic(teamCopy):
                        teamCopy.movePiece(*move, col=teamCopy._team)
                if len(teamCopy._piece_locations[teamCopy.homeTrough]) == NUMBER_OF_PIECES:
                    return True
                if oppCopy.isForcedMove is True:
                    for num, move in enumerate(oppCopy._last_move):
                        oppCopy.movePiece(move[1], move[0], 1, col=oppCopy._team)
                else:
                    for move in oppCopy._racingLogic(oppCopy):
                        oppCopy.movePiece(*move, col=oppCopy._team)
                if len(oppCopy._piece_locations[oppCopy.homeTrough]) == NUMBER_OF_PIECES:
                    return False

                teamCopy.confirm()
                oppCopy.confirm()
        except Exception as ce:
            print('caught', type(ce), 'error in canWin')
            print(traceback.format_exc())
            raise
        print('end of canWin')
    #set dice to every possible number and if every iteration results in no detected moves, then no point in player being able to roll
    def canRoll(self):
        all_rolls = ((1,2), (3,4), (5,6))
        can_roll = False
        self._dice_3, self._dice_4 = None, None
        for d1, d2 in all_rolls:
            self._dice_1, self._dice_2 = d1, d2
            for _ , moves in self.countMoves(self._countBarPieces(count='team')):
                if moves != (None, None, None, None, None):
                    can_roll = True
                    break
            if can_roll is True:
                break
        self._dice_1, self._dice_2 = None, None  
        print('canRoll:', can_roll)   
        return can_roll 
    
    #animate a piece going from one index to another
    #moves the actual piece object itself, does not delete and recreate piece for every frame
    def _animateMove(self, f, t, pc, speed):
        try:
            if f != 26:
                print(self._piece_locations[f])
                print(f)
                piece = self._piece_locations[f][-1][0]
            #when animating a piece from the bar, will get the pieceID of most recently placed of specified color
            else:
                for p, c in reversed(self._piece_locations[f]):
                    if pc == c:
                            piece = p
                            break
            #if moving from trough, replace rectangular piece with circular one
            if f == 25 or f == 0:
                oldPiece = self._piece_locations[f].pop()[0]
                piece = self.create_oval(*self.coords(oldPiece), fill=pc, outline='black', tags=(pc, f'piece'))
                self._piece_locations[f].append((piece, pc))
                self.delete(oldPiece)
            #find start and ending coordinates of our piece, which is the path (lines) piece will take in the animation           
            start_coords = self.coords(piece)
            end_coords = self._addPiece(t, pc, coordinates=True)
            #put our start and end oval coordinates into local variables for our animate function to use
            l1_x1, l1_y1, l2_x1, l2_y1 = start_coords
            l1_x2, l1_y2, l2_x2, l2_y2 = end_coords
            #calculate distance of our two lines
            distance1 = math.sqrt((l1_x2 - l1_x1)**2 + (l1_y2 - l1_y1)**2)
            distance2 = math.sqrt((l2_x2 - l2_x1)**2 + (l2_y2 - l2_y1)**2)
            avgDistance = (distance1 + distance2) / 2
            traversedDist = 0
            #recursive function for animation
            def animate(traversed_dist, last_frame):
                current_frame = time()
                delta_time = current_frame - last_frame
                last_frame = current_frame
                l1_new_x = l1_x1 - ((traversed_dist*(l1_x1-l1_x2))/avgDistance)
                l1_new_y = l1_y1 - ((traversed_dist*(l1_y1-l1_y2))/avgDistance)
                l2_new_x = l2_x1 - ((traversed_dist*(l2_x1-l2_x2))/avgDistance)
                l2_new_y = l2_y1 - ((traversed_dist*(l2_y1-l2_y2))/avgDistance)
                self.coords(piece, l1_new_x, l1_new_y, l2_new_x, l2_new_y)
                traversed_dist += ((400*speed)*delta_time)
                if traversed_dist < avgDistance:
                    self.after(40, animate, traversed_dist, last_frame)
                else:
                    with self.animation_lock:
                        self.animation_lock.notify()
                
            lastFrame = time()
            self.after(40, animate, traversedDist, lastFrame)
            with self.animation_lock:
                self.animation_lock.wait()
        
        except Exception as ce:
            print(type(ce))
            print(traceback.format_exc())
            raise
    
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
    def _undo(self, barUndo='opp'):
        def undo(bar=barUndo):
            self.unbind('<3>')
            self._clearSpots()
            self.button.state(['disabled'])
            if len(self._last_move) > 0:
                prev = self._last_move.pop()
                #restore dice data back to previous state
                self._dice_1, self._dice_2, self._dice_3, self._dice_4 = prev[2]
                #move last piece moved back to it's original place
                if self._animate is True:
                    dt = self.movePiece(*prev[0:2]).start()
                    self.synchQueue.get()
                else:
                    self.movePiece(*prev[0:2])
                #move any opponent pieces that were taken to the bar back to their original places
                if prev[3] is not None:
                    for idx in prev[3]:
                        if idx != -1:
                            if self._animate is True:
                                dt = self.movePiece(26,idx,col=self._opponent if bar == 'opp' else self._team, barAnalysis=False).start()
                                self.synchQueue.get()
                            else:
                                self.movePiece(26,idx,col=self._opponent if bar == 'opp' else self._team, barAnalysis=False)

            self.bind('<3>', lambda e: self._undo())
    
        if self._animate is True:
            undoThread = threading.Thread(target=undo, daemon=True)
            undoThread.start()
        else:
            undo()
        
    #when all dice are null, board will call this to enable client's Confirm button
    def _confirm(self):
        self.button.state(['!disabled'])
    
    #client will use this method to refresh board to fresh state after player has performed their move (player clicks the confirm button)  
    def confirm(self):
        self._last_move.clear()
        self._last_move_copy.clear()
        self.move_history.clear()
        self.availableMoves.clear()
        self.forced_moves.clear()
        self.alt_move_lists.clear()
        self.synchQueue = Queue()
        self.pipCount()

#testing grounds
if __name__ == '__main__':                  
                   
    root = Tk()
    
    w = Toplevel(root)
    mock_button = ttk.Button(root, text="mock")
    mb2 = ttk.Button(root, text='mock')
    mock_meth = lambda *args: print('mock method')
    canvas = BackgammonBoard(root, ('forest green', 'blue', 'red', 'pink', 'purple', 'black', 'black'), mock_button, mb2, mock_meth)
    canvas2= BackgammonBoard(w, ('gray75', 'blue', 'red', 'pink', 'purple', 'black', 'black'), mock_button, mb2, mock_meth)
    canvas.grid(column=0, row=0, sticky=(N,E,S,W))
    canvas2.grid(column=0, row=0, sticky=(N,E,S,W))
    canvas.setUpGame('br')
    canvas2.setUpGame('bl')
    canvas._animate = False
    
    canvas.movePiece(24,5,2)
    canvas.movePiece(13,4,5)
    canvas.movePiece(8,3,3)
    canvas.movePiece(1,20,2)
    canvas.movePiece(12,21,5)
    canvas.movePiece(17,22,3)
    
    canvas._animate = True

    canvas.setDice(5,1)
    print('canvas bar data1: ', canvas._piece_locations[26])
    canvas.analyzeMoves(True)
    print('canvas bar data2: ', canvas._piece_locations[26])

    canvas.configure(state='normal')
    
    canvas2._animate = False

    canvas2.movePiece(24,5,2)
    canvas2.movePiece(13,4,5)
    canvas2.movePiece(8,3,3)
    canvas2.movePiece(1,20,2)
    canvas2.movePiece(12,21,5)
    canvas2.movePiece(17,22,3)
    
    canvas2._animate = True
    canvas2.setDice(4,5)

    print('canvas isRacing:', canvas.isRacing())
    print('canvas canWin:', canvas.canWin())
    print('canvas2 isRacing:', canvas2.isRacing())
    print('canvas2 canWin:', canvas2.canWin())
    #canvas2.analyzeMoves(True)
    #print('canvas2 bar data: ', canvas2._piece_locations[26])
    #board_copy2 = canvas2.createCopy('team')
    #print('board copy bar data: ', board_copy2._piece_locations[26])
    #restart_thread1 = threading.Thread(target=lambda:canvas.restartGame(animationSpeed=3.0), daemon=True)
    #restart_thread2 = threading.Thread(target=canvas2.restartGame, daemon=True)
    #root.after(1000, restart_thread1.start())
    #w.after(1000, restart_thread2.start())
    root.mainloop()
