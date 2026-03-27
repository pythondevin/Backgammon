from random import randint
from time import sleep
from threading import Condition, Thread
from copy import deepcopy

mainCondition = Condition()
transitionCondition = Condition()

#class ComputerPlayer - contains all logic for communicating with player and is a client object to BackgammonBoard object
#composes itself with one of the Strategies for move making decisions
#implements same interface as a server socket

#ComputerPlayer will compose itself with one of these strategies and pass board data to the Strategy   
#this is the base class, GameStrategy from which all other Strategies inherit, ComputerPlayer will never compose itself of this base class  
#base class contains all helper functions other Strategies will utilize 
#all other Strategies will only override chooseMove() and use the helper functions it inherits                  
class GameStrategy():
    #class variable which is a tuple of tuples representing every roll in the game
    COMBINATIONS = ((1,1), (1,2), (1,3), (1,4), (1,5), (1,6), (2,2), (2,3), (2,4), (2,5), (2,6), (3,3), (3,4), (3,5), (3,6), \
                    (4,4), (4,5), (4,6), (5,5), (5,6), (6,6))
    #every Strategy will share a board through GameStrategy's board class variable, will assign during ComputerPlayer initialization
    board = None
    #will share access to the ComputerPlayer object, so every Strategy can know about each other, also assigned during ComputerPlayer initialization
    computer = None

    def __init__(self):
        pass
           
    #function ComputerPlayer will call for our strategy to choose a move
    #this base class implementation just performs expensive calculations such as computing odds of all our blots in ascending order of danger as instance variables
    def chooseMove(self):
        #create copy of our board but from opponent perspective, to see which of our blots they can hit for odds calculations
        self.board_copy = GameStrategy.board.createCopy('opp')
        self.blot_odds = self.threatAnalysis()
        self.lowest_list, self.all_odds, self.new_blot_indices, self.new_blot_odds = self._lowestOdds()
        self.currentDanger = self.sumOdds(self.analyzeBlots())
        print('lowest_list: ', self.lowest_list)
        print('all_odds: ', self.all_odds)
        print('GameStrategy.board.blot_list: ', GameStrategy.board.blot_list)
        for odds, moves in zip(self.blot_odds, GameStrategy.board.blot_list):
            print(odds, moves)
        print('seeing size of congruent lists: ', len(self.blot_odds), len(GameStrategy.board.blot_indices), len(GameStrategy.board.blot_list))
            

    #perform all blot moves from our board on opponent's board, then return a list containing all blot odds for all blot moves
    def threatAnalysis(self):
        #set up collection representing odds of every potential blot being hit by opponent
        #is congruent with blot_list and blot_indices
        all_odds = []
        for idx1, moveset in enumerate(GameStrategy.board.blot_list):
            #perform our blot move on board copy
            for fr, to in moveset:
                self.board_copy.movePiece(fr, to, dice=1, col=self.board_copy._opponent)

            all_odds.append(self.analyzeBlots())
            #undo our original blot_list moves
            for _ in range(0,len(self.board_copy._last_move)):
                self.board_copy._undo(barUndo='team')

        return all_odds
        
    #analyze all opponent blots on a board, and return a dict, containing blot and odds of being hit value pairs
    #all odds/risk calculations are done here
    def analyzeBlots(self):
        #add all current blots to our blot_indices list to accurately reflect danger after performing move
        all_blots = [spot for spot in range(1,25) if len(self.board_copy._piece_locations[spot]) == 1 and self.board_copy._piece_locations[spot][0][1] == self.board_copy._opponent]
        #iterate through all possible dice combinations from opponent's view to see if any results in a hit of our blot(s), if so update blot_odds
        blot_odds = {spot:0 for spot in all_blots}
        for d1, d2, in GameStrategy.COMBINATIONS:
            self.board_copy.setDice(d1, d2)
            all_moves = self.countAllMoves()
            #opponent must get off bar first
            if len(all_moves) == 1 and all_moves[0][0] == 26:
                #inner function for analyzing bar moves and post bar moves
                def makeBarMoves(spot, idx, move_list):
                    bar_moves = []
                    bar_moves.append((26, (spot,)))
                    move_ct = 0
                    while(True): 
                        #while suite will end when no more bar moves detected
                        #will never actually run out of moves before we get all pieces off bar, because that would be a forced move and non of this code would even execute!
                        if len(bar_moves) == 0:
                            break
                        start, moves = bar_moves.pop()
                        for die, move in enumerate(moves[:2], 1):
                            if move is not None:
                                self.board_copy.movePiece(26, move, dice=idx if move_ct == 0 else die, col=self.board_copy._team)
                                move_ct += 1
                                new_moves = self.countAllMoves()
                                if len(new_moves) > 0 and new_moves[0][0] != 26:
                                    move_list += new_moves
                                    break
                                #if more bar moves detected, will repeat until non bar moves detected or no more moves detected
                                elif len(new_moves) > 0 and new_moves[0][0] == 26:
                                    bar_moves += new_moves

                    for _ in range(0, move_ct):
                        self.board_copy._undo()
                for die, move in enumerate(all_moves[0][1][:2], 1):
                    if move is not None:
                        makeBarMoves(move, die, all_moves)
                    
            #iterate through all of our detected moves from opponent's view
            for fr, moves in all_moves:
                for die, spot in enumerate(moves, 1):
                    #avoid duplicate double calculation
                    if d1 == d2 and die == 2:
                        continue
                    #if opponent can move to one of our blot indices, is a hit and we will keep track of all hits through blot_odds
                    if spot in blot_odds:
                        blot_odds[spot] += 2 if d1 != d2 else 1
                        #add additional risk if blot will be left in homeboard or close to homeboard
                        if spot in GameStrategy.board.hb_indices:
                            blot_odds[spot] += 3
                        elif spot in GameStrategy.board.closeToHomeboard:
                            blot_odds[spot] += 2
                        #minimize risk if blot is on opponent's homeboard or close to
                        if spot in GameStrategy.board.opp_hb_indices:
                            blot_odds[spot] -= 2
                        elif spot in GameStrategy.board.closeToOppHomeboard:
                            blot_odds[spot] -= 1
                        #factor in how many blots/spots clogged the opponent has
                        blot_odds[spot] += (GameStrategy.board.cloggedHomeboard(GameStrategy.board._opponent)*0.25)
                        blot_odds[spot] -= (GameStrategy.board.cloggedHomeboard(GameStrategy.board._opponent, criteria='blot')*0.25)
                        #factor in how many spots we have clogged
                        blot_odds[spot] += (GameStrategy.board.cloggedHomeboard(GameStrategy.board._team)*0.15) 
                        #minimize risk if blot is on a prime spot
                        #SUGGESTION: do a calculation based upon how easy/hard covering this blot will be on next turn
                        if spot in GameStrategy.board.prime_spots:
                            blot_odds[spot] -= 0.25

        return blot_odds

    def countAllMoves(self):
        move_list = []
        for idx, moves in self.board_copy.countMoves(self.board_copy._countBarPieces(count='team')):
            if moves != (None, None, None, None, None):
                move_list.append((idx, (moves)))

        return move_list

    #analyze our threatAnalysis results and return a blot_list with ascending probability of being sent to bar by opponent
    def _lowestOdds(self):
        new_blot_list = []
        all_odds = []
        new_blot_indices = []
        new_blot_odds = []
        blot_odds_copy = deepcopy(self.blot_odds)
        blot_list_copy = deepcopy(GameStrategy.board.blot_list)
        blot_indices_copy = deepcopy(GameStrategy.board.blot_indices)
        while(len(new_blot_list) < len(blot_list_copy)):
            lowest_odds = self.lowestCalc(blot_odds_copy)
            new_blot_list.append(blot_list_copy[lowest_odds[0]])
            all_odds.append(lowest_odds[1])
            new_blot_indices.append(blot_indices_copy[lowest_odds[0]])
            new_blot_odds.append(blot_odds_copy[lowest_odds[0]])
            del blot_list_copy[lowest_odds[0]]
            del blot_odds_copy[lowest_odds[0]]
            del blot_indices_copy[lowest_odds[0]]

        return new_blot_list, all_odds, new_blot_indices, new_blot_odds

    #find lowest odds from any odds dict
    def lowestCalc(self, blotDict):
        lowest_odds = None
        odds = 0
        for value in blotDict[0].values():
            odds += value
        lowest_odds = (0, odds)
        for idx, blot_list in enumerate(blotDict[1:], 1):
            odds = self.sumOdds(blot_list)
            if odds < lowest_odds[1]:
                lowest_odds = (idx, odds)

        return lowest_odds

    #add all odds values from a blot list dict
    def sumOdds(self, oddsDict):
        total = 0
        for value in oddsDict.values():
            total += value
        return total

    #search for prime clog spots from a moveset
    #will return move that clogs most important spot
    def _searchPrime(self, move_list, threshold):
        potentials = []
        for idx, move in enumerate(move_list):
            if move in GameStrategy.board.clog_list:
                for spot in GameStrategy.board.clog_indices[GameStrategy.board.clog_list.index(move)]:
                    if spot in GameStrategy.board.prime_spots:
                        potentials.append((move, self._calculateClogs(move), GameStrategy.board.prime_spots.index(spot)))
            
        #detect if there are two moves that clog same prime spot, if so, detirmine which moves are safest, then detirmine if that's safe enough (configurable with threshold arg)
        if len(potentials) > 0:
            print('searchPrime potentials: ', potentials)
            all_odds = []
            #perform multisort based upon how many spots we can clog in one move, then based upon importance of spots it clogs
            for moves, _, _ in sorted(potentials, key=lambda x:(-x[1], x[2])):
                if moves in GameStrategy.board.safe_moves:
                    return moves
                elif moves in GameStrategy.board.blot_list:
                    all_odds.append((moves, self.sumOdds(self.blot_odds[GameStrategy.board.blot_list.index(moves)])))
                
            #evaluate all moves that will leave a blot, calculate risk, detirmine if risk is below threshold
            if len(all_odds) > 0:
                print('all_odds: ', all_odds)
                for moveset, odds in sorted(all_odds, key=lambda x:x[1]):
                    if odds < threshold:
                        return moveset

        return None

    #look at move list, return bar move that will be most devestating to opponent
    def devestatingBlot(self, move_list):
        if len(GameStrategy.board.opponent_pips) > 0:
            highest_pip = GameStrategy.board.opponent_pips[0]
            idx_highest = None
            for idx, moveset in enumerate(move_list):
                if moveset in GameStrategy.board.bar_list:
                    bar_idx = GameStrategy.board.bar_list.index(moveset)
                    if idx_highest is not None:
                        if GameStrategy.board.opponent_pips[bar_idx] > highest_pip:
                            highest_pip = GameStrategy.board.opponent_pips[idx]
                            idx_highest = idx
                    else:
                        idx_highest = idx

            if idx_highest is not None:
                return move_list[idx_highest]

        return None

    #looks at a move list, looks at all clogging moves, counts amount of clogs, returns move with most clogs (if any)
    def countClogs(self, moveList):
        potentials = []
        for idx, move in enumerate(moveList):
            clogs = 0
            if move in GameStrategy.board.clog_list:
                clogs += len(GameStrategy.board.clog_indices[GameStrategy.board.clog_list.index(move)])
            if move in GameStrategy.board.unclog_list:
                clogs -= len(GameStrategy.board.unclog_indices[GameStrategy.board.unclog_list.index(move)]) 
            potentials.append((move, clogs))
        
        if len(potentials) > 0:
            potentials.sort(key=lambda x:x[1])
            if potentials[-1][1] > 0:
                return potentials.pop()[0]
        return None

    #analyze our safe moves list
    def checkSafeMoves(self):
        print('checking for safe moves')
        #check for bar moves
        result = self.devestatingBlot(GameStrategy.board.safe_moves)
        if result is not None:
            return result
        #lean towards not unclogging a spot, especially a prime spot with our safe move
        unclogs = []
        for moveset in GameStrategy.board.safe_moves:
            if moveset not in GameStrategy.board.unclog_list:
                print('doing safe move, no unclogging')
                return moveset
            else:
                unclogs.append(moveset)
        leftovers = []
        for moveset in unclogs:
            idx = GameStrategy.board.unclog_list.index(moveset)
            found = False
            for spot in GameStrategy.board.unclog_indices[idx]:
                if spot in GameStrategy.board.prime_spots:
                    print('unclog in safe detected')
                    found = True
            if found is False:
                print('doing safe move with unclogging')
                return moveset
            else:
                leftovers.append(moveset)

        if len(leftovers) > 0:
            print('just doing safe move')
            return leftovers.pop()

        return None

    #check if we have moves to get a blot safe, if so, lean towards a move that clogs most spots (and preferrably no unclogging)
    def getBlotSafe(self, threshold):
        print('seeing if we should get our blot safe')
        all_blots = self.analyzeBlots()
        possibles = []
        safeMoves = []
        #see if one of our safe moves will result in getting a blot safe, prefer getting blots on homeboard/close to homeboard
        for moveset in GameStrategy.board.availableMoves if GameStrategy.board._homeboard == 'br' else reversed(GameStrategy.board.availableMoves):
            for fr, to in moveset:
                if fr in all_blots or to in all_blots:
                    if moveset in GameStrategy.board.safe_moves:
                        safeMoves.append(moveset)
                    elif moveset in GameStrategy.board.blot_list: 
                        possibles.append((moveset, self.sumOdds(self.blot_odds[GameStrategy.board.blot_list.index(moveset)])))

        if len(safeMoves) > 0:
            result = self.devestatingBlot(safeMoves)
            if result is not None:
                return result
            result = self._searchPrime(safeMoves, threshold)
            if result is not None:
                return result
            result = self.countClogs(safeMoves)
            if result is not None:
                return result
            return safeMoves.pop()

        #check that conditions are safer than before with our moves in possibles list
        print('possibles in getBlotSafe: ', possibles)
        if len(possibles) > 0:
            possibles.sort(key=lambda x:x[1])
            lowestOdds = possibles.pop()
            if lowestOdds[1] < self.sumOdds(all_blots):
                return lowestOdds[0]
        return None
            
    #analyze bar list to see if we should put opponent on bar, given the oppurtunity
    def analyzeBarList(self, threshold):
        #iterate through bar list and detirmine if move is safe enough or will be very detrimental to opponent
        if len(GameStrategy.board.bar_list) > 0:
            print('bar list detected')
            potentials = []
            safe = []
            leftovers = []
            #clog a prime spot if we can
            moveset = self._searchPrime(GameStrategy.board.bar_list, threshold)
            if moveset is not None:
                return moveset

            for moveset in GameStrategy.board.bar_list:
                if moveset in GameStrategy.board.clog_list and moveset in GameStrategy.board.safe_moves:
                    potentials.append(moveset)
                elif moveset in GameStrategy.board.safe_moves:
                    safe.append(moveset)
                else:
                    leftovers.append(moveset)

            #if can't clog a prime spot, lean towards putting enemy on bar and clogging spot at same time (if possible)
            #SUGGESTION: do a danger calculation of blots left behind before performing clog bar move
            if len(potentials) > 0:
                #do most devestating move
                print('doing devestating potentials move')
                return self.devestatingBlot(potentials)

            #if spot can't be clogged, do safe move if available
            if len(safe) > 0:
                print('doing safe bar move')
                #we will return most devestating bar move from our safe list
                return self.devestatingBlot(safe)

            #if still no move chosen, just do most devestating move if it's safe enough
            if len(leftovers) > 0:
                print('checking for safe, devestating bar moves')
                new_leftovers = []
                while(len(leftovers) > 0):
                    d_move = self.devestatingBlot(leftovers)
                    if d_move in GameStrategy.board.blot_list:
                        odds = self.blot_odds[GameStrategy.board.blot_list.index(d_move)]
                        total = self.sumOdds(odds)
                        leftovers.remove(d_move)
                        print('blot danger: ', total)
                        if total < threshold:
                            new_leftovers.append(d_move)
                    
                #choose safest, most devestating move 
                if len(new_leftovers) > 0:
                    return self.devestatingBlot(new_leftovers)

        return None

    #calculate and return how many spots a move clogs
    def _calculateClogs(self, moveset):
        clog_len = 0
        if moveset in GameStrategy.board.clog_list:
            clog_len += len(GameStrategy.board.clog_indices[GameStrategy.board.clog_list.index(moveset)]) 
        if moveset in GameStrategy.board.unclog_list:
            clog_len -= len(GameStrategy.board.unclog_indices[GameStrategy.board.unclog_list.index(moveset)])
        return clog_len
    #analyze all clog moves available to us
    def checkClogMoves(self, threshold):
        #iterate through clog_list (if any elements are there)
        print('clog move detected')
        #we will clog a prime spot if we can
        moveset = self._searchPrime(GameStrategy.board.clog_list,threshold)
        if moveset is not None:
            return moveset
        print('analyzing clog moves more in depth')
        #no prime clog spot detected, check if any clog moves will put opponent on bar and any safe moves
        #if still no moves, just do safest clog move that is below threshold
        bar_clogs = []
        multi_clogs = []
        safe_clogs = []
        leftovers = []
        for moveset in GameStrategy.board.clog_list:
            clog_len = self._calculateClogs(moveset)
            #if unclogging a spot, make sure we are not unclogging a primes spot. if so, put into leftovers list
            found = False
            if moveset in GameStrategy.board.unclog_list:
                for spot in GameStrategy.board.unclog_indices[GameStrategy.board.unclog_list.index(moveset)]:
                    if spot in GameStrategy.board.prime_spots:
                        found = True
                        break
                #disregard move if we unclog a prime spot
                if found is True:
                    continue
            if moveset in GameStrategy.board.bar_list:
                bar_clogs.append(moveset)
            elif clog_len > 1:
                multi_clogs.append((moveset, clog_len))
            elif moveset in GameStrategy.board.safe_moves:
                safe_clogs.append(moveset)
            else:
                leftovers.append((moveset, self.sumOdds(self.blot_odds[GameStrategy.board.blot_list.index(moveset)])))
            
        #if we can clog and put opponent on bar, look for most devestating move
        if len(bar_clogs) > 0:
            len_bc = len(bar_clogs)
            while(len_bc > 0):
                d_move = self.devestatingBlot(bar_clogs)
                bar_clogs.remove(d_move)
                len_bc -= 1
                if d_move in GameStrategy.board.blot_list:
                    if self.sumOdds(self.blot_odds[GameStrategy.board.blot_list.index(d_move)]) < threshold:
                        return d_move
                else:
                    return d_move
        #if we can clog multiple spots, we will do if not too dangerous
        if len(multi_clogs) > 0:
            for moveset, _ in sorted(multi_clogs, key=lambda x:x[1]):
                if moveset in GameStrategy.board.blot_list:
                    if self.sumOdds(self.blot_odds[GameStrategy.board.blot_list.index(moveset)]) < threshold:
                        return moveset
                else:
                    return moveset
        #if we can clog safely, we will do so
        if len(safe_clogs) > 0:
            return safe_clogs.pop()

        #if we can clog and does not meet above criteria, will look for safest clog move if it is below our threshold
        if len(leftovers) > 0:
            lowest_odds_move = sorted(leftovers, key=lambda x:x[1])[0]
            if lowest_odds_move[1] < threshold:
                return lowest_odds_move[0]
                
        return None

    #seeing if we can get a man deep behind enemy lines safe or if we should advance him forward
    def checkAdvancing(self, threshold):
        print('checking if we should exit enemy homeboard or start advancing')
        #do lowest danger move
        possible = []
        for moveset in sorted(GameStrategy.board.availableMoves):
            for fr, to in moveset:
                #will check if we should leave homeboard because it wouldn't be too dangerous or if there's a safe way to get out
                if fr in GameStrategy.board.behindSpots:
                    print('checking getting out or advancing')
                    print('moveset: ', moveset)
                    if moveset in GameStrategy.board.blot_list:
                        idx = GameStrategy.board.blot_list.index(moveset)
                        total = self.sumOdds(self.blot_odds[idx])
                        if total < threshold:
                            possible.append((moveset, total))
                    else:
                        possible.append((moveset, 0))

        if len(possible) > 0:  
            print('possibles: ', possible)
            #do lowest odds move, could be getting out or advancing
            return sorted(possible, key=lambda x:x[1])[0][0]

        return None

    #conserve our options for 6's, typically used to keep pieces behind enemy lines longer
    def conserveOptions(self, threshold):
        for moveset in sorted(GameStrategy.board.availableMoves, reverse=False if GameStrategy.board._homeboard == 'br' else True):
            if moveset in GameStrategy.board.blot_list:
                odds = self.sumOdds(self.blot_odds[GameStrategy.board.blot_list.index(moveset)])
                if odds < threshold:
                    #don't leave blot(s) on homeboard if we already have blots on homeboard
                    for spot in GameStrategy.board.blot_indices[GameStrategy.board.blot_list.index(moveset)]:
                        if GameStrategy.board.countPiecesInOpp()[0] > 0:
                            if spot in GameStrategy.board.hb_indices:
                                break
                    print('conserving our options')
                    return moveset
            else:
                print('conserving our options safely')
                return moveset
        return None
