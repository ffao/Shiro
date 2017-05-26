import PyV8
import getpass
from PIL import Image, ImageDraw, ImageFont
import StringIO
import urllib2, urllib
import json
import random

import chatexchange.client
import chatexchange.events
import re
import sys
import os
import time

guessed = []
board = []
ctxt = PyV8.JSContext()
ctxt.enter()
ctxt.eval(open("boardgen.js").read())
shutdown = False

def main():
    global room
    init('0')

    host_id = 'stackexchange.com'
    room_id = '59120'  # Sandbox

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

    room = client.get_room(room_id)
    room.join()
    room.watch(on_message)

    print("(You are now in room #%s on %s.)" % (room_id, host_id))
    while not shutdown:
        message = raw_input("<< ")
        room.send_message(message)

    client.logout()

TRUSTED_USER_IDS = [200996, 209507, 238144, 263999, 156773, 69330, 190748, 155240, 56166, 251910, 17335, 240387, 21351]

def on_message(message, client):
    global shutdown
    if not isinstance(message, chatexchange.events.MessagePosted):
        # Ignore non-message_posted events.
        return

    is_trusted_user = (message.user.id in TRUSTED_USER_IDS)

    print("")
    #print(">> (%s / %s) %s" % (message.user.name, repr(message.user.id), message.content))

    pat = re.compile("(guess)?:?\s*<b>(.*)</b>\s*", re.IGNORECASE)
    m = re.match(pat, message.content)
    if m is not None:
        guess = m.groups()[1].strip()
        guessed.append( guess.lower() )

    if is_trusted_user and message.content.lower().strip() == "!board":
        show_board()

    if message.content.lower().strip() == "!undo":
        guessed.pop()

    if is_trusted_user and message.content.lower().startswith("!newgame"):
        new_game(message.content)

    if is_trusted_user and message.content.lower().startswith("!seed"):
        try:
            new_seed = message.content[6:]
            init(new_seed)
            show_board()
        except:
            pass

    if is_trusted_user and message.content.lower().strip() == "!shutdown":
        shutdown = True

def new_game(msg):
    try:
        players = [x.strip() for x in msg[8:].split(",")]
    except Exception, e:
        print e
        return

    print "players: ", players
    if len(players) < 4:
        return

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
        if random.randrange(2) == 0: 
            red.append(players[0])
        else: 
            blue.append(players[0])

    seed = str(random.randint(1, 1000000000))
    print 'everything is done'

    my_message = '''Suggested teams:
RED: %s
BLUE: %s

Suggested seed: %s'''

    room.send_message(my_message % (', '.join(red), ', '.join(blue), seed))

    init(seed)  
    show_board()


def init(_seed):
    global seed, guessed, board
    seed = _seed
    guessed = []
    board = get_board(seed)

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

def get_board(seed):
    ctxt.locals.obtainedseed = seed
    board = ctxt.eval("createNewGame(obtainedseed);").split(',')
    
    print board
    return board[0], board[1:26], board[26:51]

def draw_grid(seed, solved):
    WIDTH = 500
    GRID_WIDTH = WIDTH / 5
    HEIGHT = 300
    GRID_HEIGHT = HEIGHT / 5

    font = ImageFont.truetype("ariblk.ttf", 12)
    image1 = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255) )
    draw = ImageDraw.Draw(image1)

    #print board
    for x in xrange(5):
        for y in xrange(5):
            if x*5+y in solved:
                #print 'color: ', board[2][x*5+y]
                draw.rectangle([x*GRID_WIDTH, y*GRID_HEIGHT, (x+1)*GRID_WIDTH, (y+1)*GRID_HEIGHT], fill=board[2][x*5+y])

    for x in xrange(GRID_WIDTH, WIDTH, GRID_WIDTH):
        draw.line([x, 0, x, HEIGHT], (0,0,0))
    for y in xrange(GRID_HEIGHT, HEIGHT, GRID_HEIGHT):
        draw.line([0, y, WIDTH, y], (0,0,0))

    for x in xrange(5):
        for y in xrange(5):
            word = board[1][x*5+y]

            size = draw.textsize(word, font=font)
            draw.text((x * GRID_WIDTH + GRID_WIDTH/2 - size[0]/2, y * GRID_HEIGHT + GRID_HEIGHT/2 - size[1]/2), word, (0,0,0), font=font)

    output = StringIO.StringIO()
    image1.save(output, format='png')

    return output.getvalue()

def upload_image(im):
    data = urllib.urlencode([('image', im)])
    req = urllib2.Request('https://api.imgur.com/3/image', data=data, headers={"Authorization": "Client-ID 44c2dcd61ab0bb9"})
    return json.loads(urllib2.urlopen(req).read())["data"]["link"]

main()

