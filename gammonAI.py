from random import randint
import time
import copy
from operator import itemgetter, attrgetter
from threading import Condition, Thread
#this class will contain all logic for computer to play a human
#will run the game much like gammonserver does, except will make it's own moves back to the client
#same interface as server socket from client perspective
mainCondition = Condition()
transitionCondition = Condition()
class ComputerPlayer():
    #class variable which is a tuple of tuples representing every roll in the game
    combinations = ((1,1), (1,2), (1,3), (1,4), (1,5), (1,6), (2,2), (2,3), (2,4), (2,5), (2,6), (3,3), (3,4), (3,5), (3,6), \
                    (4,4), (4,5), (4,6), (5,5), (5,6), (6,6))
    #instantiate the AI with the orientation of it's homeboard
    def __init__(self, homeboard, board):
        self._homeboard = homeboard
        #we will maintain our own copy of a board
        self._board = board
        #this instance variable operates as a flag for our recv() method, essentially puts us in a state of taking turns when 'OFF'
        self._state = 'ON'
        self.our_turn = None
        #methods will respond to player based upon what 'phase' the game is currently in
        self.phases = ('recvname', 'sendorientation', b'opp', b'first roll', b'frwin', b'frtie', b'frloss', b'turn', 'sendname', 'senddie', b'opproll', \
                       'senddice', 'gettingdice', b'score', 'willbeopponentscore', b'stakes', b'nextmatch', b'incre', b'opp', b'team', 'contemplating', b'rematch', b'scorereset', b'end')
        self.phase = None
        self.team_score = 0
        self.opponent_score = 0
        self.repeats = 0
        self.prev = None
        self.is_game_over = False
        
    def connect(self, *args):
        print('here at our connect method')
        self.phase = 0
        
    def sendall(self, *args):
        def winningState():
            print('AI has won the game')
            self._state = 'ON'
            self.our_turn = False
            self.team_score += (self._board.isGammon()*self._board.stakes) 
            self.phase = 15
            self._board.restartGame()
            self._board.setUpGame(self._board._homeboard, subsequent=True)
            print('AI score and client score:', self.team_score, self.opponent_score)
            
        def losingState():
            print('client has won the game')
            self.opponent_score += (self._board.stakes*self._board.isGammon()) 
            self.phases = self.phases[0:14] + (bytes(f'{self.opponent_score}', 'ascii'),) + self.phases[15:]
            #now we will alert client of their win
            self.phase = 13
            self._state = 'ON' 
            self.our_turn = False
            self._board.restartGame()
            self._board.setUpGame(self._board._homeboard, subsequent=True)
            print('AI score and client score:', self.team_score, self.opponent_score)
            if self.is_game_over is True:
                with transitionCondition:
                    transitionCondition.notify()
                self.is_game_over = False
            
        #client sends us their username
        if self.phase == 0:
            self.players = [b'us', args[0]]
            self.phase = 1
            print('here at receiving clients username')
        #client sends us their first roll
        elif self.phase == 3:
            self._state = 'ON'
            result = int(args[0])
            self.roll = randint(1,6)
            if result > self.roll:
                self.phase = 4
            elif result < self.roll:
                self.phase = 6
            else:
                self.phase = 5
                
            self.roll = (self.roll, result)
        #client is sending us that game is not over, we won't do anything with this information
        elif self.phase == 12 and str(args[0], 'ascii') != 'N':
            self.phase = 10
        #client is sending us the score of the match because we won, will disregard this info since AI calculates this itself
        elif self.phase == 16:
            print('client sent us the score (AI perspective')
        elif self.phase == 20:
            print('client has sent us their answer to AIs doubling proposal', 'args:', args)
            #we will continue game if client accepted doubling proposal and end game if they said no (AI win)
            if str(args[0], 'ascii') == 'N':
                #BUG FIX, instead of just continuing game, will need to tell client to increment their doubling cube, THEN continue the game
                self.phase = 17
                self._state = 'ON'
                self._board.redrawCube('opp')
            else:
                winningState()
        elif self.phase == 21:
            print('client has sent us their response to the rematch', 'args:', args)
            self._state = 'ON'
            if str(args[0], 'ascii') == 'Y':
                self.phase = 22
            else:
                self.phase = 23
        #client said game is over after we sent them our move (AI win)
        elif str(args[0], 'ascii') == 'Y':
            winningState()
        #client is sending us their move so we will update our board
        #will need to check for a doubling proposal here to implement doubling in the AI, will probably make a method for making decision
        #also need to check if end of game here (and when we move our pieces in _makeMove())
        elif self.our_turn is False and str(args[0], 'ascii')[0].isdigit():
            print('performing client move:', str(args[0]))
            self._movePieces(str(args[0], 'ascii'))
            #check if game is over as a result of doing this move on our board, which means ComputerPlayer lost
            if self._board.isGameOver() is True:
                #give client's board enough time to finish it's animation
                self.is_game_over = True
                self._board.root.after(4000, losingState)
        #if client proposes a doubling of the stakes
        if str(args[0], 'ascii') == 'double':
            print('AI has received doubling proposal')
            diff = int(self._board.team_pipcount) - int(self._board.opp_pipcount)
            if diff < 15:
                print('confirmed accepted')
                self._board.redrawCube('team')
                self.phase = 17
                self._state = 'ON'
            #will need to end the game as a result of declining proposal here (client win)
            else:
                losingState()
        
        def transition():
            if self.is_game_over is True:
                with transitionCondition:
                    transitionCondition.wait()
            #if client is blocked on their recv() call, then release them after every sendall() call by the client    
            with mainCondition:
                mainCondition.notify()
                
            return
        
        t_thread = Thread(target=transition) 
        t_thread.daemon = False
        t_thread.start()   
            
    def recv(self, *args):
        print('CURRENT PHASE:', self.phase)
        if self._state == 'ON':
            if self.phase == self.prev:
                self.repeats += 1
            else:
                self.repeats = 0
                
            if self.repeats == 6:
                raise Exception('erronious conditions')
                
            self.prev = self.phase
            #tell client their homeboard orientation
            if self.phase == 1:
                self.phase = 2
                print('here at sending our client their orientation')
                return b'br' if self._homeboard == 'bl' else b'bl'
            #tell client to receive our name
            if self.phase == 2:
                self.phase = 8
                return self.phases[2]
            #tell client it's first roll
            elif self.phase == 3:
                time.sleep(2)
                self._state = 'OFF'
                return self.phases[self.phase]
            #client won first roll, it is their turn, set our phase to 'senddie'
            elif self.phase == 4:
                self.phase = 9
                self.our_turn = False
                return self.phases[4]
            #first roll was a tie, revert phase back to first roll and tell client it was a tie
            elif self.phase == 5:
                self.phase = 3
                return self.phases[5]
            #client lost the first die roll, tell them they lost and set our phase to 'senddie'
            elif self.phase == 6:
                self.phase = 9
                self.our_turn = True
                return self.phases[6]
            #send client our name
            elif self.phase == 8:
                self.phase = 3
                return b'DevinGPT'
            #send client our first die roll result
            elif self.phase == 9:
                self._state = 'OFF'
                if self.our_turn is False:
                    self.phase = 10
                return bytes(f'{self.roll[0]}', 'ascii')
            #tell client they will be receiving their score because they won
            elif self.phase == 13:
                self.phase = 14
                return self.phases[13]
            #send client their score
            elif self.phase == 14:
                self.phase = 16
                return self.phases[14]
            #tell client to update their board because we won
            elif self.phase == 15:
                self.phase = 16
                return self.phases[15]
            #tell client to prepare for their next match, unless one player's points has reached the winning threshold
            elif self.phase == 16:
                if self.team_score >= 11 or self.opponent_score >= 11:
                    self.phase = 21
                    self.team_score = 0
                    self.opponent_score = 0
                else:
                    self.phase =  3 
                    
                return self.phases[16]
            #tell client to increment their doubling cube
            elif self.phase == 17:
                self.phase = 18
                return self.phases[17]
            #tell client how orient their doubling cube 
            elif self.phase == 18:
                self.phase = 7 if self._board.cube_location == 'team' else 10
                self._state = 'OFF'
                #we need to tell client it is their turn after an accepting of the doubling proposal
                self.our_turn = True
                return self.phases[18] if self._board.cube_location == 'team' else self.phases[19]
            #game is over, we are asking client if they would like a rematch
            elif self.phase == 21:
                self._state = 'OFF'
                return self.phases[21]
            #client has agreed to a rematch, we will tell client to reset their scoreboard
            elif self.phase == 22:
                self.phase = 3
                return self.phases[22]
            #client has declined the rematch, we will tell client to end their session
            elif self.phase == 23:
                print('computer telling game thread to shut down')
                return self.phases[23]
            
        else:
            #when we are waiting for client to make move, we will block client's recv() call
            if self.our_turn is False or self.our_turn is None or self.phase == 20:
                with mainCondition:
                    mainCondition.wait()
                if self.phase == 4 or self.phase == 5 or self.phase == 6:
                    time.sleep(1)
                return b'test'
            else:
                time.sleep(2)
                #these phases essentially represent us taking turns playing the game with the client
                #tell client it is their turn, set our turn flag to false
                if self.phase == 7:
                    self.our_turn = False
                    self.phase = 12
                    return self.phases[7]
                #send opproll phase to client unless AI wants to propose a doubling of the stakes
                elif self.phase == 10:
                    #positive difference means WE have the higher pip count
                    difference = int(self._board.team_pipcount) - int(self._board.opp_pipcount)
                    #this suite will detirmine whether the AI will propose a doubling of the stakes
                    if difference < -10:
                        loc = self._board.cube_location
                        if loc == 'team' or loc == 'mid':
                            self.phase = 20
                            return b'double'
                        
                    self.phase = 11
                    return self.phases[10]
                #send our roll to client
                elif self.phase == 11:
                    self.phase = 9
                    self.roll = [randint(1,6), randint(1,6)]
                    print('AI rolled:', self.roll)
                    return bytes(f'{self.roll[0]},{self.roll[1]}', 'ascii')
                #time to decide on a move to make, then send to the client
                elif self.phase == 9:
                    self.phase = 7
                    return bytes(self._makeMove(), 'ascii')
                else:
                    self._state = 'ON'
        
    #this method will set the phase to tell client to end it's gamethread   
    def close(self):
        self._state = 'ON'
        self.phase = 23
        with mainCondition:
            mainCondition.notify()
        
    
    #socket interface methods that are meaningless to our AI class 
    def __enter__(self):
        pass
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def __repr__(self):
        return 'ComputerPlayer'
    
    #move pieces on our board to reflect client's move
    def _movePieces(self, move):
        if len(move) > 1:
            move_args = move.split(':')
            for num, ml in enumerate(move_args):
                move_list = ml.split(',')
                for i in range(0, len(move_list)):
                    move_list[i] = int(move_list[i])
                print('move_list', move_list)
                self._board.movePiece(*move_list[0:2], 1, col=self._board._opponent, barPieces=move_list[2:] if len(move_list) > 2 else None, \
                pipcount=False if num < len(move_args)-1 else True)
            
        self.our_turn = True
        print('AI board data:', self._board._piece_locations)
    
    
    #this method will return how many spots can be clogged, how many enemy blots can be put on bar, and how risky each move is
    #is passed the potential move list to analyze   
    def _calculateMovePotential(self, pt_moves):
        team = self._board._team
        homeboard = self._board._homeboard
        all_rolls = []
        all_rolls_2 = []
        opp_bar = False
        for p, c in self._board._piece_locations[26]:
            if c == self._board._opponent:
                opp_bar = True
                break
            
        for iter in range(0,2):
            #make congruent list that represents the probability that piece will get hit by enemy piece once moved
            probabilities = []
            distances = []
            for f,t,c,d in pt_moves:
                chosen_idx = t if iter == 0 else f
                condition = (len(self._board._piece_locations[chosen_idx]) == 0) if chosen_idx == t else (len(self._board._piece_locations[chosen_idx]) == 2)
                #condition signifies if a blot can be potentially left after this move is performed
                if condition is True:
                    for i in range(1,chosen_idx) if homeboard == 'br' else range(chosen_idx,25):   
                        if len(self._board._piece_locations[i]) > 0 and self._board._piece_locations[i][0][1] != team:
                            distances.append((chosen_idx-i) if homeboard == 'br' else (i-chosen_idx))
                            
                        #add in danger of opponent pieces on bar to the calculation but only do this once per iteration
                        if (i == 1 or i == chosen_idx) and opp_bar is True:
                            idx = 25 if homeboard == 'bl' else 0
                            distances.append((idx-chosen_idx) if homeboard == 'bl' else (chosen_idx-idx))
                          
                probabilities.append(distances.copy())
                distances.clear()
            
            #compute probabilities for every move of getting hit if leaving a blot by counting amount of rolls that can hit the potential blot
            for num, dis in enumerate(probabilities):
                detected_rolls = set()
                chosen_idx = 1 if iter == 0 else 0
                #iterate through every distance that can hit us from this move
                for d in dis:
                    #will do simple calculation for single dice shots
                    if d <= 6:
                        for com in self.combinations:
                            if d == com[0] or d == com[1]:
                                detected_rolls.add(com)
                    
                    #for every distance, we will check to see every combination that can hit it
                    #also see if intermediate spot(s) are open to see if combo really works  
                    for comb in self.combinations:
                        d1, d2 = comb[0], comb[1]
                        roll_value = d1 + d2
                        roll_value2 = 0
                        roll_value3 = 0
                        if d1 == d2:
                            roll_value2 = d1 + d1 + d1
                            roll_value3 = d1 + d1 + d1 + d1
                                
                        if d == roll_value or d == roll_value2 or d == roll_value3:
                            spot1 = self._board._piece_locations[(pt_moves[num][chosen_idx]+d1) if homeboard == 'bl' else \
                                                               (pt_moves[num][chosen_idx]-d1)]
                            spot2 = self._board._piece_locations[(pt_moves[num][chosen_idx]+d2) if homeboard == 'bl' else \
                                                               (pt_moves[num][chosen_idx]-d2)]
                            #this suite ensure that if a spot is three or four moves away (double only), then can only hit that spot if all intermediate
                            #spots are open
                            if d1 == d2:
                                if d == roll_value and (len(spot1) > 1 and spot1[0][1] == team) is False:
                                    detected_rolls.add(comb)
                                elif d == roll_value2:
                                    spot3 = self._board._piece_locations[(pt_moves[num][chosen_idx]+(d1*2)) if homeboard == 'bl' else \
                                                                   (pt_moves[num][chosen_idx]-(d1*2))]
                                    if (len(spot1) > 1 and spot1[0][1] == team) is False and (len(spot3) > 1 and spot3[0][1] == team) is False:
                                        detected_rolls.add(comb)
                                elif d == roll_value3:
                                    spot3 = self._board._piece_locations[(pt_moves[num][chosen_idx]+(d1*2)) if homeboard == 'bl' else \
                                                                   (pt_moves[num][chosen_idx]-(d1*2))]
                                    spot4 = self._board._piece_locations[(pt_moves[num][chosen_idx]+(d1*3)) if homeboard == 'bl' else \
                                                                   (pt_moves[num][chosen_idx]-(d1*3))]
                                    if (len(spot1) > 1 and spot1[0][1] == team) is False and (len(spot3) > 1 and spot3[0][1] == team) is False and \
                                    (len(spot4) > 1 and spot4[0][1] == team) is False:
                                        detected_rolls.add(comb)
                            #all non-double rolls with be analyzed here, ensure at least one intermediate spot is open 
                            else:
                                if (len(spot1) > 1 and spot1[0][1] == team) is False or (len(spot2) > 1 and spot2[0][1] == team) is False:
                                    detected_rolls.add(comb)
                
                #second iteration of loop populations all_rolls_2 list, which represents all rolls that can hit blot on spot piece moved from (if applicable)                            
                all_rolls.append(detected_rolls) if iter == 0 else all_rolls_2.append(detected_rolls)
        
        final_rolls = []      
        for dr1, dr2 in zip(all_rolls, all_rolls_2):
            rolls = set()
            #extract roll data out of each congruent set (one set represents rolls that can hit piece we just moved, other represents rolls that hit blot we left behind, if any)
            for r in dr1:
                rolls.add(r)
                
            for r1 in dr2:
                rolls.add(r1)
            
            rolls = sorted(rolls, key=itemgetter(0,1))   
            final_rolls.append(rolls)
        
        
        #count rolls in final_rolls, compute probablity that moving piece to that spot will result in being hit
        probabilities = []
        for lis in final_rolls:
            roll_count = 0
            for r in lis:
                if r[0] != r[1]:
                    roll_count += 2
                else:
                    roll_count += 1
                    
            chance = (roll_count/36) * 100
            probabilities.append(chance)
                       
        print('potential moves:', pt_moves)      
        print('probabilites:', probabilities)
        #now analyze our potential moves for spots to clog and opponent blots that can be put on bar
        clog_potential = []
        blot_potential = []
        available_dice = 2 if self.roll[0] != self.roll[1] else 4
        #sort our move list numerically by where the piece will land
        new_list = sorted(pt_moves, key=itemgetter(1))
        prev = None, None
        for idx, data in enumerate(new_list):
            #make die_data actually reflect number of dice being used with this move
            die_data = data[3]-1 if data[3] != 1 else 1
            clog_cond = len(self._board._piece_locations[data[1]]) == 0 or (len(self._board._piece_locations[data[1]]) == 1 and self._board._piece_locations[data[1]][0][1] != team)
            #if previous move goes to same spot, we can potentially clog a spot
            if data[1] == prev[0] and clog_cond:
                #check that potential clogging is possible using available_dice data
                if available_dice-die_data-prev[1] >= 0:
                    clog_potential.append((new_list[idx-1], data))
            
            #if we roll doubles and more than one piece on spot, we can clog a spot       
            if clog_cond and available_dice == 4 and len(self._board._piece_locations[data[0]]) > 1:
                clog_potential.append((data,data))
                
            if len(self._board._piece_locations[data[1]]) == 1 and self._board._piece_locations[data[1]][0][1] != team:
                blot_potential.append(data)
                
            prev = data[1], die_data
            
        return clog_potential, blot_potential, probabilities
    
    #it's time for us to decide what the best move is, perform it on our board, then return the move to be made to the client
    #forced moves are also dealt with here
    def _makeMove(self):
        print('here at make move')
        self._board.setDice(*self.roll)
        team = self._board._team
        homeboard = self._board._homeboard
        #positive difference means WE have the higher pip count
        difference = int(self._board.team_pipcount) - int(self._board.opp_pipcount)
        #set our strategy, based on State Pattern
        #in State Pattern parlance, this method is the context, which will control the state transitions (see suites below)
        strategy = None
        if self._board.is_racing() is True:
            strategy = RacingStrategy.instance()
        elif difference < -10:
            strategy = SafeStrategy.instance()
        elif difference > -5 and difference < 5:
            strategy = NormalStrategy.instance()
        elif difference < 15 and difference > 5:
            strategy = AggressiveStrategy.instance()
        else:
            strategy = BlockingStrategy.instance()
        
        print('strategy has been set to:', strategy)  
        is_doubles = self._board.is_double
        #if move isn't forced, decide what to do. If move is forced, just send client forced move
        move_to_send = None
        if self._board.is_forced_move is False:
            #do moves we need to do to get to point of having options (if any)
            print('before_potentials', self._board.before_potentials)
            #if there were alternatives involving getting piece from bar
            if len(self._board.before_potentials) > 0 and self._board.before_potentials[0][1] == 26:
                bar_p = 0
                for p, c in self._board._piece_locations[26]:
                    if c == team:
                        bar_p += 1
                
                #find any potential choices in the before_potentials move phase
                self.alt_before_potentials = None
                loop_count = 0
                #this code will basically be used for multiple options when getting off of the bar, to see if other way of getting off bar opens up
                #more opponent pieces to put on bar
                while(True):
                    print('scanning for potential alternatives, loop number', loop_count) 
                    if loop_count == len(self._board.before_potentials):
                        break
                           
                    f, ml = next(self._board.countMoves(bar_p))
                    move_list = []
                    for d, m in enumerate(ml,1):
                        if m is not None:
                            #turn our actual_idx into light_idx value
                            real_m = self._board._spotid.index(m)
                            move_list.append((f,real_m,1,d))
                    
                    #will only use the alt_before_potentials list if we find the before_potentials move(s) that were performed
                    alt_before_potentials = [] 
                    match_found = False  
                    for move in move_list:
                        m1 = self._board.before_potentials[loop_count]
                        if (move[0],move[1]) != (m1[1],m1[0]):
                            alt_before_potentials.append(move)
                        else:
                            match_found = True
                                    
                    if (match_found is True and len(alt_before_potentials) > 0) or (match_found is False and len(alt_before_potentials) > 1):
                        self.alt_before_potentials = alt_before_potentials
                        break
                    elif (match_found is True and len(alt_before_potentials) == 0) or (match_found is False and len(alt_before_potentials) == 1):
                        self._board.movePiece(*move_list[0])
                    else:
                        break
                            
                    loop_count += 1
                
                #good moves list will represent concrete alternatives for before_potentials and potentials variable
                good_moves = []       
                if self.alt_before_potentials is not None:
                    print('found potential choices for before potentials moves:', end=' ')
                    print(self.alt_before_potentials)
                    for move in self.alt_before_potentials:
                        self._board.movePiece(*move)
                        move_list = []
                        move_count = 0
                        active_dice = self._board.countDice()
                        for f, ml in self._board.countMoves():
                            for d, m in enumerate(ml,1):
                                if m is not None:
                                    real_m = self._board._spotid.index(m)
                                    move_list.append((f,real_m,1,d))
                                    size = len(self._board._piece_locations[f]) if f != 26 else bar_p
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
                        
                        if move_count > active_dice:
                            good_moves.append((copy.deepcopy(self._board._last_move), move_list))
                            
                        self._board._undo()
                        
                while(len(self._board._last_move) > 0):
                    self._board._undo()
                    
                print('other choices for before_potentials:', good_moves)
                #if we found concrete alternatives, will see if it is worth doing alternative based upon current strategy
                if len(good_moves) > 0:
                    strategy.alternateBarMoves(self._board, good_moves, self)
            
            #perform our vital pre potentials moves             
            d_args = []
            for num, move in enumerate(self._board.before_potentials):
                print('performing before potentials move:', move)
                #find the dice arg for movePiece, will make appropiate die or dice null
                f, t = move[1], move[0]
                if f == 26:
                    f = 0 if homeboard == 'bl' else 25
                    
                difference = (t-f) if homeboard == 'bl' else (f-t)
                print('difference:', difference)
                d_arg = None
                if difference == self._board._dice_1 or difference > self._board._dice_2:
                    d_arg = 1
                elif difference <= self._board._dice_2:
                    d_arg = 2
                elif difference == (self._board._dice_1+self._board._dice_2):
                    d_arg = 3
                elif difference == (self._board._dice_1+self._board._dice_2+self._board._dice_3):
                    d_arg = 4
                       
                d_args.append(d_arg)
                self._board.movePiece(*move[-3:-5:-1], 1, dice=d_arg, col=self._board._team, pipcount=True if num < len(self._board.before_potentials)-1 else False, highlight=False)
            
            self.roll = (self._board._dice_1, self._board._dice_2, self._board._dice_3, self._board._dice_4)
            #call our calculate method to get lists representing moves to clog a spot, put an enemy piece on bar, and probabilities of getting hit by enemy after making particular move   
            self.clog_potential, self.blot_potential, self.probabilities = self._calculateMovePotential(self._board.potentials)    
            print('clog_potential:', self.clog_potential)
            print('blot_potential:', self.blot_potential)
            print('potentials:', self._board.potentials)
            strategy.blotOptionAnalysis(self)
            strategy.coverPieces(self)
            strategy.clogOptionAnalysis(self)
            strategy.doRemainingMoves(self) 
            print('potentials:', self._board.potentials)
            print('probabilites:', self.probabilities)
            print('_last_move:', self._board._last_move)   
            #change to _last_move to check for intermediate opponent pieces we have to move to bar   
            for num, move in enumerate(self._board._last_move):
                #we will see what dice arg was used in the movePiece call
                die_arg = None
                dice = move[2]
                next_dice = None
                if len(self._board._last_move)-1 > num:
                    next_dice = self._board._last_move[num+1][2]
                    
                dice_used = 0
                next_dice = next_dice if next_dice is not None else (self._board._dice_1, self._board._dice_2, self._board._dice_3, self._board._dice_4)
                for idx, (d1, d2) in enumerate(zip(dice, next_dice), 1):
                    if d1 is not None and d2 is None:
                        dice_used += 1
                        die_arg = idx
                        if is_doubles is False and idx == 2:
                            if dice_used == 2: 
                                die_arg = 3
                            break
                        
                if is_doubles is True:
                    die_arg = dice_used + 1
                
                print('die_arg:', die_arg)   
                if die_arg > 2:
                    original_spot = move[1]
                    intermediate_spots = set()
                    dice_data = move[2]
                    intermediate_spots.add((dice_data[0]+original_spot) if homeboard == 'bl' else (original_spot-dice_data[0]))
                    intermediate_spots.add((dice_data[1]+original_spot) if homeboard == 'bl' else (original_spot-dice_data[1]))
                    if die_arg > 3:
                        intermediate_spots.add((dice_data[0]+dice_data[1]+original_spot) if homeboard == 'bl' else (original_spot-dice_data[0]-dice_data[1]))
                    if die_arg > 4:
                        intermediate_spots.add((dice_data[0]+dice_data[1]+dice_data[2]+original_spot) if homeboard == 'bl' else (original_spot-dice_data[0]-dice_data[1]-dice_data[2]))
                    
                    new_bar_list = [] 
                    num_of_blots = 0 
                    for spot in intermediate_spots:
                        if len(self._board._piece_locations[spot]) == 1 and self._board._piece_locations[spot][0][1] != team:
                            num_of_blots += 1
                            #for doubles, any intermediate spot with a blot must be put on bar
                            #for non-doubles, if both intermediate spots contain an enemy blot, then we will send one farthest away to the bar
                            if is_doubles is True or num_of_blots == 2:
                                new_bar_list.append(spot)
                    
                    #remove and replace move in _last_move list with the new barPieces list           
                    if len(new_bar_list) > 0:
                        new_move = (move[0], move[1], move[2], (new_bar_list+move[3]) if move[3] is not None else new_bar_list)
                        self._board._last_move.remove(move)
                        self._board._last_move.insert(num, new_move)
            
            print('_last_move:', self._board._last_move)   
            move_to_send = self._board._last_move
            
        else:
            move_to_send = self._board.forced_moves
            #perform forced move on our board
            for num, move in enumerate(move_to_send):
                self._board.movePiece(*move[-3:-5:-1], 1, col=self._board._team, pipcount=True if num < len(move_to_send)-1 else False, highlight=False)    
        
            
        #pack move to a form we can send to the client
        move_st = ''
        for c, ml in enumerate(move_to_send):
            t, f, d, bp = ml
            move_st += f'{f},{t}'
            if bp is not None:
                for i in bp:
                    move_st += f',{i}' 
            
            if c != len(move_to_send) - 1:      
                move_st += ':'
        
        #if move set is empty, we send a cryptic '5'
        if len(move_st) == 0:
            move_st = '5'  
        
        self._board.confirm() 
        print(self._board._piece_locations)
        if self._board.isGameOver() is True:
            self.our_turn = False
            
        return move_st       
                