class NormalStrategy(GameStrategy):
    THRESHOLD = 20
    def chooseMove(self):
        super().chooseMove()
        result = self.analyzeBarList(NormalStrategy.THRESHOLD)
        if result is not None:
            return result
        #look at current conditions of board, if danger, try to get a blot safe
        if self.currentDanger > 0:
            result = self.getBlotSafe(NormalStrategy.THRESHOLD)
            if result is not None:
                print('doing getBlotSafe move')
                return result
        result = self._searchPrime(GameStrategy.board.clog_list, NormalStrategy.THRESHOLD)
        if result is not None:
            return result
        result = self.checkAdvancing(NormalStrategy.THRESHOLD)
        if result is not None:
            return result
        result = self.checkClogMoves(NormalStrategy.THRESHOLD)
        if result is not None:
            return result
        result = self.checkSafeMoves()
        if result is not None:
            print('doing safeMoves')
            return result
        result = self.conserveOptions(SafeStrategy.THRESHOLD)
        if result is not None:
            return result
        print('just do lowest odds move')
        return self.lowest_list[0]
    
#do less risky moves
class SafeStrategy(GameStrategy):
    THRESHOLD = NormalStrategy.THRESHOLD/1.4
    def chooseMove(self):
        super().chooseMove()
        result = self.getBlotSafe(SafeStrategy.THRESHOLD)
        if result is not None:
            return result
        #check for bar moves
        moveset = self._searchPrime(GameStrategy.board.bar_list,SafeStrategy.THRESHOLD)
        if moveset is not None:
            return moveset
        for idx, moveset in enumerate(GameStrategy.board.bar_list):
            moveset = self.analyzeBarList(SafeStrategy.THRESHOLD)
            if moveset is not None:
                return moveset
        #do less risky checkAdvancing check if we are leading, except if we lead by significant margin, then do more risky check!
        moveset = self.checkAdvancing(SafeStrategy.THRESHOLD if GameStrategy.computer.difference < ComputerPlayer.TRANSITION * 1.5 else AggressiveStrategy.THRESHOLD)
        if moveset is not None:
            return moveset
        moveset = self.checkClogMoves(SafeStrategy.THRESHOLD)
        if moveset is not None:
            return moveset
        #if we are leading by a decent margin and have pieces left behind, perform LateGameStrategy logic to try and get pieces out of enemy territory
        if int(GameStrategy.board.opp_pipcount) - int(GameStrategy.board.team_pipcount) > ComputerPlayer.TRANSITION * 1.5:
            return GameStrategy.computer.lateGameStrat.chooseMove()
        #do default checking of safe moves
        result = self.checkSafeMoves()
        if result is not None:
            return result
        #do lowest odds blot move with minimal risk
        return self.lowest_list[0]
