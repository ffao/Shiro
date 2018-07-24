from excepthook import uncaught_exception, install_thread_excepthook
import sys
sys.excepthook = uncaught_exception
install_thread_excepthook()

import boardgen
import getpass
from PIL import Image, ImageDraw, ImageFont
import StringIO
import urllib2, urllib
import json
import random
import traceback
import HTMLParser

unescape = HTMLParser.HTMLParser().unescape

from ChatExchange import chatexchange
import re
import os
import time
import puush
import sqlite3

import requests
from requests.auth import HTTPBasicAuth
from helpers import log, log_exception

imagehost = 'puush'

guessed = []
board = []
shutdown = False
whose_turn = "None"
num_guesses = 0

if 'OTS_User' in os.environ:
    OTS_User = os.environ['OTS_User']
else:
    OTS_User = raw_input("OneTimeSecret User: ")

if 'OTS_Password' in os.environ:
    OTS_Password = os.environ['OTS_Password']
else:
    OTS_Password = raw_input("OneTimeSecret API Key: ")

if 'Puush_API_Key' in os.environ:
    Puush_API_Key = os.environ['Puush_API_Key']
else:
    Puush_API_Key = raw_input("Puush API Key: ")

pinned_message_blue = None
pinned_message_red = None
blue = []
red = []

def main():
    global room, my_user
    init('0')
    init_whitelist()
    init_pinglist()

    host_id = 'stackexchange.com'
    room_id = '59120'  # Codenames

    if 'ChatExchangeU' in os.environ:
        email = os.environ['ChatExchangeU']
    else:
        email = raw_input("Email: ")
    if 'ChatExchangeP' in os.environ:
        password = os.environ['ChatExchangeP']
    else:
        password = getpass.getpass("Password: ")

    client = chatexchange.client.Client(host_id)
    client.login(email, password)
    my_user = client.get_me()

    room = client.get_room(room_id)
    room.join()
    room.watch(on_message)

    log('info', "(You are now in room #%s on %s.)" % (room_id, host_id))
    while not shutdown:
        message = raw_input("<< ")
        
    client.logout()

passphrases = ["[passing]","[pass]"] #stuff that indicates somebody is passing
TRUSTED_USER_IDS = [200996, 233269, 209507, 238144, 263999, 156773, 69330, 190748, 155240, 56166, 251910, 17335, 240387, 21351, 188759, 174589, 254945, 152262, 207333, 215298, 147578, 242914, 217429, 147578]
PING_NAMES = ['ffao']

def init_whitelist():
    global TRUSTED_USER_IDS
    db = sqlite3.connect('temp.db')
    
    results = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='whitelist'");
    if not results.fetchall():
        db.execute('CREATE TABLE whitelist (ID int)')
        db.commit()
        db.close()

        db = sqlite3.connect('temp.db', isolation_level=None)
        db.executemany('INSERT INTO whitelist (ID) values (?)', [(x,) for x in TRUSTED_USER_IDS])
        db.commit()
    else:
        results = db.execute("SELECT * FROM whitelist")
        TRUSTED_USER_IDS = [x[0] for x in results.fetchall()]
        log('debug', "TRUSTED: " + str(TRUSTED_USER_IDS))

    db.close()

def init_pinglist():
    global PING_NAMES
    db = sqlite3.connect('temp.db')
    
    results = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pinglist'");
    if not results.fetchall():
        db.execute('CREATE TABLE pinglist (name text)')
        db.commit()
        db.close()

        db = sqlite3.connect('temp.db', isolation_level=None)
        db.executemany('INSERT INTO pinglist (name) values (?)', [(x,) for x in PING_NAMES])
        db.commit()
    else:
        results = db.execute("SELECT * FROM pinglist")
        PING_NAMES = [x[0] for x in results.fetchall()]
        log('debug', "PINGABLE: " + str(PING_NAMES))

    db.close()

def add_whitelist(msg):
    ID = int(msg.split(None, 1)[1])
    TRUSTED_USER_IDS.append(ID)

    db = sqlite3.connect('temp.db')
    db.execute('INSERT INTO whitelist (ID) values (?)', (ID,))
    db.commit()
    db.close()

def add_pinglist(msg, name=None):
    if name is None:
        name = unescape(msg.split(None, 1)[1]).strip()
    room.send_message("Adding {} to the pinglist.".format(name))
    PING_NAMES.append(name)

    db = sqlite3.connect('temp.db')
    db.execute('INSERT INTO pinglist (name) values (?)', (name,))
    db.commit()
    db.close()

