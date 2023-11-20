from socketserver import BaseRequestHandler, TCPServer, ThreadingMixIn
import threading
import sys
import time
import traceback

#shared data between client connection threads
activeClients = []
first_rolls = []
client_moves = []
client_rolls = []
match_winner = []
scoreboard = [0,0]
#multiple threads will be accessing and mutating shared data, ensure only thread at a time can do this
thread_lock = threading.Lock() 
#the barrier used to wait for two threads to get to that point before Handler executes beyond that point
barrier = threading.Barrier(2)
#this condition is used by main thread, will block main execution until client thread says it's time to shut down server
mainCondition = threading.Condition()
#client threads will use this Condition object to coordinate flow of the game
gameCondition = threading.Condition()

class GameError(Exception):
    pass

class ThreadedTCPServer(ThreadingMixIn, TCPServer):
    pass

class GameHandler(BaseRequestHandler): 
    turn_client = None
       
    def handle(self):
        try:
            #will receive client's username right after connection, add to list and wait for two clients to connect
            print('Got connection from', self.client_address)
            username = self.request.recv(9)
            #kill thread if more than two clients attempt to connect during one game session
            #also tell 'extra' client to kill their socket connection
            with thread_lock:
                if len(activeClients) >= 2:
                    self.request.sendall(b'bl')
                    time.sleep(1)
                    self.request.sendall(b'end')
                    sys.exit()
                else:
                    activeClients.append(username)
                print(activeClients)
                #find out index of opponent's name in activeClients list
                idx = None
                idx = len(activeClients)-1
                idx = 0 if idx == 1 else 1
                #tell client to set up their board depending on their index in activeClients
                if idx == 0:
                    self.request.sendall(b'br')
                else:
                    self.request.sendall(b'bl')
            #blocking code to wait for two threads to arrive at this point
            print(str(barrier.n_waiting))
            while(True):
                try:
                    print('waiting for other client connection iteration')
                    barrier.wait(timeout=5)
                    break
                except threading.BrokenBarrierError as be:
                    print(be)
                    barrier.reset()
                    self.request.sendall(b'test')
                        
            #send clients name of their opponents to update their GUI
            with thread_lock:
                #if usernames are the same, second client will have a '1' appended to their name
                if activeClients[0] == activeClients[1]:
                    activeClients[1] = username + b'1'
                    if idx == 0:
                        username = activeClients[1]
                
                self.request.sendall(b'opp')
                time.sleep(1)       
                self.request.sendall(activeClients[idx])
                
            time.sleep(1) 
            print('active clients:', activeClients) 
            #start the main game loop
            while(True):          
                #now ask clients to roll one die, keep asking until both user roll different numbers
                while(True):
                    self.request.sendall(b'first roll')
                    fr_result = self.request.recv(1)
                    sender = self.request.recv(9)
                    fr_t = (fr_result, sender)
                    with thread_lock:
                        first_rolls.append(fr_t)
                        #if repeating first rolls, delete the first two items in list
                        if len(first_rolls) > 2:
                            del first_rolls[0:2]
                    #wait for opponent to submit their first roll data, timeout from wait() every 20 seconds 
                    while(True):
                        try:
                            print('wait iteration for thread')
                            barrier.wait(timeout=5)
                            break
                        except threading.BrokenBarrierError as be:
                            print(be)
                            barrier.reset()
                            self.request.sendall(b'test')
                            with thread_lock:
                                if len(activeClients) != 2:
                                    raise GameError('player has left, must restart')
                                    
                    with thread_lock:        
                        fr1, fr2 = first_rolls[0][0], first_rolls[1][0]
                        if fr1 == fr2:
                            self.request.sendall(b'frtie')
                            time.sleep(2)
                        elif fr1 > fr2:
                            turn_client = first_rolls[0][1]
                            break
                        elif fr1 < fr2:
                            turn_client = first_rolls[1][1]
                            break
                
                time.sleep(2)      
                move_count = 0
                #start game loop of taking turns until a player wins or gives up
                while(True):
                    with thread_lock:
                        if len(activeClients) < 2:
                            raise GameError('other player has left the game') 
                                                  
                    print('Turn client:', str(turn_client, 'ascii'), 'username:', username)
                    if username == turn_client:
                        if move_count > 0:
                            self.request.sendall(b'turn')
                            move = self.request.recv(6)
                            #consider a pause here in the event the client cannot roll, will send 0,0 as their roll fairly quickly
                            if move != b'double':
                                client_rolls.append(move)
                                with gameCondition:
                                    gameCondition.notify()
                                    
                                move = self.request.recv(40)
                                client_moves.append(move)
                                
                            else:
                                client_moves.append(move)
                                with gameCondition:
                                    gameCondition.notify()
                                  
                            time.sleep(1)
                        else:
                            self.request.sendall(b'frwin')
                            time.sleep(1)
                            fr = first_rolls[0][0] if first_rolls[1][1] == turn_client else first_rolls[1][0]
                            self.request.sendall(fr)
                            move = self.request.recv(40)
                            client_moves.append(move)
                    else:
                        if move_count == 0:
                            self.request.sendall(b'frloss')
                            time.sleep(1)
                            fr = first_rolls[0][0] if first_rolls[1][1] == username else first_rolls[1][0]
                            self.request.sendall(fr)
                                
                        else: 
                            with gameCondition:
                                gameCondition.wait() 
                            
                            if len(client_rolls) > 0:   
                                self.request.sendall(b'opproll')
                                time.sleep(1)
                                self.request.sendall(client_rolls[0])  
                                
                            with thread_lock:
                                if len(activeClients) < 2:
                                    raise GameError('other player has left the game')     
                        
                               
                        with gameCondition:
                            gameCondition.wait()
                       
                            
                        first_rolls.clear()
                        client_rolls.clear()
                    
                    if username == turn_client:       
                        with gameCondition:
                            gameCondition.notify()
                            
                    #make sure clients are still here before we start next turn loop    
                    while(True):
                        try:
                            print('wait iteration before notifying other ')
                            barrier.wait(timeout=5)
                            break
                        except threading.BrokenBarrierError as be:
                            print(be)
                            barrier.reset()
                            self.request.sendall(b'test')
                            with thread_lock:
                                if len(activeClients) != 2:
                                    raise GameError('player has left, must restart')
                    #both threads need to adjust whose turn it is now
                    #also tell other client what the move was
                    last_move = client_moves[len(client_moves)-1]
                    if username != turn_client:
                        self.request.sendall(last_move)
                        #only adjust whose turn it is if last move was not a double proposal
                        if last_move != b'double':
                            turn_client = username
                        isOver = self.request.recv(1)
                        time.sleep(1)
                        #if client tells us game is now over, break from loop
                        #can deal with doubling here!!!
                        if isOver == b'N':
                            pass
                        else:
                            break
                        print(username, 'has received the move/doubling proposal')
                    else:
                        if last_move != b'double':
                            turn_client = activeClients[0] if activeClients[0] != username else activeClients[1]
                        print(username, 'is waiting waiting for other player to receive their move')
                        with gameCondition:
                            gameCondition.wait()
                        
                        #winner of match has been detirmined, time to break from main game loop   
                        if len(match_winner) > 0:
                            break
                            
                    if (username == turn_client and last_move != b'double') or (username != turn_client and last_move == b'double'):
                        print(username, 'has notified other player that the move has been received')
                        with gameCondition:
                            gameCondition.notify()
                    
                    #will only reach this suite if double proposal has been accepted, will adjust cube on clients' boards       
                    if last_move == b'double':
                        self.request.sendall(b'incre')
                        time.sleep(1)
                        if username == turn_client:
                            self.request.sendall(b'opp')
                        else:
                            self.request.sendall(b'team')
                          
                    move_count += 1
                
                with thread_lock:
                    if len(activeClients) < 2:
                        raise GameError('other player has left the game')   
                #loser of the game always breaks from main game loop first, must notify winner to quit waiting
                #loser thread will also calculate score of match by asking client for the stakes of the match
                if len(match_winner) == 0:
                    #consider a little wait here or move wait on suite before thread gets here (has received doubling proposal)
                    move_count = 0
                    match_winner.append(activeClients[0] if username != activeClients[0] else activeClients[1])
                    self.request.sendall(b'stakes')
                    stakes = int(self.request.recv(2))
                    #loser thread will update the scoreboard
                    if username == activeClients[0]:
                        scoreboard[1] += stakes
                    else:
                        scoreboard[0] += stakes
                    with gameCondition:
                        gameCondition.notify()
                
                #repeat the main game loop again if either player's score does not equal 11
                #if game is over (11 or more points), then tell clients who the winner is, ask for rematch, and restart their GUI if they wish to rematch
                print('match winner:', match_winner)
                print('scoreboard', scoreboard)
                if username == match_winner[0]:
                    client_moves.clear()
                    move_count = 0
                    self.request.sendall(b'score')
                    time.sleep(1)
                    match_winner.clear()
                    player_score = str(scoreboard[0]) if idx == 1 else str(scoreboard[1])
                    self.request.sendall(bytes(player_score, 'ascii'))
                    
                if scoreboard[0] < 11 and scoreboard[1] < 11:
                    print(username, 'is going into next iteration of main game loop')
                    self.request.sendall(b'nextmatch')
                    time.sleep(1)
                else:
                    print('game is over!!')
                    #ask each player if they would like a rematch, if not shut thread down
                    self.request.sendall(b'rematch')
                    answer = self.request.recv(1)
                    if answer == b'N':
                        self.request.sendall(b'end')
                        raise ConnectionAbortedError('player declined the rematch')
                    else:
                        time.sleep(1)
                        self.request.sendall(b'nextmatch')
                        time.sleep(1)
                        self.request.sendall(b'scorereset')
                        #reset scoreboard for next game
                        with thread_lock:
                            scoreboard[0] = 0
                            scoreboard[1] = 0
                        #wait for both threads to accept rematch
                        #if only one thread accepts, then we will tell accepting thread to restart server
                        while(True):
                            try:
                                print('wait iteration for rematch')
                                barrier.wait(timeout=5)
                                break
                            except threading.BrokenBarrierError as be:
                                print(be)
                                barrier.reset()
                                self.request.sendall(b'test')
                                with thread_lock:
                                    if len(activeClients) != 2:
                                        raise GameError('player has left, must restart')
                                    
            
        
        #server must restart because our opponent has left, reset state and alert player to restart their GUI      
        except GameError as ge:
            print('handling a player leaving')
            print(type(ge))
            first_rolls.clear()
            activeClients.clear()
            client_moves.clear()
            client_rolls.clear()
            match_winner.clear()
            scoreboard[0] = 0
            scoreboard[1] = 0
            barrier.reset()
            try:
                self.request.sendall(b'restart')
            except Exception as e:
                print(type(e))
                print('couldn\'t tell player to restart')
                with mainCondition:
                    mainCondition.notify()
                sys.exit()
                
            self.handle()
        #a player has disconnected, remove their name from our active clients list
        #will occur if player exits their game or we send them 'end' message, or any Exception that occurs!
        #will probably turn this suite into a GroupException check for all connection Exceptions (and possibly SystemExit)
        except Exception as ce:
            print(type(ce))
            print(traceback.format_exc())
            with thread_lock:
                activeClients.remove(username)
                if len(activeClients) == 0:
                    print('turning on shutdown variable')
                    with mainCondition:
                        mainCondition.notify()
            print(username, 'has disconnected from the game')
            print(activeClients)
            with gameCondition:
                gameCondition.notify()
            sys.exit()
        
            
serv = ThreadedTCPServer(('localhost', 20000), GameHandler)
with serv:
    #Seperate thread for server and starts new thread for each request because of ThreadingMixIn class
    server_thread = threading.Thread(target=serv.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    #one of our handler threads will notify us when to shut server down
    with mainCondition:
        mainCondition.wait()
    serv.shutdown()
    
print('main thread in server script has executed')
    