#we are losing, take more risks, although if game is somewhate close, we will be relatively more reasonable with our risks    
class AggressiveStrategy(GameStrategy):
    THRESHOLD = 30
    def chooseMove(self):
        super().chooseMove()
        #look for moves to send enemy to bar
        if len(GameStrategy.board.bar_list) > 0:
            moveset = self.analyzeBarList(AggressiveStrategy.THRESHOLD)
            if moveset is not None:
                return moveset
            
        #game is close, do more sensible moves
        print('difference: ', GameStrategy.computer.difference)
        print('condition: ', ComputerPlayer.TRANSITION*1.5)
        if self.currentDanger > NormalStrategy.THRESHOLD:
            result = self.getBlotSafe(AggressiveStrategy.THRESHOLD)
            if result is not None:
                return result
        if GameStrategy.computer.difference < ComputerPlayer.TRANSITION*1.5:
            moveset = self.checkAdvancing(NormalStrategy.THRESHOLD)
            if moveset is not None:
                return moveset
            moveset = self.checkClogMoves(AggressiveStrategy.THRESHOLD)
            if moveset is not None:
                return moveset
        #we are behind by significant margin, keep our deepest pieces behind enemy lines and conserve our options, if possible
        else:
            moveset = self.conserveOptions(SafeStrategy.THRESHOLD)
            if moveset is not None:
                return moveset
        #look through our blot indices to see if there are any prime spots to leave a blot on, if so, look if danger is below our threshold
        if len(self.new_blot_indices) > 0:
            for idx, spots in enumerate(self.new_blot_indices):
                total_danger = 0
                for odds in self.new_blot_odds[idx]:
                    total_danger += odds
                for spot in spots:
                    if spot in GameStrategy.board.prime_spots:
                        if total_danger < AggressiveStrategy.THRESHOLD:
                            print('leaving blot on prime spot, AggressiveStrategy')
                            return self.lowest_list[idx]
        #no ideal aggressive moves detected, just do safest move
        print('just do lowest odds aggressive move')
        return self.lowest_list[0]
