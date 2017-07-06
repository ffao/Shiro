from __future__ import print_function
from datetime import datetime
import traceback

try:
    from colorama import init, Fore, Style 
    init()

    def cprint(s, log_level):
        colors = {
            'debug': (Fore.WHITE, Style.NORMAL),
            'info': (Fore.CYAN, Style.NORMAL),
            'warning': (Fore.YELLOW, Style.BRIGHT),
            'error': (Fore.RED, Style.BRIGHT),
            'default': (Fore.WHITE, Style.NORMAL)
        }
        color = (colors[log_level] if log_level in colors else colors['default'])
        print(color[0], end='')
        print(color[1], end='')
        print(s)
        print(Style.RESET_ALL)
except:
    def cprint(s, log_level):
        print(s)

# noinspection PyMissingTypeHints
def log(log_level, *args):
    log_str = u"[{}] {}".format(datetime.now().isoformat()[11:-7],
                              u"  ".join([str(x) for x in args]))
    with open("errorLogs.txt", "a") as f:
        f.write(log_str + '\n')

    cprint(log_str, log_level)

def log_exception(exctype, value, tb, log_level='error'):
    now = datetime.utcnow()
    tr = '\n'.join((traceback.format_tb(tb)))
    exception_only = ''.join(traceback.format_exception_only(exctype, value)).strip()
    logged_msg = "{exception}\n{now} UTC\n{row}\n\n".format(exception=exception_only, now=now, row=tr)
    log(log_level, logged_msg)