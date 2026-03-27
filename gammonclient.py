from tkinter import *
from tkinter import ttk
from tkinter import messagebox, font
from gammongame import Dice, BackgammonBoard, DiceSet
from gammonAI import ComputerPlayer
from random import randint
from socket import socket, AF_INET, SOCK_STREAM
import threading
import sys
import traceback
import time

root = Tk()
#will hide our root window, no widgets will actually be gridded to it, TopLevel windows will be gridded only
root.attributes('-alpha', 0.0)

#create global styles here 
background_color = 'steel blue'  
s = ttk.Style()
summaryFont = font.Font(family='Helvetica', name='summaryTextFont', size=14, weight='bold')
pipFont = font.Font(family='Helvetica', name='pipTextFont', size=13, weight='bold', underline=1)
welcomeFont = font.Font(family='Helvetica', name='welcomeFont', size=38, weight='bold')
s.configure('Name.TLabel', font=('TkDefaultFont', 25), background=background_color)
s.configure('BigName.TLabel', font=('TkDefaultFont', 40), background=background_color)
s.configure('Pip.TLabel', font=pipFont, background=background_color)
s.configure('Number.TLabel', font=summaryFont, background=background_color)
s.configure('Welcome.TLabel', font=welcomeFont, background=background_color)
s.configure('Background.TFrame', background=background_color)
#empty space styles to place between widgets
s.configure('BigSpace.TLabel', font=('TkDefaultFont', 25), background=background_color)
s.configure('SmallSpace.TLabel', font=('TkDefaultFont', 6), background=background_color)
s.configure('Confirm.TButton', font=summaryFont)
#configure state-specific stylizing here
s.map('Confirm.TButton', \
      foreground=[('disabled', 'gray70'), ('active', 'forest green'), ('!disabled', 'black')], \
      background=[('disabled', 'gray70'), ('active', 'gold2'), ('!disabled', 'red')])


def mainMenu():
    #put main menu here, which will compose our sock variable with a ComputerPlayer or socket object through button callback composeSocket()
    main_prompt = Toplevel(root, background=background_color)
    mock_button = ttk.Button(root)
    mock_method = lambda: print('mock method')
    AI_board = BackgammonBoard(root, ('forest green', 'blue', 'red', 'goldenrod', 'gray54', 'black', 'black'), mock_button, mock_button, mock_method, animate=False)
    #set up socket connection with server OR create ComputerPlayer with same interface as a socket
    def composeSocket(type):
        global sock
        if type == 'Computer':
            print('composing a computer')
            AI_board.setUpGame('bl')
            sock = ComputerPlayer('bl', AI_board)
        else:
            print('composing a socket')
            sock = socket(AF_INET, SOCK_STREAM)
        
        #destroy main menu after socket has been composed   
        main_prompt.grab_release()
        main_prompt.destroy()

    stop_event = threading.Event()
    #entire application is done if user closes the main menu  
    def closeMainMenu(event):
        print('at closeMainMenu')
        root.destroy()
        event.set()
    
    board_frame = ttk.Frame(main_prompt)
    b_frame = ttk.Frame(main_prompt, style='Background.TFrame', padding=(20,20,20,20))
    dice_frame = ttk.Frame(main_prompt, style='Background.TFrame', padding=(10,10,10,10))
    #grid our frames
    board_frame.grid(column=0, row=1, columnspan=3, sticky=(N,S,E,W))
    b_frame.grid(column=3, row=1, sticky=(N,S))
    dice_frame.grid(column=3, row=0, sticky=(N,S,E,W), padx=20)
    #grid welcome widgets
    ttk.Label(main_prompt, text="Welcome to Devin's Backgammon Game!", style='Welcome.TLabel').grid(column=0, row=0, columnspan=3, padx=20, sticky=(N,S,E,W))
    #grid decoration board
    dec_board = BackgammonBoard(board_frame, ('forest green', 'blue', 'red', 'goldenrod', 'gray54', 'black', 'black'), mock_button, mock_button, mock_method, animate=True)
    dec_board.grid(column=0, row=0, sticky=(N,S,E,W))
    #'br' if randint(1,2) == 1 else 'bl'
    dec_board.setUpGame('br')
    dec_board.configure(state='disabled')
    #grid button frame widgets
    ttk.Label(b_frame, text='  ', style='SmallSpace.TLabel').grid(column=0, row=0)
    ttk.Label(b_frame, text='Play', style='BigName.TLabel').grid(column=0, row=2)
    ttk.Label(b_frame, text='   ', style='BigSpace.TLabel').grid(column=0, row=3)
    ttk.Label(b_frame, text='VS', style='BigName.TLabel').grid(column=0, row=5)
    ttk.Label(b_frame, text='  ', style='BigSpace.TLabel').grid(column=0, row=6)
    ttk.Button(b_frame, text='Computer', command=lambda *args:composeSocket('Computer'), style='Confirm.TButton').grid(column=0, row=8)
    ttk.Label(b_frame, text='   ', style='SmallSpace.TLabel').grid(column=0, row=9)
    ttk.Label(b_frame, text='OR', style='Name.TLabel').grid(column=0, row=11)
    ttk.Label(b_frame, text='   ', style='SmallSpace.TLabel').grid(column=0, row=12)
    ttk.Button(b_frame, text='Human', command=lambda *args:composeSocket('Human'), style='Confirm.TButton', state=DISABLED).grid(column=0, row=14)
    #grid our decoration dice
    d1 = Dice(dice_frame)
    d1['height'] = 40
    d1['width'] = 40
    d1.dot_size = 2
    d1.drawDie(3)
    d1.die_value = 3
    d2 = Dice(dice_frame)
    d2['height'] = 40
    d2['width'] = 40
    d2.dot_size = 2.5
    d2.drawDie(2)
    d2.die_value = 2
    d1.grid(column=0, row=0)
    ttk.Label(dice_frame, text='  ', style='SmallSpace.TLabel').grid(column=1, row=1)
    d2.grid(column=2, row=2)
    dec_board.setDice(d1.get(), d2.get())
    dec_board.analyzeMoves(True)
    main_prompt.protocol('WM_DELETE_WINDOW', lambda: closeMainMenu(stop_event))
    main_prompt.transient(root) 
    #blocking code until user submits their answer, then we will create a GameWindow
    main_prompt.grab_set()
    main_prompt.wait_window()
    if stop_event.is_set() is not True:
        createGameWindow()
    else:
        print('exiting application')
        sys.exit(0)