#racing time, select move that balances most pieces in, bearing off, and filling gaps
class RacingStrategy(GameStrategy):
    def chooseMove(self):
        #will 'slice' our _piece_locations dictionary to get just our homeboard data (spot and how many pieces occupying it)
        hb_slice = {spot:len(GameStrategy.board._piece_locations[spot]) for spot in GameStrategy.board.hb_indices}
        #will create a new move history that will be sorted by how many pieces we can bear off, get into homeboard, or move internally
        new_move_history = []
        totalBearOff = 0
        totalInHomeboard = 0
        print('available moves in RacingStrategy: ', GameStrategy.board.availableMoves)
        for moveset in GameStrategy.board.availableMoves:
            #within each moveset, we will count how many moves get a piece into homeboard, and how many moves are moving pieces within homeboard
            beared_off = 0
            pieces_in = 0
            gapFilled = 0
            for fr, to in moveset:
                if fr not in hb_slice and to in hb_slice:
                    pieces_in += 1
                elif fr in hb_slice and to in hb_slice:
                    if hb_slice[to] == 0:
                        gapFilled += 1
                elif to == 25 or to == 0:
                    beared_off += 1
                
            totalBearOff += beared_off
            totalInHomeboard += pieces_in
            new_move_history.append((moveset, beared_off, pieces_in, gapFilled))

        #perform multisort on our new_move_history, based on how many pieces we can bear off, get into homeboard, and move internally
        new_move_history.sort(key=lambda x:(x[1], x[2], x[3]), reverse=True)
        #return move that bears off maximum amount of pieces and gets most pieces in
        return new_move_history[0][0]