def remove_pinglist(msg, name=None):
    if name is None:
        name = unescape(msg.split(None, 1)[1]).strip()
    room.send_message("Removing {} from the pinglist.".format(name))
    PING_NAMES.remove(name)

    db = sqlite3.connect('temp.db')
    db.execute('DELETE FROM pinglist WHERE name = ?', (name,))
    db.commit()
    db.close()

def cooldown(seconds):
    def inner(fn):
        def ret_fn(*args, **kwargs):
            if time.time() > ret_fn.last_time_stamp + seconds:
                fn(*args, **kwargs)
                ret_fn.last_time_stamp = time.time()

        ret_fn.last_time_stamp = 0
        return ret_fn
    return inner

def on_message(message, client):
    global shutdown, whose_turn, num_guesses, red, blue
    if not isinstance(message, chatexchange.events.MessagePosted):
        # Ignore non-message_posted events.
        return

    is_shiro = (message.user.id == my_user.id)
    is_super_user = (is_shiro or message.user.id == 200996 or message.user.is_moderator)
    is_trusted_user = (is_super_user or message.user.id in TRUSTED_USER_IDS)

    #print("")
    #print(">> (%s / %s) %s" % (message.user.name, repr(message.user.id), message.content))

    try:
        clue_pattern = re.compile(r"(?:Red|Blue): <b>.+\s*\((\d+|unlimited|\u221e)\)</b>", re.IGNORECASE) #Strange things happening with this pattern
        clue_match = re.match(clue_pattern, message.content)

        if not is_shiro and clue_match is not None and ((whose_turn == "SMRed" and message.user.name == red[0]) or (whose_turn == "SMBlue" and message.user.name == blue[0])):
            clue = clue_match.groups()[0].strip().lower()
            #print("Matched clue: %s" % (clue))
            if clue.isdigit() and int(clue) > 0:
                num_guesses = int(clue) + 1
            else:
                num_guesses = 100
            toggle_turn()

        #print("num guesses: %s" % (num_guesses))
            
        pat = re.compile(r"\s*<b>(.*)</b>\s*", re.IGNORECASE)
        guess_match = re.match(pat, message.content)

        if not is_shiro and guess_match is not None and ((whose_turn == "Red" and message.user.name in red[1:]) or (whose_turn == "Blue" and message.user.name in blue[1:])):
            guess = guess_match.groups()[0].strip().lower()
            if guess in passphrases:
                show_board()
                toggle_turn()
            else:
                process_guess(guess.upper())
                
        if is_shiro and message.content.strip().startswith("<b>RED</b>:"):
            pin_red(message.message)

        if is_shiro and message.content.strip().startswith("<b>BLUE</b>:"):
            pin_blue(message.message) 
            
        if is_trusted_user and message.content.lower().strip() == "!teams":
            show_teams()

        if is_trusted_user and message.content.lower().strip() == "!board":
            show_board()

        if is_trusted_user and message.content.lower().strip() == "!flipcoin":
            flip_coin()
            
        if is_trusted_user and message.content.lower().strip() == "!blame":
            blame()

        if is_trusted_user and message.content.lower().strip() == "!recall":
            recall()

        if is_trusted_user and message.content.lower().startswith("!join"):
            add_user(message.content, message.user.name)
        elif message.content.lower().strip() == "!join":
            add_user(message.content, message.user.name)

        if is_trusted_user and message.content.lower().startswith("!leave"):
            remove_user(message.content, message.user.name)
        elif message.content.lower().strip() == "!leave":
            remove_user(message.content, message.user.name)

        if is_trusted_user and message.content.lower().startswith("!newgame"):
            new_game(message.content)

        if is_super_user and message.content.lower().startswith("!whitelist"):
            add_whitelist(message.content)
        
        if is_trusted_user and message.content.lower().strip() == "!finalboard":
            show_final()

        if is_super_user and message.content.lower().startswith("!imagehost"):
            change_host(message.content)

        if is_trusted_user and message.content.lower().startswith("!seed"):
            try:
                new_seed = message.content[6:]
                init(new_seed)
                show_board()
            except:
                pass

        if is_super_user and message.content.lower().strip() == "!shutdown":
            shutdown = True

        if is_super_user and message.content.lower().strip() == "!ping":
            ping()
            
        if message.content.lower().strip() == "!help":
            info()

        if is_trusted_user and message.content.lower().strip() == "!pingable":
            add_pinglist(message.content, message.user.name.replace(" ", ""))
        elif is_super_user and message.content.lower().startswith("!pingable"):
            add_pinglist(message.content)

        if is_trusted_user and message.content.lower().strip() == "!notpingable":
            remove_pinglist(message.content, message.user.name.replace(" ", ""))
        elif is_super_user and message.content.lower().startswith("!notpingable"):
            remove_pinglist(message.content)

        if is_trusted_user and message.content.lower().startswith("!pinglist"):
            pinglist()

        if is_trusted_user and (message.content.lower().startswith("!who") or message.content.lower().strip() == "!guesses"):
            #print(whose_turn)
            if whose_turn == "Red" or whose_turn == "Blue":
                room.send_message("%s currently has %s guesses remaining." % (whose_turn, num_guesses if num_guesses < 25 else "unlimited"))
            elif whose_turn[:2] == "SM":
                room.send_message("We are currently waiting for a clue from the %s spymaster." % (whose_turn[2:]))

    except:
        log_exception(*sys.exc_info())
        #traceback.print_exc()
        #print ""