#this class will contain all of the methods for a particular game strategy, such as playing more aggressively, more of a blocking strategy, racing, etc 
#we will compose our ComputerPlayer class with a GameStrategy instance, which will return a method depending on what strategy client specifies 
#no need to get an actual instance of these classes, the instance method will return the class which essentially just gives you access to the namespace of a strategy                                
class GameStrategy():
    @classmethod
    def instance(cls):
        return cls
    
    #move piece on ComputerPlayer's board
    @classmethod
    def movePiece(cls, board, player, *moves):        
        #there might be two moves to unpack from moves, in which case we can only perform those moves if they can BOTH be performed
        roll = (board._dice_1, board._dice_2, board._dice_3, board._dice_4)
        print('roll data:', roll)
        for n, move in enumerate(moves, 1):
            print('sub-analyzing move', move)
            skip = False
            if move[3] == 1 or move[3] == 2:
                if roll[move[3]-1] is None:
                    skip = True
            elif move[3] == 3:
                if roll[0] is None or roll[1] is None:
                    skip = True
            elif move[3] == 4:
                if roll[0] is None or roll[1] is None or roll[2] is None:
                    skip = True
            elif move[3] == 5:
                if roll[0] is None or roll[1] is None or roll[2] is None or roll[3] is None:
                    skip = True
            
            #we only remove move if we can't perform move(s) or we perform all move(s)
            if skip is True or len(board._piece_locations[move[0]]) == 0:
                print('here', 'skip=', skip)
                if n == 2:
                    board._undo()   
                break
            else:   
                board.movePiece(*move, highlight=False)
                roll = (board._dice_1, board._dice_2, board._dice_3, board._dice_4)
                print('roll data2:', roll)
                if n == len(moves):
                    #update clog, blot, probabilities, and potentials list
                    print('updating potentials and probabilities')   
                    move_list = []
                    for f, ml in board.countMoves():
                        for d, m in enumerate(ml,1):
                            if m is not None:
                                #turn our actual_idx into light_idx value
                                real_m = board._spotid.index(m)
                                move_list.append((f,real_m,1,d))
                    
                    board.potentials = move_list  
                    #update clog, blot and probabilities lists after we are done moving pieces        
                    player.clog_potential, player.blot_potential, player.probabilities = player._calculateMovePotential(board.potentials)
                   
                    
    #count how many spots on opponent's or our homeboard are clogged
    #optional arg will be for an alternate calculation that returns how many blots on our or opponent's homeboard
    @classmethod
    def clogCount(cls, board, team, clog=True): 
        clogs = 0
        compare = 2 if clog is True else 1
        if team == board._opponent:
            for i in range(1,7) if board._homeboard == 'bl' else range(19,25):
                if len(board._piece_locations[i]) == compare and board._piece_locations[i][0][1] == team:
                    clogs += 1 
        elif team == board._team:
            for i in range(1,7) if board._homeboard == 'br' else range(19,25):
                if len(board._piece_locations[i]) == compare and board._piece_locations[i][0][1] == team:
                    clogs += 1 
                
        return clogs 
    
    
    #return True or False whether there are any enemy pieces on bar or not
    @classmethod
    def is_enemy_on_bar(cls, board):
        for p, c in board._piece_locations[26]:
            if c == board._opponent:
                return True
            
        return False
    
    #default implementations go here
    @staticmethod
    def alternateBarMoves(board, move_list, player):
        pass
    
    @staticmethod
    def clogOptionAnalysis(player):
        pass
    
    @staticmethod
    def blotOptionAnalysis(player):
        pass
    
    @staticmethod
    def coverPieces(player):
        pass
    
    @staticmethod
    #if we have two or more dice left to use and there are still potential clogging moves, we will perform them
    def doRemainingMoves(player):
        if player._board.countDice() >= 2:
            prime_spots = (6,5,4,7) if player._board._homeboard == 'bl' else (19,20,21,18)
            for m1, m2 in reversed(player.clog_potential) if player._board._homeboard == 'bl' else player.clog_potential:
                #blot will be made if spot has this many pieces on it before we perform clogging
                pieces_left = 2 if m1 != m2 else 3
                #won't perform clogging if it leaves a blot and we're not clogging a prime spot on opponent's homeboard
                if (len(player._board._piece_locations[m1[0]]) == pieces_left or len(player._board._piece_locations[m2[0]]) == pieces_left) and m1[1] not in prime_spots: 
                     #will probably put double conditions with three piece on origin condition in here as well
                    print('here1')
                    continue
                else: 
                    print('here2')
                    GameStrategy.movePiece(player._board, player, m1, m2)
    
    
    
    