#create game window and listener that will guide the game with a computer or person over a server connection
def createGameWindow():
    #create all of our 'listening' variables, will display all of these variables in the UI
    username = StringVar()
    user_score = StringVar()
    opponentname = StringVar()
    opponent_score = StringVar()
    team_pips = StringVar()
    opp_pips = StringVar()
    #will set username listener variable to client's name and destroy modal prompt asking for player's username
    def dismissWindow(*args):
        user_n = name.get()
        if len(user_n) < 2 or len(user_n) > 9 or user_n[0].isalpha() is False:
            name.delete(0, 'end')
            name.focus_set()
            return
        username.set(user_n)
        name_prompt.grab_release()
        name_prompt.destroy() 
        
    #create the modal window that will prompt client for their name as soon as event loop starts
    name_prompt = Toplevel(root)
    name = ttk.Entry(name_prompt)
    name.focus_set()
    ttk.Label(name_prompt, text='Please type your name.', font=('TkDefaultFont', 25)).grid(column=0, row=0, columnspan=3, sticky=(W,E))
    name.grid(column=0, row=2, sticky=(E))
    ttk.Label(name_prompt, text='     ', font=('TkDefaultFont', 25)).grid(column=0, row=3)
    enter_button = ttk.Button(name_prompt, text='Enter', command=dismissWindow)
    enter_button.grid(column=2, row=2)
    name_prompt.protocol('WM_DELETE_WINDOW', dismissWindow)
    name_prompt.transient(root) 
    #blocking code until user submits their name
    name_prompt.wait_visibility()
    name_prompt.grab_set()
    name_prompt.wait_window() 

    #define all callbacks for buttons as inner functions here

    #this callback will fire as a result of user clicking the roll button, will draw dice on user screen
    #is passed our Dice objects, and we call Dice's roll method to fire animation and set the dice values
    #optional arg signifies if it is first roll of game
    def drawDice(dice, firstRoll=False):
        roll_button.state(['disabled'])
        def roll(dice, first_roll=firstRoll):
            roll_button.state(['disabled'])
            if first_roll is False:
                dice.rollDice()
                r1, r2 = dice.getDice()
                board.setDice(r1, r2)
                sock.sendall(bytes(f'{r1},{r2}', 'ascii'))
                #detirmine if move is forced after we roll
                board.analyzeMoves(False)
                if board.isForcedMove is True:
                    summarytext.insert('end', '\nThis is a forced move.')
                else:
                    if r1 != r2:
                        summarytext.insert('end', f'\nYou rolled a {r1} and {r2}.')
                    else:
                        summarytext.insert('end', f"\nYou rolled double {r1}'s.")

                print('value of dice:', dice.getDice())
                summarytext.see('end')
            #if first_roll is True, then we will only display one die
            else:
                dice._d1.rollDie()
                print('the first die:', dice._d1.get())
                sock.sendall(bytes(f'{dice._d1.get()}', 'ascii'))
                #sock.sendall(bytes(username.get(), 'ascii'))
                roll_button['command'] = lambda *args:drawDice(dice)
       
        dice_thread = threading.Thread(target=roll, args=(dice,), daemon=True)
        dice_thread.start()


    #will send user's move to server after client presses Confirm button
    def confirm(*args):
        confirm_button.state(['disabled'])
        board.configure(state='disabled')
        print('our move:', board._last_move)
        #pack last move to a form we can send to the server
        move_st = ''
        for c, ml in enumerate(board._last_move):
            t, f, d, bp = ml
            move_st += f'{f},{t}'
            if bp is not None:
                for i in bp:
                    if i != -1:
                        move_st += f',{i}' 
        
            if c != len(board._last_move) - 1:      
                move_st += ':'
            
        #refresh board back to fresh state
        board.confirm()
        if len(move_st) > 0:
            sock.sendall(bytes(move_st, 'ascii'))
        #if no moves were made (in case of no possible moves, which is a forced move) then just send one number
        else:
            sock.sendall(b'5')
        
        #board.pipCount()
        team_pips.set(board.team_pipcount)
        opp_pips.set(board.opp_pipcount)
        summarytext.insert('end', f'\nIt is now {opponentname.get()}\'s turn.')
        summarytext.see('end')

   #create condition to make
   #callback for forced move button
    def doForcedMove(*args):
        def performForcedMove():
            forced_button.state(['disabled'])
            print('performing forced moves:', board._last_move)
            for num, move in enumerate(board._last_move):
                board.movePiece(move[1], move[0], 1, col=board._team).start()
                board.synchQueue.get()
            #wait for moves to be completed
            if len(board._last_move) == 0:
                summarytext.insert('end', '\nYou cannot move at this time.')
                summarytext.see('end')

            confirm()

        forced_thread = threading.Thread(target=performForcedMove, daemon=True)
        forced_thread.start()

    #this method is called when client closes their game window    
    def closeGameWindow(*args):
        sock.close()
        GameWindow.destroy()
        mainMenu()
    
    
    #board will call this method when player doubles the other player, is passed to board during instantiation
    def doubling():
        answer = messagebox.askyesno(message='Are you sure you wish to double your opponent?', icon='question', title='Confirm')
        if answer is True:
            summarytext.insert('end', f'\n{opponentname.get()} is contemplating the doubling proposal.')
            #will reverse turn state here until doubling has been settled
            board.configure(state='disabled')
            roll_button.state(['disabled'])
            sock.sendall(b'double')

    #bring up modal window asking player if they wish to accept doubling from opponent
    #pressing button will send result to server   
    def doublePrompt():
        double_prompt = Toplevel(root)
        def dismissDouble(answer):
            sock.sendall(answer)
            double_prompt.grab_release()
            double_prompt.destroy()
        
        yes_button = ttk.Button(double_prompt, text='Yes', command=lambda *args: dismissDouble(b'N'))
        no_button = ttk.Button(double_prompt, text='No', command=lambda *args: dismissDouble(b'Y'))
        ttk.Label(double_prompt, text=f'{opponentname.get()} has proposed a doubling of the stakes.', font=('TkDefaultFont', 25)).grid(column=0, row=0, columnspan=3, sticky=(W,E))
        ttk.Label(double_prompt, text='Do you accept?', font=('TkDefaultFont', 40)).grid(column=0, row=1)
        yes_button.grid(column=0, row=2, sticky=(E))
        ttk.Label(double_prompt, text='     ', font=('TkDefaultFont', 25)).grid(column=0, row=3)
        no_button.grid(column=2, row=2)
        double_prompt.protocol('WM_DELETE_WINDOW', lambda *args: print('cannot exit modal prompt'))
        double_prompt.transient(root) 
        #blocking code until user submits their answer
        double_prompt.grab_set()
        double_prompt.wait_window() 
    
    #after the points threshold has been reached, server will ask us if we would like a rematch
    def rematchPrompt():
        answer = messagebox.askyesno(message='Would you like a rematch?', icon='question', title='Rematch')
        sock.sendall(b'Y') if answer is True else sock.sendall(b'N')

    #create GameWindow consisting of board, players' names and scores, pipcounts, and messagebox
    GameWindow = Toplevel(root)
    GameWindow.resizable(False, False)  
    label_frame = ttk.Frame(GameWindow, style='Background.TFrame')
    #create board and couple with our confirm and forced move buttons, along with our doubling method 
    confirm_button = ttk.Button(label_frame, text='Confirm', command=confirm, style='Confirm.TButton')
    forced_button = ttk.Button(label_frame, text='Do Forced Move', command=doForcedMove, style='Confirm.TButton')
    board = BackgammonBoard(GameWindow, ('forest green', 'blue', 'red', 'goldenrod', 'gray54', 'black', 'black'), confirm_button, forced_button, doubling)
    board.configure(state='disabled')
    board.grid(column=1, row=0, columnspan=3, sticky=(N,S))
    #intercept close button to close our socket connection
    GameWindow.protocol("WM_DELETE_WINDOW", closeGameWindow)
    #create labels representing user's names and scores 
    #also this frame will contain Confirm and Forced Move buttons, and pip counters for team and opponent 
    label_frame.grid(column=0, row=0, sticky=(N,S,E,W))
    ttk.Label(label_frame, textvariable=username, style='Name.TLabel').grid(column=1, row=0)
    ttk.Label(label_frame, text='     ', style='SmallSpace.TLabel').grid(column=1, row=1)
    ttk.Label(label_frame, textvariable=user_score, style='Name.TLabel').grid(column=1, row=2)
    user_score.set('0')
    ttk.Label(label_frame, text='     ', style='SmallSpace.TLabel').grid(column=1, row=3)
    ttk.Label(label_frame, textvariable=opponentname, style='Name.TLabel').grid(column=1, row=4)
    ttk.Label(label_frame, text='     ', background=background_color).grid(column=1, row=5)
    ttk.Label(label_frame, textvariable=opponent_score, style='Name.TLabel').grid(column=1, row=6)
    opponent_score.set('0')
    ttk.Label(label_frame, text='\n', style='SmallSpace.TLabel').grid(column=1, row=7)
    team_pips.set(board.team_pipcount)
    opp_pips.set(board.opp_pipcount)
    team_pip_label = ttk.Label(label_frame, text=f"{username.get()}'s pip count", style='Pip.TLabel')
    team_pip_label.grid(column=1, row=12)
    ttk.Label(label_frame, textvariable=team_pips, style='Number.TLabel').grid(column=1, row=14)
    ttk.Label(label_frame, text='\n', style='BigSpace.TLabel').grid(column=1, row=15)
    #will fill out this text when we get opponent's name from server
    opp_pip_label = ttk.Label(label_frame, style='Pip.TLabel')
    opp_pip_label.grid(column=1, row=16)
    ttk.Label(label_frame, textvariable=opp_pips, style='Number.TLabel').grid(column=1, row=18)
    
    confirm_button.state(['disabled'])
    confirm_button.grid(column=1, row=8)
    ttk.Label(label_frame, text='       ', style='SmallSpace.TLabel').grid(column=1, row=9)
    forced_button.state(['disabled'])
    forced_button.grid(column=1, row=10)
    ttk.Label(label_frame, text='\n', style='BigSpace.TLabel').grid(column=1, row=11)
    
    #create space to left and right of the label frame
    ttk.Label(label_frame, text='       ', style='SmallSpace.TLabel').grid(column=0, row=0)
    ttk.Label(label_frame, text='       ', style='SmallSpace.TLabel').grid(column=2, row=0)
    
    #create frame below the board that will contain roll button, dice images, and summary text bar
    dice_frame = ttk.Frame(GameWindow, style='Background.TFrame')
    dice_frame.grid(column=0, row=1, columnspan=5, sticky=(N,S,E,W))
    die_1 = Dice(dice_frame)
    die_2 = Dice(dice_frame)
    gameDice = DiceSet(die_1, die_2)
    ttk.Label(dice_frame, text='\t', style='SmallSpace.TLabel').grid(column=2, row=1)
    die_1.grid(column=3, row=1)
    ttk.Label(dice_frame, text='       ', style='SmallSpace.TLabel').grid(column=4, row=1)
    die_2.grid(column=5, row=1)
    roll_button = ttk.Button(dice_frame, text='Roll', command=lambda *args:drawDice(die_1, die_2), style='Confirm.TButton')
    ttk.Label(dice_frame, text='\t', style='SmallSpace.TLabel').grid(column=0, row=1)
    roll_button.grid(column=1, row=1)
    roll_button.state(['disabled'])
    ttk.Label(dice_frame, text='\t', style='SmallSpace.TLabel').grid(column=6,row=1)
    summarytext = Text(dice_frame, width=70, height=1, font=summaryFont)
    summarytext.grid(column=7,row=1, sticky=(E,W))
    summarytext.see('1.0')
    
    #create space on top and bottom of dice frame
    ttk.Label(dice_frame, text='       ', style='SmallSpace.TLabel').grid(column=0, row=0)
    ttk.Label(dice_frame, text='       ', style='SmallSpace.TLabel').grid(column=0, row=2)

    GameWindow.grab_set()
    

    #this function will be launched in our 'game_thread'
    #will perform instructions from the server or ComputerPlayer on our board and messagebox
    def serverListener():     
        def handle():
            recentWin = False
            #get user's name and set up our board according to instructions
            sock.sendall(bytes(username.get(), 'ascii'))
            setup_orient = str(sock.recv(2), 'ascii')
            print('setup_orient: ', setup_orient)
            board.setUpGame(setup_orient)
            while(True):
                try:
                    msg = str(sock.recv(80), 'ascii')
                    print('received message:', msg)
                    if msg == 'first roll':
                        gameDice.clearDice()
                        roll_button.state(['!disabled'])
                        roll_button['command'] = lambda *args:drawDice(gameDice, firstRoll=True)
                        summarytext.insert('end', '\nPlease press the roll button to roll one die.')
                    elif msg == 'turn':
                        if board.canRoll() is True:
                            #check if it is possible for us to win the game, if not, end the match
                            if board.isRacing() is True:
                                canWin = board.canWin()
                                print('canWin in client: ', canWin)
                                if canWin is False:
                                    sock.sendall(b'Y')
                            board.configure(state='normal')
                            roll_button.state(['!disabled'])
                            summarytext.insert('end', '\nIt is your turn. Please roll the dice.')
                        else:
                            summarytext.insert('end', '\nYou cannot roll at this time.')
                            summarytext.see('end')
                            time.sleep(2)
                            confirm()
                    #opponent sent us their move, we will perform it on our board and set new pipcounts to display on our GUI
                    elif len(msg) > 0 and msg[0].isdigit():
                        #if message is only one length (a cryptic 5), then we don't move any pieces
                        #if message is more than one length, we will parse the move and perform it on our board
                        if len(msg) > 1:
                            print('client moving pieces to reflect ai move')
                            move_args = msg.split(':')
                            print('move string in client: ', move_args)
                            print('bar data: ', board._piece_locations[26])
                            for num, ml in enumerate(move_args):
                                move_list = ml.split(',')
                                for i in range(0, len(move_list)):
                                    move_list[i] = int(move_list[i])
                                #perform opponent's move on our board
                                dt = board.movePiece(move_list[0], move_list[1], count=1, dice=None, col=board._opponent, barPieces=move_list[2:] if len(move_list) > 2 else None)
                                dt.start()
                                #do one move at a time, halt program here until individual moves are done
                                board.synchQueue.get()

                            print('bar data: ', board._piece_locations[26])
                            board.pipCount()
                            team_pips.set(board.team_pipcount)
                            opp_pips.set(board.opp_pipcount)
                        #opponent has forced move or cannot move
                        else:
                            summarytext.insert('end', f'\n{opponentname.get()} cannot move at this time.')
                            summarytext.see('end')
                            time.sleep(2)
                    
                        #query our board, asking if game is over
                        if board.isGameOver() is False:
                            sock.sendall(b'N')
                        else:
                            sock.sendall(b'Y') 
        
                        team_pips.set(board.team_pipcount)   
                        opp_pips.set(board.opp_pipcount) 
                        gameDice.clearDice()
                    #time for opponent to send us their roll
                    elif msg == 'opproll':
                        gameDice.clearDice()
                        data = str(sock.recv(3), 'ascii')
                        roll = data.split(',')
                        #check if dice are 0 here, if so say opponent cannot roll
                        if roll[0] != '0':
                            gameDice.rollDice(finalNum1=int(roll[0]), finalNum2=int(roll[1]))
                            if roll[0] != roll[1]:
                                summarytext.insert('end', f'\n{opponentname.get()} rolled a {roll[0]} and {roll[1]}.')
                            else:
                                summarytext.insert('end', f"\n{opponentname.get()} rolled double {roll[0]}'s")
                        else:
                            summarytext.insert('end', f'\n{opponentname.get()} cannot roll at this time.')
                            summarytext.see('end')
                            time.sleep(2)
                
                    elif msg == 'frwin':
                        second_die = int(sock.recv(1))
                        print('second_die: ', second_die)
                        gameDice._d2.rollDie(finalNum=second_die)
                        print('frwin dice data: ', gameDice.getDice())
                        board.setDice(*gameDice.getDice())
                        board.configure(state='normal')
                        summarytext.insert('end', '\nYou won first die roll. It is now your turn.')
                    elif msg == 'frloss':
                        opp_die = int(sock.recv(1))
                        gameDice._d2.rollDie(finalNum=opp_die)
                        summarytext.insert('end', f'\nYou lost the first die roll. Opponent rolled a {opp_die}.')
                    elif msg == 'frtie':
                        gameDice._d2.rollDie(finalNum=gameDice._d1.get())
                        summarytext.insert('end', '\nFirst roll was a tie.')
                    #server will test our connection during certain points in it's execution
                    elif msg == 'test':
                        pass
                    elif msg == 'double':
                        print('other client sent us a doubling request!')
                        doublePrompt()
                    elif msg == 'incre':
                        print('incrementing our client doubling cube!')
                        loc = str(sock.recv(4), 'ascii')
                        board.redrawCube(loc)
                    #we lost the game
                    elif msg == 'stakes':
                        print('server asked us for the stakes')
                        summarytext.insert('end', f'\n{opponentname.get()} has won the match.')
                        total = int(board.stakes*board.isGammon())
                        opponent_score.set(str(int(opponent_score.get())+total))
                        sock.sendall(bytes(str(total), 'ascii'))
                        recentWin = False
                    elif msg == 'nextmatch':
                        print('server wants us to prepare for next match')
                        opp_pips.set('167')
                        team_pips.set('167')
                        gameDice.clearDice()
                        board.restartGame()
                    #we won game (AI match)
                    elif msg == 'score':
                        summarytext.insert('end', f'\nWe won the match.')
                        print('server is trying to update our score')
                        user_score.set(str(int(sock.recv(2))))
                        recentWin = True
                    elif msg == 'rematch':
                        if recentWin is True:
                            summarytext.insert('end', f'\nWe have won the game.')
                        else:
                            summarytext.insert('end', f'\n{opponentname.get()} has won the game.')
                        summarytext.see('end')
                        rematchPrompt()
                    elif msg == 'scorereset':
                        user_score.set('0')
                        opponent_score.set('0')
                    elif msg == 'opp':
                        opp_name = str(sock.recv(9), 'ascii')
                        opponentname.set(opp_name)
                        opp_pip_label['text'] = f"{opponentname.get()}'s pip count"
                        #if username same as opponent's name, then our name needs a '1' appended to it
                        if opponentname.get() == username.get():
                            username.set(username.get()+'1')
                            team_pip_label['text'] = f"{username.get()}'s pip count"
                    elif msg == 'restart':
                        print('server told us to restart our game')
                        summarytext.insert('end', f'\n{opponentname.get()} has left the game. Waiting for new player to join.')
                        summarytext.see('end')
                        board.restartGame(end=True)
                        user_score.set('0')
                        opponent_score.set('0')
                        opp_pips.set('167')
                        team_pips.set('167')
                        opponentname.set('')
                        roll_button.state(['disabled'])
                        gameDice.clearDice()
                        handle()
                    elif msg == 'end':
                        summarytext.insert('end', f'\nThe match has ended.  Close out window to go back to main menu.')
                        summarytext.see('end')
                        print('shutting down game thread in client')
                        break

                    summarytext.see('end')
            
                except Exception as ce:
                    print(type(ce))
                    print(traceback.format_exc())
                    print('shutting down game thread in client')
                    return
                    
        with sock:
            sock.connect(('192.168.0.13', 20000))
            handle()
            return

    game_thread = threading.Thread(target=serverListener)
    game_thread.start()
              

if __name__ == '__main__':
    mainMenu()
    #start event loop of client GUI
    root.mainloop()