def process_guess(guess):
    global whose_turn, num_guesses
    condolences = ["Oh, dear.\n", "That's too bad.\n", "I feel for you.\n", "What were you thinking?\n", "Uh... what?\n", "Maybe you'll do better next time.\n", "Seriously?\n", "I hope you feel okay about that.\n", "When will you learn?\n"]
    if guess in board[1]:
        guessed.append( guess.lower() )
        message = guess
        new_turn = False
        guess_color = board[2][board[1].index(guess)]
        if guess_color == "#00eeee":
            message += " is Blue\n"
            if whose_turn == "Red":
                new_turn = True
                message += random.choice(condolences)
            elif whose_turn == "Blue":
                num_guesses -= 1
                if num_guesses == 0:
                    message += "You are out of guesses. "
                    new_turn = True
        elif guess_color == "#ff0000":
            message += " is Red\n"
            if whose_turn == "Blue":
                new_turn = True
                message += random.choice(condolences)
            elif whose_turn == "Red":
                num_guesses -= 1
                if num_guesses == 0:
                    message += "You are out of guesses. "
                    new_turn = True
        elif guess_color == "#ffff00":
            message += " is Yellow (neutral)\n"
            new_turn = True
        elif guess_color == "#808080":
            message += " is Black (assassin!).\nGame over. "
            if whose_turn == "Blue":
                message += "Red wins!"
            elif whose_turn == "Red":
                message += "Blue wins!"
            show_final()
        
        if new_turn:
            if whose_turn == "Blue":
                message += "It is now Red's turn"
            elif whose_turn == "Red":
                message += "It is now Blue's turn"
            toggle_turn()
            
        room.send_message(message)
        if new_turn:
            show_board()
        
    else:
        room.send_message("%s doesn't appear to be on the board..." % (guess.upper()))

        
def flip_coin():
    room.send_message(random.choice(["Red", "Blue"]))
    
def blame():
    global red, blue
    room.send_message("It's %s's fault." % (random.choice(red + blue)))

def change_host(msg):
    global imagehost

    pieces = msg.lower().split()
    if len(pieces) >= 2:
        new_host = pieces[1].strip()
        if new_host in ['imgur', 'puush']: imagehost = new_host
            
def info():
    room.send_message("Hello! I'm Shiro, a bot to help with the game Codenames. To see the rules and a list of commands that you can use, see [this answer on Puzzling Meta](https://puzzling.meta.stackexchange.com/a/5989). Have fun!")

