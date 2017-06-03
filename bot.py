import PyV8
import getpass
from PIL import Image, ImageDraw, ImageFont
import StringIO
import urllib2, urllib
import json
import random
import traceback

import chatexchange.client
import chatexchange.events
import re
import sys
import os
import time
import puush

import requests
from requests.auth import HTTPBasicAuth

imagehost = 'puush'

guessed = []
board = []
ctxt = PyV8.JSContext()
ctxt.enter()
ctxt.eval(open("boardgen.js").read())
shutdown = False

OTS_User = 'zaroogous@safetymail.info'
if 'OTS_Password' in os.environ:
    OTS_Password = os.environ['OTS_Password']
else:
    OTS_Password = raw_input("OTS Password: ")

if 'Puush_API_Key' in os.environ:
    Puush_API_Key = os.environ['Puush_API_Key']
else:
    Puush_API_Key = raw_input("Puush API Key: ")

pinned_message_blue = None
pinned_message_red = None
blue = []
red = []

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

passphrases = ["[passing]","[pass]"] #stuff that indicates somebody is passing
TRUSTED_USER_IDS = [200996, 233269, 209507, 238144, 263999, 156773, 69330, 190748, 155240, 56166, 251910, 17335, 240387, 21351, 188759, 174589, 254945, 152262, 207333, 215298, 147578, 242914, 217429]

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
    global shutdown
    if not isinstance(message, chatexchange.events.MessagePosted):
        # Ignore non-message_posted events.
        return

    is_shiro = (message.user.id == 285026)
    is_super_user = (message.user.id == 200996 or message.user.is_moderator)
    is_trusted_user = (message.user.id in TRUSTED_USER_IDS or is_super_user)

    #print("")
    #print(">> (%s / %s) %s" % (message.user.name, repr(message.user.id), message.content))

    try:
        pat = re.compile("\s*<b>(.*)</b>\s*", re.IGNORECASE)
        m = re.match(pat, message.content)
        if m is not None:
            guess = m.groups()[0].strip().lower()
            if guess in passphrases:
                show_board()
            else:
                guessed.append( guess )

        if is_shiro and message.content.strip().startswith("<b>RED</b>:"):
            pin_red(message.message)

        if is_shiro and message.content.strip().startswith("<b>BLUE</b>:"):
            pin_blue(message.message) 

        if is_trusted_user and message.content.lower().strip() == "!board":
            show_board()

        if is_trusted_user and message.content.lower().strip() == "!undo":
            guessed.pop()

        if is_trusted_user and message.content.lower().strip() == "!flipcoin":
            flip_coin()

        if is_trusted_user and message.content.lower().strip() == "!recall":
            recall()

        if is_trusted_user and message.content.lower().startswith("!join"):
            add_user(message.content, message.user.name)

        if is_trusted_user and message.content.lower().startswith("!leave"):
            remove_user(message.content, message.user.name)

        if is_trusted_user and message.content.lower().startswith("!newgame"):
            new_game(message.content)
        
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

    except:
        traceback.print_exc()
        print ""

def flip_coin():
    room.send_message(random.choice(["Red", "Blue"]))

def change_host(msg):
    global imagehost

    pieces = msg.lower().split()
    if len(pieces) >= 2:
        new_host = pieces[1].strip()
        if new_host in ['imgur', 'puush']: imagehost = new_host

def new_game(msg):
    global red, blue
    players = None

    try:
        players = [x.strip() for x in msg[8:].split(",")]
    except Exception, e:
        return

    red = []
    blue = []

    print "players: ", players
    if players is not None and len(players) >= 4:
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
                blue.append(players[0])
            else:
                red.append(players[0])

        room.send_message("**RED**: *%s*, %s" % (red[0], ', '.join(red[1:])))
        room.send_message("**BLUE**: *%s*, %s" % (blue[0], ', '.join(blue[1:])))
        time.sleep(2)

    seed = str(random.randint(1, 1000000000))
    print 'everything is done'

    my_message = '''RED spymaster only, please click on this link to see the seed: %s
BLUE spymaster only, please click on this link to see the seed: %s

Please save the seed somewhere! As a last resort if any of you happens to forget the seed, you can type !recall to get a new link.'''

    room.send_message(my_message % (submit_secret(seed), submit_secret(seed)))

    init(seed)
    if board[0]=="#00eeee":
        room.send_message("BLUE goes first!")
    elif board[0]=="#ff0000":
        room.send_message("RED goes first!")
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
        joining_user = segments[1]

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
        joining_user = name
    else:
        joining_user = segments[1]

    if name in red[1:]:
        red.reverse()
        red.remove(name)
        red.reverse()
        room.send_message("**RED**: *%s*, %s" % (red[0], ', '.join(red[1:])))
    if name in blue[1:]:
        blue.reverse()
        blue.remove(name)
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

def show_final():
    solved = []
    for idx, x in enumerate(board[1]):
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
        pinned_message_red.cancel_stars()
    msg.pin()
    pinned_message_red = msg

def pin_blue(msg):
    global pinned_message_blue
    if pinned_message_blue is not None:
        pinned_message_blue.cancel_stars()
    msg.pin()
    pinned_message_blue = msg

def upload_image(im):
    if imagehost == 'imgur':
        return upload_imgur(im)

    elif imagehost == 'puush':
        return upload_puush(im)

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

main()