#it's a close game and we only have a couple more pieces behind enemy lines, priortize trying to get them out
class LateGameStrategy(GameStrategy):
    def chooseMove(self):
        super().chooseMove()
        #look at our bar move options
        if len(GameStrategy.board.bar_list) > 0:
            moveset = self.analyzeBarList(SafeStrategy.THRESHOLD)
            if moveset is not None:
                return moveset
        #check getting pieces out of enemy homeboard
        moveset = self.checkAdvancing(AggressiveStrategy.THRESHOLD)
        if moveset is not None:
            return moveset
        #if we have any safe moves, prioritize getting pieces out of enemy lines
        if len(GameStrategy.board.safe_moves) > 0:
            for moveset in GameStrategy.board.safe_moves:
                for fr, _ in moveset:
                    if fr in GameStrategy.board.behindSpots:
                        return moveset
        #if no acceptable safe moves, look in blot list for moves that get pieces out of enemy lines, detirmine if move is below danger threshold
        if len(GameStrategy.board.blot_list) > 0:
            possibles = []
            for idx, moveset in enumerate(GameStrategy.board.blot_list):
                for fr, _ in moveset:
                    if fr in GameStrategy.board.behindSpots:
                        odds = self.sumOdds(self.blot_odds[idx])
                        if odds < AggressiveStrategy.THRESHOLD:
                            possibles.append((moveset, odds))
            if len(possibles) > 0:
                return sorted(possibles, key=lambda x:x[1])[0][0]

        #if no acceptable moves found, conserve our options so we might have more choices for where to move our back pieces next turn
        moveset = self.conserveOptions(SafeStrategy.THRESHOLD)
        if moveset is not None:
            return moveset
        print('just do lowest odds LateGame move')
        return self.lowest_list[0]