class NormalStrategy(GameStrategy):
    #for normal strategy, we will see if using alternate move to get piece out on bar results in more oppurtunities to put enemy piece on bar
    def alternateBarMoves(board, move_list, player):
        clog2, blot2, prob2 = player._calculateMovePotential(board.potentials)
        bp = move_list[0][0]
        p = move_list[0][1]
        clog1, blot1, prob1 = player._calculateMovePotential(p)
        print('analyzing move data:', bp, p)
        if len(blot1) > len(blot2) or (len(board._piece_locations[bp[0][0]]) == 1 and board._piece_locations[bp[0][0]][0][1] != board._team):
            print('changing move data to', bp, p)
            board.before_potentials = bp
            board.potentials = p 
          
    def clogOptionAnalysis(player):
        print('here at Normal clogOptionAnalysis')
        #evaluation of prime spots will occur in this order
        prime_spots = (19,18,20,21,17,6,7,5,4,8) if player._board._homeboard == 'bl' else (6,7,5,4,8,19,18,20,21,17)
        home_indices = (6,5,4,3,2,1) if player._board._homeboard == 'br' else (19,20,21,22,23,24)
        #we will occasionally reverse lists during traversal to look at spots closer or further from our homeboard
        #we will also pack both clogging moves into a tuple to put into moves list, that way both moves must be able to be performed or none at all
        for m1, m2 in reversed(player.clog_potential) if player._board._homeboard == 'br' else player.clog_potential:
            if player._board.countDice() == 0:
                break
            #blot will be made if spot has this many pieces on it before we perform clogging
            pieces_left = 2 if m1 != m2 else 3
            #check if moves are in list first before finding the index
            idx1 = None
            idx2 = None
            for num, move in enumerate(player._board.potentials):
                if move == m1:
                    idx1 = num
                if move == m2:
                    idx2 = num
            #if either move is not found in list, remove from clog_list and move to next iteration
            if idx1 is None or idx2 is None:
                print('here1')
                continue        
            #won't perform clogging if it leaves a blot and we're not clogging a prime spot on opponent's homeboard
            if (len(player._board._piece_locations[m1[0]]) == pieces_left or len(player._board._piece_locations[m2[0]]) == pieces_left) and m1[1] not in prime_spots[5:]: 
                 #will probably put double conditions with three piece on origin condition in here as well
                print('here2')
                continue 
            if m1[1] in prime_spots:
                print('here3')
                GameStrategy.movePiece(player._board, player,m1, m2)
            #we will clog a prime spot or any spot that also coincides with getting an enemy blot 
            elif m1 in player.blot_potential:
                print('here4')
                GameStrategy.movePiece(player._board, player,m1, m2)
    
    #we will put enemy piece on bar if it is an intermediate move and we can get safe, or if it's not too dangerous                      
    def blotOptionAnalysis(player):
        print('here at Normal blot')
        SafeStrategy.blotOptionAnalysis(player)
        home_indices = (6,5,4,3,2,1) if player._board._homeboard == 'br' else (19,20,21,22,23,24)
        for move in player.blot_potential:
            if player._board.countDice() == 0:
                break
            if move[1] not in home_indices:
                GameStrategy.movePiece(player._board, player, move)
                    
    
    #we will detirmine if we should cover any of our blips, will only cover blip if move to cover is not more dangerous than simply moving our blot
    def coverPieces(player):
        print('here at normal cover')
        #detirmine if we can get an enemy and put them on bar at same time, if so, we will skip this method so clogOptionAnalysis can take care of the good stuff
        for m1, m2 in player.clog_potential:
            for m in player.blot_potential:
                if m1 == m or m2 == m:
                    return
        
        prob = player.probabilities.copy()      
        for num, move in enumerate(player._board.potentials):
            if player._board.countDice() == 0:
                break
            if len(player._board._piece_locations[move[1]]) == 1 and player._board._piece_locations[move[1]][0][1] == player._board._team:
                compare = prob[num]
                risks = []
                for n1, m1 in enumerate(player._board.potentials.copy()):
                    if m1[0] == move[1]:
                        risks.append((prob[n1], n1))
                        
                pos = 0
                for r in risks:
                    if compare <= r[0]:
                        pos += 1
                        
                if pos == len(risks):
                    print('doing move1', move)
                    GameStrategy.movePiece(player._board, player,move)
                    
                else:
                    risks.sort(key=itemgetter(0))
                    print('doing move2', player._board.potentials[risks[0][1]])
                    GameStrategy.movePiece(player._board, player, player._board.potentials[risks[0][1]])
            elif len(player._board._piece_locations[move[0]]) == 1 and prob[num] == 0.0:
                print('doing move3', move)
                GameStrategy.movePiece(player._board, player, move)
                
                    
    def doRemainingMoves(player):
        print('here at Normal doRemainingMoves')
        GameStrategy.doRemainingMoves(player)
        prime_spots = (19,20,21,22,23,18,17,16,15,14,13,6,7,5,4,8) if player._board._homeboard == 'br' else (6,5,4,3,2,7,8,9,10,11,12,19,18,20,21,17)
        home = (19,20,21,22,23,24) if player._board._homeboard == 'bl' else (6,5,4,3,2,1)
        loop_count = 0
        while(player._board.countDice() > 0):
            loop_count += 1
            if loop_count == 10:
                raise Exception('infinite recursion in doRemainingMoves()') 
            #count pieces we have on opponent homeboard
            behind_enemy_lines = 0
            for i in range(1,7) if player._board._homeboard == 'bl' else range(19,25):
                size = len(player._board._piece_locations[i])
                if size > 0 and player._board._piece_locations[i][0][1] == player._board._team:
                    behind_enemy_lines += size
            
            #sort by highest, then safest rolls
            new_list = [player._board.potentials[i] + (player.probabilities[i],) for i in range(0,len(player._board.potentials))]  
            new_list.sort(key=itemgetter(3), reverse=True)
            new_list.sort(key=itemgetter(4))
            print(new_list)     
            for m in new_list:
                move = m[0:4]
                #condition that detects if we will be unclogging a prime spot if the move were performed, in which case we will not do move
                if (move[0] in prime_spots[0:3] and len(player._board._piece_locations[move[0]]) > 1) is False:
                    idx = player._board.potentials.index(move)
                    if move[1] in prime_spots[7:11]:
                        print('here2')
                        GameStrategy.movePiece(player._board, player, move)
                        break
                    elif move[1] in prime_spots[0:5]:
                        print('here3')
                        GameStrategy.movePiece(player._board, player, move)
                        break
            #lowest chances will represent a sorted list of ascending probability with in place sorting of how many pieces in spot of origin
            lowest_chances = []
            for num, move in enumerate(player._board.potentials):
                lowest_chances.append((move,len(player._board._piece_locations[move[0]]),player.probabilities[num]))               
            #will perform move that has more pieces on the origin spot
            #will only put us in danger of putting blot on our homeboard while enemy on bar if we have to
            lowest_chances.sort(key=itemgetter(2))
            
            print('lowest_chances:', lowest_chances)
            print('probabilities:', player.probabilities)
            print('potentials:', player._board.potentials)
            print('active dice:', player._board._dice_1, player._board._dice_2, player._board._dice_3, player._board._dice_4)
            for iter, data in enumerate(lowest_chances):
                m, size, prob = data
                idx = player._board.potentials.index(m)
                #if move results in putting a blot on our homeboard while and enemy piece is on the bar OR we move to our homeboard while there is a risk
                if m[1] in home and (GameStrategy.is_enemy_on_bar(player._board) or \
                (len(player._board._piece_locations[m[1]]) == 1 and player._board._piece_locations[m[1]][0][1] == player._board._opponent)) or (m[1] in home and prob > 0.0):
                    print('here5')
                    #if we have enough options left to do rest of our roll, then we will skip this move
                    move_dice = 0
                    for move in player._board.potentials:
                        if move != m:
                            die = (move[3]-1) if move[3] != 1 else 1
                            move_dice += die
                        
                    if move_dice >= player._board.countDice() and iter == 0 and len(lowest_chances) > 1:
                        continue
                    else:
                        GameStrategy.movePiece(player._board, player, m)
                else:
                    print('here7')
                    GameStrategy.movePiece(player._board, player, m)
                    
                break
            
            
                         
            