def new_game(msg):
    global red, blue, whose_turn
    players = None

    try:
        players = [unescape(x).strip() for x in msg[8:].split(",")]
    except Exception, e:
        return

    red = []
    blue = []

    log('info', 'New game is starting!')
    log('debug', "players: {}".format(players))
    if players is not None and len(players) >= 2:
        spymasters = players[:2]
        random.shuffle(spymasters)

        red = [spymasters[0]]
        blue = [spymasters[1]]

        players = players[2:]
        n = len(players) / 2
        for x in xrange(n):
            who = random.randrange(len(players))
            red.append(players.pop(who))
        for x in xrange(n):
            who = random.randrange(len(players))
            blue.append(players.pop(who))

        if players:
            if random.randrange(2):
                red.append(players[0])
            else:
                blue.append(players[0])

        room.send_message("**RED**: *%s*, %s" % (red[0], ', '.join(red[1:])))
        room.send_message("**BLUE**: *%s*, %s" % (blue[0], ', '.join(blue[1:])))
        time.sleep(2)

    seed = str(random.randint(1, 1000000000))

    my_message = '''RED spymaster only, please click on this link to see the seed: %s
BLUE spymaster only, please click on this link to see the seed: %s

Please save the seed somewhere! As a last resort if any of you happens to forget the seed, you can type !recall to get a new link.'''

    room.send_message(my_message % (submit_secret(seed), submit_secret(seed)))

    init(seed)
    if board[0]=="#00eeee":
        room.send_message("BLUE goes first!")
        whose_turn = "SMBlue"
    elif board[0]=="#ff0000":
        room.send_message("RED goes first!")
        whose_turn = "SMRed"
    show_board()


def add_user(content, name):
    global red, blue

    if not red or not blue:
        room.send_message("Sorry, I don't have any teams stored right now!")
        return

    segments = content.strip().split(None, 1)
    if len(segments) == 1:
        joining_user = name
    else:
        joining_user = unescape(segments[1]).strip()

    dest_color = ''
    if content.lower().strip().startswith("!joinred"):
        dest_color = 'red'
    elif content.lower().strip().startswith("!joinblue"):
        dest_color = 'blue'
    else:
        if len(red) != len(blue):
            dest_color = 'red' if len(red) < len(blue) else 'blue'
        else:
            dest_color = random.choice(['red', 'blue'])
        room.send_message("Hi %s, you'll be joining team %s!" % (joining_user, dest_color))

    if dest_color == 'red':
        red.append(joining_user)
        room.send_message("**RED**: *%s*, %s" % (red[0], ', '.join(red[1:])))
    else:
        blue.append(joining_user)
        room.send_message("**BLUE**: *%s*, %s" % (blue[0], ', '.join(blue[1:])))

def remove_user(content, name):
    global red, blue

    if not red or not blue:
        room.send_message("Sorry, I don't have any teams stored right now!")
        return

    segments = content.strip().split(None, 1)
    if len(segments) == 1:
        leaving_user = name
    else:
        leaving_user = unescape(segments[1]).strip()

    if leaving_user in red[1:]:
        red.reverse()
        red.remove(leaving_user)
        red.reverse()
        room.send_message("**RED**: *%s*, %s" % (red[0], ', '.join(red[1:])))
    if leaving_user in blue[1:]:
        blue.reverse()
        blue.remove(leaving_user)
        blue.reverse()
        room.send_message("**BLUE**: *%s*, %s" % (blue[0], ', '.join(blue[1:])))

def recall():
    room.send_message("To view the current seed, click this link: %s" % submit_secret(seed))

def init(_seed):
    global seed, guessed, board
    seed = _seed
    guessed = []
    board = get_board(seed)

@cooldown(10)
def show_board():
    solved = []
    for idx, x in enumerate(board[1]):
        if x.lower().strip() in guessed:
            solved.append(idx)
    print 'drawing grid'
    im = draw_grid(seed, solved)
    print 'sending message'
    time.sleep(3)
    room.send_message( upload_image(im) )

@cooldown(10)
def ping():
    room.send_message( " ".join('@'+x for x in PING_NAMES) )

@cooldown(10)
def pinglist():
    room.send_message( " ".join(x for x in PING_NAMES) )

@cooldown(10)
def show_final():
    solved = range(25)
    '''Past code, in case this doesn't work for some reason:
    solved = []
    for idx, x in enumerate(board[1]):
        solved.append(idx)
        '''
    print 'drawing grid'
    im = draw_grid(seed, solved)
    print 'sending message'
    time.sleep(3)
    room.send_message( upload_image(im) )

def get_board(seed):
    board = boardgen.createNewGame(seed).split(',')
    
    print board
    return board[0], board[1:26], board[26:51]