class ComputerPlayer():
    #instantiate the AI with the orientation of it's homeboard
    def __init__(self, homeboard, board):
        self._homeboard = homeboard
        #we will maintain the game's state in ComputerPlayer class
        self._board = board
        #this instance variable operates as a flag for our recv() method, essentially puts us in a state of taking turns when 'OFF'
        self._state = 'ON'
        self.our_turn = None
        self.phase = None
        self.team_score = 0
        self.opponent_score = 0
        self.repeats = 0
        self.prev = None
        #instantiate all of our Strategies as instance variables of ComputerPlayer
        self.racingStrat = RacingStrategy()
        self.normStrat = NormalStrategy()
        self.aggroStrat = AggressiveStrategy()
        self.safeStrat = SafeStrategy()
        self.lateGameStrat = LateGameStrategy()
        self.difference = 0
        self.isRace = None
        #every Strategy will share this class variable of GameStrategy, for move anaylyzing purposes
        GameStrategy.board = board
        #every Strategy will share this object, so it can have access to the other Strategies through our instance variables
        GameStrategy.computer = self
        
    def connect(self, *args):
        print('here at our connect method')
        self.phase = 'recvname'

    def winningState(self):
        print('AI has won the game')
        self.our_turn = False
        self.team_score += (self._board.isGammon()*self._board.stakes) 
        self.phase = b'stakes'
        self._board.restartGame()
        self.difference = 0
        print('AI score and client score:', self.team_score, self.opponent_score)
            
    def losingState(self):
        print('client has won the game')
        self.opponent_score += (self._board.stakes*self._board.isGammon()) 
        #now we will alert client of their win
        self.phase = b'score' 
        self.our_turn = False
        self._board.restartGame()
        self.difference = 0
        print('AI score and client score:', self.team_score, self.opponent_score)
        
    def sendall(self, *args):
        def transition():
            print('here at transition')
            #if client is blocked on their recv() call, then release them after every sendall() call by the client    
            with mainCondition:
                mainCondition.notify()

            self._state = 'ON'
                
            return
        
        print('sendall current phase: ', self.phase)
        print(self.our_turn)
        print(str(args[0], 'ascii')[0].isdigit())
        #client sends us their username
        if self.phase == 'recvname':
            self.players = [b'us', args[0]]
            self.phase = 'sendorientation'
            print('here at receiving clients username')
        #client sends us their first roll
        elif self.phase == b'first roll':
            result = int(args[0])
            roll = randint(1,6)
            print('result, roll: ', result, roll)
            if result > roll:
                self.phase = b'frwin'
            elif result < roll:
                self.phase = b'frloss'
            else:
                self.phase = b'frtie'

            self.roll = (roll, result)
                
            transition()
       
        #client is sending us the score of the match because we won, will disregard this info since AI calculates this itself
        elif self.phase == b'nextmatch':
            print('client sent us the score (AI perspective')
        elif self.phase == 'contemplating':
            print('client has sent us their answer to AIs doubling proposal', 'args:', args)
            #we will continue game if client accepted doubling proposal and end game if they said no (AI win)
            if str(args[0], 'ascii') == 'N':
                #tell client to increment their doubling cube
                self.phase = b'incre'
                self._board.redrawCube('opp')
            else:
                self.winningState()

            transition()
        elif self.phase == b'rematch':
            print('client has sent us their response to the rematch', 'args:', args)
            if str(args[0], 'ascii') == 'Y':
                self.phase = b'scorereset'
            else:
                self.phase = b'end'

            transition()
        #client said game is over after we sent them our move (AI win), or they surrendered because game is impossible to come back from
        elif str(args[0], 'ascii') == 'Y':
            #haven't tested yet
            print('won the game1')
            self.winningState()

            transition()
         #if client proposes a doubling of the stakes
        elif str(args[0], 'ascii') == 'double':
            print('AI has received doubling proposal')
            #will make sure the game is not about to end, adjust values for end game pipcounts
            if self._doubling('accept') is True:
                print('confirmed accepted')
                self._board.redrawCube('team')
                self.phase = b'incre'
            #will need to end the game as a result of declining proposal here (client win)
            else:
                self.losingState()

            transition()
        #client is sending their dice data, we do nothing with this information
        #we need to check this condition, since the roll being sent will pass the test for suite under this one
        elif self.phase == 'getdice':
            self.phase = b'opproll'
        #client is sending us their move so we will update our board
        elif self.our_turn is False and str(args[0], 'ascii')[0].isdigit():
            print('performing client move:', str(args[0]))
            #client either cannot roll or move
            print('client cannot roll or move check')
            if str(args[0], 'ascii') == '5':
                print('client cannot roll or move here')
                sleep(2)
            self._movePieces(str(args[0], 'ascii'))
            #check if game is over as a result of doing this move on our board, which means ComputerPlayer lost
            if self._board.isGameOver() is True:
                #got here successfully
                print('lost game1')
                self.losingState()

            transition()
       
        print('end of sendAll call')
        
    def recv(self, *args):
        print('CURRENT PHASE:', self.phase)
        print('state: ', self._state)
        if self._state == 'ON':
            if self.phase == self.prev:
                self.repeats += 1
            else:
                self.repeats = 0
                
            if self.repeats == 6:
                raise Exception('erronious conditions')
                
            self.prev = self.phase
            #tell client their homeboard orientation
            if self.phase == 'sendorientation':
                self.phase = 'opp'
                print('here at sending our client their orientation')
                return b'br' if self._homeboard == 'bl' else b'bl'
            #tell client to receive our name
            elif self.phase == 'opp':
                self.phase = 'sendname'
                return b'opp'
            #send client our name
            elif self.phase == 'sendname':
                self.phase = b'first roll'
                return b'DI'
            #tell client it's first roll
            elif self.phase == b'first roll': 
                self._state = 'OFF'
                sleep(2)
                return b'first roll'
            #client won first roll, it is their turn, set our phase to 'senddie'
            elif self.phase == b'frwin':
                self.phase = 'senddie'
                self.our_turn = False
                return b'frwin'
            #first roll was a tie, revert phase back to first roll and tell client it was a tie
            elif self.phase == b'frtie':
                self.phase = b'first roll'
                return b'frtie'
            #client lost the first die roll, tell them they lost and set our phase to 'senddie'
            elif self.phase == b'frloss':
                self.phase = 'senddie'
                self.our_turn = True
                return b'frloss'
            #send client our first die roll result
            elif self.phase == 'senddie':
                if self.our_turn is False:
                    self.phase = b'opproll'
                    self._state = 'OFF'
                else:
                    self.phase = 'taketurn'

                return bytes(f'{self.roll[0]}', 'ascii')
            #time to decide on a move to make, then send to the client
            elif self.phase == 'taketurn':
                self.phase = b'turn'
                #_makeMove() is where AI decides what to do depending on what Strategy it is composed with
                sleep(1)
                return bytes(self._makeMove(), 'ascii')
            #time for AI to roll unless it wants to double or surrender from game being impossible to come back from
            elif self.phase == b'opproll':
                self.isRace = self._board.isRacing()
                if self.isRace is True:
                    canWin = self._board.canWin()
                    print('canWin in AI: ', canWin)
                    #discontinue match if we cannot make a comeback, client wins
                    if canWin is False:
                        self.losingState()
                        self.phase = b'score'
                        return b'test'
                #offer a doubling of the stakes to client if we are winning and difference is significant
                if self._board.cube_location != 'opp' and self._doubling('propose') is True:
                    self.phase = 'contemplating'
                    self._state = 'OFF'
                    self.our_turn = False
                    return b'double'
                self.phase = 'senddice'
                return b'opproll'
            #send our roll to client
            elif self.phase == 'senddice':
                #send client '0,0' if we cannot roll and set phase for client to take their turn, otherwise we will send client our roll and take our turn normally
                if self._board.canRoll() is True:
                    self.phase = 'taketurn'
                    self.roll = [randint(1,6), randint(1,6)]
                    print('AI rolled:', self.roll)
                    return bytes(f'{self.roll[0]},{self.roll[1]}', 'ascii')
                else:
                    self.phase = b'turn'
                    return bytes('0,0', 'ascii')

            #tell client it is their turn
            elif self.phase == b'turn':
                self.phase = 'getdice'
                self.our_turn = False
                self._state = 'OFF'
                return b'turn'
            #tell client they will be receiving their score because they won
            elif self.phase == b'score':
                self.phase = 'willbeopponentscore'
                return b'score'
            #send client their score
            elif self.phase == 'willbeopponentscore':
                self.phase = b'nextmatch'
                return bytes(str(self.opponent_score), 'ascii')
            #tell client to update their board because we won
            elif self.phase == b'stakes':
                self.phase = b'nextmatch'
                return b'stakes'
            #tell client to prepare for their next match, unless one player's points has reached the winning threshold
            elif self.phase == b'nextmatch':
                if self.team_score >= 11 or self.opponent_score >= 11:
                    self.phase = b'rematch'
                    self.team_score = 0
                    self.opponent_score = 0
                else:
                    self.phase =  b'first roll' 
                    
                return b'nextmatch'
            #tell client to increment their doubling cube
            elif self.phase == b'incre':
                print('here at incre')
                self.phase = 'clientcube'
                return b'incre'
            #tell client how orient their doubling cube 
            elif self.phase == 'clientcube':
                print('here at clientcube')
                self.phase = b'turn' if self._board.cube_location == 'team' else b'opproll'
                return b'opp' if self._board.cube_location == 'team' else b'team'
            #game is over, we are asking client if they would like a rematch
            elif self.phase == b'rematch':
                self._state = 'OFF'
                return b'rematch'
            #client has agreed to a rematch, we will tell client to reset their scoreboard
            elif self.phase == b'scorereset':
                self.phase = b'first roll'
                return b'scorereset'
            #client has declined the rematch, we will tell client to end their session
            elif self.phase == b'end':
                print('computer telling game thread to shut down')
                return b'end'
            
        else:
            #blocking client's recv call while they make a decision
            if self.our_turn is False or self.our_turn is None:
                print('got hung up here1')
                with mainCondition:
                    mainCondition.wait()
                return b'test'
           
    #this method will set the phase to tell client to end it's gamethread   
    def close(self):
        self._state = 'ON'
        self.phase = b'end'
        with mainCondition:
            mainCondition.notify()
        
    #socket interface methods 
    def __enter__(self):
        pass
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        #computer might be stuck waiting for opponent to move, notify just in case so program can shutdown gracefully
        with mainCondition:
            mainCondition.notify()
    
    def __repr__(self):
        return 'ComputerPlayer'

    #returns True or False whether ComputerPlayer should accept or propose a doubling offer
    def _doubling(self, criteria):
        teamPips, oppPips, difference = int(self._board.team_pipcount), int(self._board.opp_pipcount), self.difference
        #if we are winning, we will always accept a doubling offer from the client
        if difference < 0 and criteria == 'accept':
            return True 
        #will offer a doubling of the stakes if we are winning by a significant margin
        if criteria == 'propose':
            if difference < 0: 
                newDiff = difference * -1
                if newDiff >= 25:
                    return True
                elif newDiff >= 15 and teamPips < 50 and oppPips < 50:
                    return True
                else:
                    return False
        #we are losing, will see if game is close enough to accept doubling offer from client
        elif criteria == 'accept':
            if (difference < 30 and oppPips > 50) \
            or (difference < 20 and oppPips < 50 and oppPips > 30) \
            or (difference < 10 and oppPips < 30):
                return True
            else:
                return False
               
    
    #move pieces on our board to reflect client's move
    def _movePieces(self, move):
        if len(move) > 1:
            move_args = move.split(':')
            for num, ml in enumerate(move_args):
                move_list = ml.split(',')
                for i in range(0, len(move_list)):
                    move_list[i] = int(move_list[i])
                self._board.movePiece(*move_list[0:2], 1, col=self._board._opponent, barPieces=move_list[2:] if len(move_list) > 2 else None)

        self._board.pipCount()
        self.our_turn = True
    
    #convert our move to data that can be passed to client
    def convertMoveToString(self):
        #pack last move to a form we can send to player
        move_st = ''
        print('sending move to client: ', self._board._last_move)
        for c, ml in enumerate(self._board._last_move):
            t, f, d, bp = ml
            move_st += f'{f},{t}'
            if bp is not None:
                for i in bp:
                    if i != -1:
                        move_st += f',{i}' 
        
            if c != len(self._board._last_move) - 1:      
                move_st += ':'
        
        #refresh our board data everytime we move and send move to player
        self._board.confirm()
        return move_st  
   
    #this variable controls the state transitions between our strategies i.e which strategy will be used for any given turn
    TRANSITION = 20
    #member function for ComputerPlayer to decide move, based on what Strategy is implmented
    #will return string representing which moves we wish to make in form of "from,to:from,to:from,to"
    def _makeMove(self):
        self._board.setDice(*self.roll)
        self._board.analyzeMoves(True)
        #no need to calculate anything if move is forced
        if self._board.isForcedMove is True:
            if len(self._board.move_history) == 0:
                return '5'
            else:
                #reset board's _last_move variable to convertMoveToString can send move to player
                if len(self._board._last_move) > 0:
                    for num, move in enumerate(self._board._last_move):
                        self._board.movePiece(move[1], move[0], col=self._board._team)   
                        
                return self.convertMoveToString()

        #positive difference means WE have the higher pip count
        difference = int(self._board.team_pipcount) - int(self._board.opp_pipcount)
        print('difference: ', difference)
        #factor in how many pieces we have in opponent homeboard compared to client to the difference value
        homePieceInOpp, oppPieceInHome = self._board.countPiecesInOpp()
        factor = (homePieceInOpp - oppPieceInHome) * 10
        print('factor: ', factor)
        #opponent has more pieces in our homeboard than pieces we have in their homeboard, therefore we are winning by larger margin or losing by a smaller margin
        if factor < 0:
            difference -= (factor*-1) 
        #we have more pieces in opponent homeboard than opponent has in our homeboard, therefore we are not winning by as large of margin anymore or losing by larger margin
        elif factor > 0:
            difference += factor
        #set our strategy, based on State Pattern
        #in State Pattern parlance, this method is the context, which will control the state transitions (see suites below)
        strategy = self.normStrat
        #we are winning by a decent margin, play it safe
        if difference < 0 and ((difference * -1) > ComputerPlayer.TRANSITION):
            strategy = self.safeStrat
        #we are losing, time to take risks
        elif difference > ComputerPlayer.TRANSITION:
            strategy = self.aggroStrat
        if self.isRace is True:
            strategy = self.racingStrat
        elif self.isRace is False:
            #if game is close and we only have a couple pieces behind enemy lines, will priotize getting them out with our LateGameStrategy
            if self._board.piecesBehind <= 3 and (strategy is self.normStrat or strategy is self.safeStrat):
                strategy = self.lateGameStrat
        
        print('pieces behind: ', self._board.piecesBehind)
        print('strategy has been set to:', strategy)
        print('team pipcount: ', int(self._board.team_pipcount), 'opp_pipcount: ', int(self._board.opp_pipcount))
        print('difference: ', difference)
        self.difference = difference
        #call strategy's algorithm for deciding a move and perform on our board
        for fr, to in strategy.chooseMove():
            self._board.movePiece(fr, to, dice=1, col=self._board._team)
        #update our board's pipcount, consider calling our board's confirm method here instead
        self._board.pipCount()
        #send move to client
        return self.convertMoveToString()


                    
                    
                    
            
                
                     
                   
    
    
    
    
    
    
    
    
    
    
    