class SafeStrategy(GameStrategy):
    #for safe strategy, we will use alternate move if it results in safer moves afterwards
    def alternateBarMoves(board, move_list, player):
        print('here at Safe alternatveBarMoves()')
        clog2, blot2, prob2 = player._calculateMovePotential(player._board.potentials)
        avg_prob2 = 0
        for prob in prob2:
            avg_prob2 += prob
            
        avg_prob2 = avg_prob2/len(prob2)
        bp = move_list[0][0]
        p = move_list[0][1]
        print('analyzing move data:', bp, p)
        clog1, blot1, prob1 = player._calculateMovePotential(p)
        avg_prob1 = 0
        for prob in prob1:
            avg_prob1 += prob 
            
        avg_prob1 = avg_prob1/len(prob1)
        #a lower average probability means safer outcome for particular move set
        if avg_prob1 < avg_prob2:
            print('changing move data to', bp, p)
            board.before_potentials = bp
            board.potentials = p
            
    def clogOptionAnalysis(player):
        print('here at safe clog')
        NormalStrategy.clogOptionAnalysis(player)
        
    def blotOptionAnalysis(player):
        #get amount of blots we have on our homeboard (if any)
        blots = GameStrategy.clogCount(player._board, player._board._team, clog=False)
        if blots > 1:
            return
        #safe blot analysis will only get blot if we can 'drive-by' it
        print('here at safe blot')
        home = (1,2,3,4,5,6) if player._board._homeboard == 'br' else (19,20,21,22,23,24)
        for move in player.blot_potential if player._board._homeboard == 'bl' else reversed(player.blot_potential):
            for num, m1 in enumerate(player._board.potentials):
                if m1 != move and m1[0] == move[0] and m1[3] > move[3] and m1[3] != 2:
                    if len(player._board._piece_locations[m1[1]]) > 0 and player._board._piece_locations[m1[1]][0][1] == player._board._team:
                        #check if we are covering our one blot in homeboard, if not, will not do move
                        #if we have no blots we will perform move
                        #if there's a perfectly good clogOption where piece is drive-bying, will not do move
                        is_match = False 
                        for m2 in player.clog_potential:
                            if m2[1] == move[1]:
                                is_match = True
                                break
                        print('is_match variable:', is_match)
                        if is_match is False and blots == 0 or (m1[1] in home and len(player._board._piece_locations[m1[1]]) == 1):
                            #we must construct intermediate move that leads from blot to safe spot
                            diff = m1[3] - move[3]
                            if player._board.is_double:
                                if m1[3] == 3:
                                    diff = 1
                                else:
                                   if diff == 2:
                                       diff = 3
                                       
                            new_move = (move[1], m1[1], 1, diff)
                            GameStrategy.movePiece(player._board, player, move, new_move)
            
    def coverPieces(player):
        NormalStrategy.coverPieces(player)
    
    #we will do only the safest moves for the SafeStrategy class   
    def doRemainingMoves(player):
        GameStrategy.doRemainingMoves(player)
        while(player._board.countDice() > 0):
            #sort by safest roll
            new_list = [player._board.potentials[i] + (player.probabilities[i],) for i in range(0,len(player._board.potentials))]
            new_list.sort(key=itemgetter(4))
            for m in new_list:
                move = m[0:4]
                GameStrategy.movePiece(player._board, player, move)
                break
            