def draw_grid(seed, solved):
    WIDTH = 500
    GRID_TOTAL_WIDTH = 500
    GRID_WIDTH = GRID_TOTAL_WIDTH / 5
    HEIGHT = 330
    GRID_TOTAL_HEIGHT = 300
    GRID_HEIGHT = GRID_TOTAL_HEIGHT / 5

    y_offset = HEIGHT - GRID_TOTAL_HEIGHT

    font = ImageFont.truetype("ariblk.ttf", 12)
    lfont = ImageFont.truetype("ariblk.ttf", 16)
    image1 = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255) )
    draw = ImageDraw.Draw(image1)
    
    blues = 0 #number of blues guessed
    reds = 0  #number of reds guessed
    #print board
    for x in xrange(5):
        for y in xrange(5):
            if x*5+y in solved:
                #print 'color: ', board[2][x*5+y]
                draw.rectangle([x*GRID_WIDTH, y_offset + y*GRID_HEIGHT, (x+1)*GRID_WIDTH, y_offset + (y+1)*GRID_HEIGHT], fill=board[2][x*5+y])
                if board[2][x*5+y]=="#00eeee":
                    blues+=1
                if board[2][x*5+y]=="#ff0000":
                    reds+=1
    
    bluesremaining = 8-blues
    redsremaining = 8-reds
    if board[0] == "#00eeee":
        bluesremaining += 1
    else:
        redsremaining += 1
    #I'm not 100% confident with the draw tools so somebody else can do them if they want

    for x in xrange(GRID_WIDTH, WIDTH, GRID_WIDTH):
        draw.line([x, y_offset, x, HEIGHT], (0,0,0))
    for y in xrange(0, HEIGHT, GRID_HEIGHT):
        draw.line([0, y + y_offset, GRID_TOTAL_WIDTH, y + y_offset], (0,0,0))

    for x in xrange(5):
        for y in xrange(5):
            word = board[1][x*5+y]

            size = draw.textsize(word, font=font)
            draw.text((x * GRID_WIDTH + GRID_WIDTH/2 - size[0]/2, y_offset + y * GRID_HEIGHT + GRID_HEIGHT/2 - size[1]/2), word, (0,0,0), font=font)

    draw.text((70,1), "RED: %s remaining" % redsremaining, (255,0,0), font=lfont)
    draw.text((270,1), "BLUE: %s remaining" % bluesremaining, (0,0,255), font=lfont)
    
    output = StringIO.StringIO()
    image1.save(output, format='png')
    
    return output.getvalue()

def pin_red(msg):
    global pinned_message_red
    if pinned_message_red is not None:
        try:
            pinned_message_red._client._br.edit_message(pinned_message_red.id, "**RED**: *%s*, %s" % (red[0], ', '.join(red[1:])))
            return
        except:
            pinned_message_red.cancel_stars()
    msg.pin()
    pinned_message_red = msg

def pin_blue(msg):
    global pinned_message_blue
    if pinned_message_blue is not None:
        try:
            pinned_message_blue._client._br.edit_message(pinned_message_blue.id, "**BLUE**: *%s*, %s" % (blue[0], ', '.join(blue[1:])))
            return
        except:
            pinned_message_blue.cancel_stars()
    msg.pin()
    pinned_message_blue = msg

def upload_image(im):
    if imagehost == 'puush':
        try:
            return upload_puush(im)
        except:
            print 'Failed to upload puush image! Falling back to imgur...'
    return upload_imgur(im)

def upload_imgur(im):
    data = urllib.urlencode([('image', im)])
    req = urllib2.Request('https://api.imgur.com/3/image', data=data, headers={"Authorization": "Client-ID 44c2dcd61ab0bb9"})
    return json.loads(urllib2.urlopen(req).read())["data"]["link"]

def upload_puush(im):
    im = StringIO.StringIO(im)
    im.name = 'temp.png'
    account = puush.Account(Puush_API_Key)
    f = account.upload(im)
    return f.url

def submit_secret(secret):
    data = {'secret': secret}
    r = requests.post('https://onetimesecret.com/api/v1/share', data=data, auth=HTTPBasicAuth(OTS_User, OTS_Password))
    return 'https://onetimesecret.com/secret/' + r.json()['secret_key']

def show_teams():
    global red,blue
    room.send_message("**RED team**: *%s*, %s" % (red[0], ', '.join(red[1:])))
    room.send_message("**BLUE team**: *%s*, %s" % (blue[0], ', '.join(blue[1:])))

def toggle_turn():
    global whose_turn
    if whose_turn == "Blue":
        whose_turn = "SMRed"
        num_guesses = 0
    elif whose_turn == "SMRed":
        whose_turn = "Red"
    elif whose_turn == "Red":
        whose_turn = "SMBlue"
        num_guesses = 0
    elif whose_turn == "SMBlue":
        whose_turn = "Blue"

main()