class AggressiveStrategy(GameStrategy):
    def alternateBarMoves(board, move_list, player):
        NormalStrategy.alternateBarMoves(board, move_list, player)
        
    def clogOptionAnalysis(player):
        NormalStrategy.clogOptionAnalysis(player)
        
    def blotOptionAnalysis(player):
        NormalStrategy.blotOptionAnalysis(player)
        
    def coverPieces(player):
        NormalStrategy.coverPieces(player)
        
    def doRemainingMoves(player):
        NormalStrategy.doRemainingMoves(player)

class BlockingStrategy(GameStrategy):
    def alternateBarMoves(board, move_list, player):
        #we will see if there is a prime spot that can be clogged from either move set. If there is, we will go with that one
        #if both move sets can result in a prime spot being clogged, then we will go with safer move set
        original = False
        alternate = False
        home = (6,5,4) if player._board._homeboard == 'bl' else (19,20,21)
        for move in board.before_potentials+player._board.potentials:
            if move[1] in home:
                original = True
                break
            
        bp, p = move_list[0][0], move_list[0][1]
        for move in bp+p:
            if move[1] in home:
                alternate = True
                break
            
        if alternate is True and original is False:
            print('changing move data to:', bp, p)
            board.before_potentials = bp
            board.potentials = p
        elif alternate is True and original is True:
            SafeStrategy.alternateBarMoves(board, move_list, player)
        
    def clogOptionAnalysis(player):
        NormalStrategy.clogOptionAnalysis(player)
        
    def blotOptionAnalysis(player):
        NormalStrategy.blotOptionAnalysis(player)
                
    def coverPieces(player):
        NormalStrategy.coverPieces(player) 
        
    def doRemainingMoves(player):
        GameStrategy.doRemainingMoves(player)
        opp_home = (6,5,4,3,2,1) if player._board._homeboard == 'bl' else (19,20,21,22,23,24)
        #we will do remaining moves while trying to keep options open by not performing the move if it comes from opponent's homeboard, unless we're forced to
        loop_count = 0
        while(player._board.countDice() > 0):
            if loop_count > 10:
                raise Exception('infinite recursion in Blocking doReaminingMoves()')
            #sort by safest roll
            new_list = [player._board.potentials[i] + (player.probabilities[i],) for i in range(0,len(player._board.potentials))]
            new_list.sort(key=itemgetter(4))
            for m in new_list:
                move = m[0:4]
                if move[0] in opp_home and loop_count == 0:
                    continue
                else:
                    GameStrategy.movePiece(player._board, player, move)
                    break
                
            loop_count += 1
        
        
class RacingStrategy(GameStrategy):
    #this class will be reliant on only this method, which will try to bear off as many pieces as possible or move every piece to homeboard   
    def doRemainingMoves(player):
        while(player._board.countDice() > 0):
            home_count = 0
            for i in range(19,26) if player._board._homeboard == 'bl' else range(0,7):
                if len(player._board._piece_locations[i]) > 0 and player._board._piece_locations[i][0][1] == player._board._team:
                    home_count += len(player._board._piece_locations[i])
                    
            new_list = sorted(player._board.potentials, key=itemgetter(3), reverse=True)
            for move in new_list if home_count != 15 else reversed(player._board.potentials):
                if home_count != 15 and move[3] != 2:
                    GameStrategy.movePiece(player._board, player,move)
                else:
                    GameStrategy.movePiece(player._board, player,move)
                    
                    
                    
            
                
                     
                   
    
    
    
    
    
    
    
    
    
    
    
