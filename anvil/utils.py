# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
#
#    Copyright 2011 OpenStack LLC.
#    All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import contextlib
import os
import random
import re
import socket
import tempfile
import urllib2

from datetime import datetime

from urlparse import urlunparse

import netifaces
import progressbar
import yaml

from Cheetah.Template import Template

from anvil import colorizer
from anvil import log as logging
from anvil import pprint
from anvil import settings
from anvil import shell as sh
from anvil import version

from anvil.pprint import center_text

MONTY_PYTHON_TEXT_RE = re.compile("([a-z0-9A-Z\?!.,'\"]+)")

# Thx cowsay
# See: http://www.nog.net/~tony/warez/cowsay.shtml
COWS = dict()
COWS['happy'] = r'''
{header}
        \   {ear}__{ear}
         \  ({eye}{eye})\_______
            (__)\       )\/\
                ||----w |
                ||     ||
'''
COWS['unhappy'] = r'''
{header}
  \         ||       ||
    \    __ ||-----mm||
      \ (  )/_________)//
        ({eye}{eye})/
        {ear}--{ear}
'''

LOG = logging.getLogger(__name__)


def expand_template(contents, params):
    if not params:
        params = {}
    return Template(str(contents), searchList=[params]).respond()


def expand_template_deep(root, params):
    if isinstance(root, (basestring, str)):
        return expand_template(root, params)
    if isinstance(root, (list, tuple)):
        n_list = []
        for i in root:
            n_list.append(expand_template_deep(i, params))
        return n_list
    if isinstance(root, (dict)):
        n_dict = {}
        for (k, v) in root.items():
            n_dict[k] = expand_template_deep(v, params)
        return n_dict
    if isinstance(root, (set)):
        n_set = set()
        for v in root:
            n_set.add(expand_template_deep(v, params))
        return n_set
    return root


def load_yaml(path):
    return load_yaml_text(sh.load_file(path))


def load_yaml_text(text):
    return yaml.safe_load(text)


def has_any(text, *look_for):
    if not look_for:
        return False
    for v in look_for:
        if text.find(v) != -1:
            return True
    return False


def wait_for_url(url, max_attempts=3, wait_between=5):
    excps = []
    LOG.info("Waiting for url %s to become active (max_attempts=%s, seconds_between=%s)",
             colorizer.quote(url), max_attempts, wait_between)

    def waiter():
        LOG.info("Sleeping for %s seconds, %s is still not active.", wait_between, colorizer.quote(url))
        sh.sleep(wait_between)

    def success(attempts):
        LOG.info("Url %s became active after %s attempts!", colorizer.quote(url), attempts)

    for i in range(0, max_attempts):
        try:
            with contextlib.closing(urllib2.urlopen(urllib2.Request(url))) as req:
                req.read()
                success(i + 1)
                return
        except urllib2.HTTPError as e:
            if e.code in xrange(200, 499) or e.code in [501]:
                # Should be ok, at least its responding...
                success(i + 1)
                return
            else:
                excps.append(e)
                waiter()
        except IOError as e:
            excps.append(e)
            waiter()
    if excps:
        raise excps[-1]


def add_header(fn, contents, adjusted=True):
    lines = []
    if not fn:
        fn = "???"
    if adjusted:
        lines.append('# Adjusted source file %s' % (fn.strip()))
    else:
        lines.append('# Created source file %s' % (fn.strip()))
    lines.append("# On %s" % (iso8601()))
    lines.append("# By user %s, group %s" % (sh.getuser(), sh.getgroupname()))
    lines.append("")
    if contents:
        lines.append(contents)
    return joinlinesep(*lines)


def iso8601():
    return datetime.now().isoformat()


def merge_dicts(*dicts, **kwargs):
    merged = {}
    for mp in dicts:
        for (k, v) in mp.items():
            if kwargs.get('preserve') and k in merged:
                continue
            else:
                merged[k] = v
    return merged


def make_url(scheme, host, port=None, path='', params='', query='', fragment=''):

    pieces = []
    pieces.append(scheme or '')

    netloc = ''
    if host:
        netloc = str(host)

    if port is not None:
        netloc += ":" + "%s" % (port)

    pieces.append(netloc or '')
    pieces.append(path or '')
    pieces.append(params or '')
    pieces.append(query or '')
    pieces.append(fragment or '')

    return urlunparse([str(p) for p in pieces])


def get_deep(items, path, quiet=True):
    if len(path) == 0:
        return items

    head = path[0]
    remainder = path[1:]
    if isinstance(items, (list, tuple)):
        index = int(head)
        if quiet and not (index < len(items) and index >= 0):
            return None
        else:
            return get_deep(items[index], remainder)
    else:
        get_method = getattr(items, 'get', None)
        if not get_method:
            if not quiet:
                raise RuntimeError("Can not figure out how to extract an item from %s" % (items))
            else:
                return None
        else:
            return get_deep(get_method(head), remainder)


def load_template(component, template_name):
    templ_pth = sh.joinpths(settings.TEMPLATE_DIR, component, template_name)
    return (templ_pth, sh.load_file(templ_pth))


def execute_template(cmd, *cmds, **kargs):
    params = kargs.pop('params', None) or {}
    results = []
    for info in [cmd] + list(cmds):
        run_what_tpl = info["cmd"]
        if not isinstance(run_what_tpl, (list, tuple, set)):
            run_what_tpl = [run_what_tpl]
        run_what = [expand_template(c, params) for c in run_what_tpl]
        stdin = None
        stdin_tpl = info.get('stdin')
        if stdin_tpl:
            if not isinstance(stdin_tpl, (list, tuple, set)):
                stdin_tpl = [stdin_tpl]
            stdin = [expand_template(c, params) for c in stdin_tpl]
            stdin = "\n".join(stdin)
        result = sh.execute(*run_what,
                            run_as_root=info.get('run_as_root', False),
                            process_input=stdin,
                            ignore_exit_code=info.get('ignore_failure', False),
                            **kargs)
        results.append(result)
    return results


def to_bytes(text):
    byte_val = 0
    if not text:
        return byte_val
    if text[-1].upper() == 'G':
        byte_val = int(text[:-1]) * 1024 ** 3
    elif text[-1].upper() == 'M':
        byte_val = int(text[:-1]) * 1024 ** 2
    elif text[-1].upper() == 'K':
        byte_val = int(text[:-1]) * 1024
    elif text[-1].upper() == 'B':
        byte_val = int(text[:-1])
    else:
        byte_val = int(text)
    return byte_val


def truncate_text(text, max_len, from_bottom=False):
    if len(text) < max_len:
        return text
    if not from_bottom:
        return (text[0:max_len] + "...")
    else:
        text = text[::-1]
        text = truncate_text(text, max_len)
        text = text[::-1]
        return text


def log_object(to_log, logger=None, level=logging.INFO, item_max_len=64):
    if not to_log:
        return
    if not logger:
        logger = LOG
    content = pprint.pformat(to_log, item_max_len)
    for line in content.splitlines():
        logger.log(level, line)


def log_iterable(to_log, header=None, logger=None, color='blue'):
    if not logger:
        logger = LOG
    if not to_log:
        if not header:
            return
        if header.endswith(":"):
            header = header[0:-1]
        if not header.endswith("."):
            header = header + "."
        logger.info(header)
        return
    if header:
        if not header.endswith(":"):
            header += ":"
        logger.info(header)
    for c in to_log:
        if color:
            c = colorizer.color(c, color)
        logger.info("|-- %s", c)


@contextlib.contextmanager
def progress_bar(name, max_am, reverse=False):
    widgets = list()
    widgets.append('%s: ' % (name))
    widgets.append(progressbar.Percentage())
    widgets.append(' ')
    if reverse:
        widgets.append(progressbar.ReverseBar())
    else:
        widgets.append(progressbar.Bar())
    widgets.append(' ')
    widgets.append(progressbar.ETA())
    p_bar = progressbar.ProgressBar(maxval=max_am, widgets=widgets)
    p_bar.start()
    try:
        yield p_bar
    finally:
        p_bar.finish()


@contextlib.contextmanager
def tempdir(**kwargs):
    # This seems like it was only added in python 3.2
    # Make it since its useful...
    # See: http://bugs.python.org/file12970/tempdir.patch
    tdir = tempfile.mkdtemp(**kwargs)
    try:
        yield tdir
    finally:
        sh.deldir(tdir)


def get_host_ip():
    """
    Returns the actual ip of the local machine.

    This code figures out what source address would be used if some traffic
    were to be sent out to some well known address on the Internet. In this
    case, a private address is used, but the specific address does not
    matter much.  No traffic is actually sent.

    Adjusted from nova code...
    """
    ip = None
    try:
        csock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        csock.connect(('8.8.8.8', 80))
        (addr, _) = csock.getsockname()
        csock.close()
        ip = addr
    except socket.error:
        pass
    # Attempt to find it
    if not ip:
        interfaces = get_interfaces()
        for (_, net_info) in interfaces.items():
            ip_info = net_info.get('IPv4')
            if ip_info:
                a_ip = ip_info.get('addr')
                if a_ip:
                    ip = a_ip
                    break
    # Just return a localhost version then
    if not ip:
        ip = "127.0.0.1"
    return ip


@contextlib.contextmanager
def chdir(where_to):
    curr_cd = os.getcwd()
    if curr_cd == where_to:
        yield where_to
    else:
        try:
            os.chdir(where_to)
            yield where_to
        finally:
            os.chdir(curr_cd)


def get_interfaces():
    interfaces = {}
    for intfc in netifaces.interfaces():
        interface_info = {}
        interface_addresses = netifaces.ifaddresses(intfc)
        ip6 = interface_addresses.get(netifaces.AF_INET6)
        if ip6:
            # Just take the first
            interface_info['IPv6'] = ip6[0]
        ip4 = interface_addresses.get(netifaces.AF_INET)
        if ip4:
            # Just take the first
            interface_info['IPv4'] = ip4[0]
        # Note: there are others but this is good for now..
        interfaces[intfc] = interface_info
    return interfaces


def format_time(secs):
    return {
        'seconds': "%.03f" % (secs),
        "minutes": "%.02f" % (secs / 60.0),
    }


def joinlinesep(*pieces):
    return os.linesep.join(pieces)


def prettify_yaml(obj):
    formatted = yaml.dump(obj,
                    line_break="\n",
                    indent=4,
                    explicit_start=True,
                    explicit_end=True,
                    default_flow_style=False,
                    )
    return formatted


def _get_welcome_stack():
    possibles = []
    # Thank you figlet ;)
    # See: http://www.figlet.org/
    possibles.append(r'''
  ___  ____  _____ _   _ ____ _____  _    ____ _  __
 / _ \|  _ \| ____| \ | / ___|_   _|/ \  / ___| |/ /
| | | | |_) |  _| |  \| \___ \ | | / _ \| |   | ' /
| |_| |  __/| |___| |\  |___) || |/ ___ \ |___| . \
 \___/|_|   |_____|_| \_|____/ |_/_/   \_\____|_|\_\

''')
    possibles.append(r'''
  ___  ___ ___ _  _ ___ _____ _   ___ _  __
 / _ \| _ \ __| \| / __|_   _/_\ / __| |/ /
| (_) |  _/ _|| .` \__ \ | |/ _ \ (__| ' <
 \___/|_| |___|_|\_|___/ |_/_/ \_\___|_|\_\

''')
    possibles.append(r'''
____ ___  ____ _  _ ____ ___ ____ ____ _  _
|  | |__] |___ |\ | [__   |  |__| |    |_/
|__| |    |___ | \| ___]  |  |  | |___ | \_

''')
    possibles.append(r'''
  _  ___ ___  _  _  __  ___  _   __  _  _
 / \| o \ __|| \| |/ _||_ _|/ \ / _|| |//
( o )  _/ _| | \\ |\_ \ | || o ( (_ |  (
 \_/|_| |___||_|\_||__/ |_||_n_|\__||_|\\

''')
    possibles.append(r'''
   _   ___  ___  _  __  ___ _____  _    __  _
 ,' \ / o |/ _/ / |/ /,' _//_  _/.' \ ,'_/ / //7
/ o |/ _,'/ _/ / || /_\ `.  / / / o // /_ /  ,'
|_,'/_/  /___//_/|_//___,' /_/ /_n_/ |__//_/\\

''')
    possibles.append(r'''
 _____  ___    ___    _   _  ___   _____  _____  ___    _   _
(  _  )(  _`\ (  _`\ ( ) ( )(  _`\(_   _)(  _  )(  _`\ ( ) ( )
| ( ) || |_) )| (_(_)| `\| || (_(_) | |  | (_) || ( (_)| |/'/'
| | | || ,__/'|  _)_ | , ` |`\__ \  | |  |  _  || |  _ | , <
| (_) || |    | (_( )| |`\ |( )_) | | |  | | | || (_( )| |\`\
(_____)(_)    (____/'(_) (_)`\____) (_)  (_) (_)(____/'(_) (_)

''')
    return random.choice(possibles).strip("\n\r")



def _welcome_slang():
    potentials = list()
    potentials.append("And now for something completely different!")
    return random.choice(potentials)


def _color_blob(text, text_color):

    def replacer(match):
        contents = match.group(1)
        return colorizer.color(contents, text_color)

    return MONTY_PYTHON_TEXT_RE.sub(replacer, text)


def _goodbye_header(worked):
    # Cowsay headers
    # See: http://www.nog.net/~tony/warez/cowsay.shtml
    potentials_oks = []
    potentials_oks.append(r'''
 ___________
/ You shine \
| out like  |
| a shaft   |
| of gold   |
| when all  |
| around is |
\ dark.     /
 -----------
''')
    potentials_oks.append(r'''
 ______________________________
< I'm a lumberjack and I'm OK. >
 ------------------------------
''')
    potentials_oks.append(r'''
 ____________________
/ Australia!         \
| Australia!         |
| Australia!         |
\ We love you, amen. /
 --------------------
''')
    potentials_oks.append(r'''
 ______________
/ Say no more, \
| Nudge nudge  |
\ wink wink.   /
 --------------
''')
    potentials_oks.append(r'''
 ________________
/ And there was  \
\ much rejoicing /
 ----------------
''')
    potentials_oks.append(r'''
 __________
< Success! >
 ----------''')
    potentials_fails = []
    potentials_fails.append(r'''
 __________
< Failure! >
 ----------
''')
    potentials_fails.append(r'''
 ___________
< Run away! >
 -----------
''')
    potentials_fails.append(r'''
 ______________________
/ NOBODY expects the   \
\ Spanish Inquisition! /
 ----------------------
''')
    potentials_fails.append(r'''
 ______________________
/ Spam spam spam spam  \
\ baked beans and spam /
 ----------------------
''')
    potentials_fails.append(r'''
 ____________________
/ Brave Sir Robin    \
\ ran away.          /
 --------------------
''')
    potentials_fails.append(r'''
 _______________________
< Message for you, sir. >
 -----------------------
''')
    potentials_fails.append(r'''
 ____________________
/ We are the knights \
\ who say.... NI!    /
 --------------------
''')
    potentials_fails.append(r'''
 ____________________
/ Now go away or I   \
| shall taunt you a  |
\ second time.       /
 --------------------
''')
    potentials_fails.append(r'''
 ____________________
/ It's time for the  \
| penguin on top of  |
| your television to |
\ explode.           /
 --------------------
''')
    potentials_fails.append(r'''
 _____________________
/ We were in the nick \
| of time. You were   |
\ in great peril.     /
 ---------------------
''')
    potentials_fails.append(r'''
 ___________________
/ I know a dead     \
| parrot when I see |
| one, and I'm      |
| looking at one    |
\ right now.        /
 -------------------
''')
    potentials_fails.append(r'''
 _________________
/ Welcome to the  \
| National Cheese |
\ Emporium        /
 -----------------
''')
    potentials_fails.append(r'''
 ______________________
/ What is the airspeed \
| velocity of an       |
\ unladen swallow?     /
 ----------------------
''')
    potentials_fails.append(r'''
 ______________________
/ Now stand aside,     \
\ worthy adversary.    /
 ----------------------
''')
    potentials_fails.append(r'''
 ___________________
/ Okay, we'll call  \
\ it a draw.        /
 -------------------
''')
    potentials_fails.append(r'''
 _______________
/ She turned me \
\ into a newt!  /
 ---------------
''')
    potentials_fails.append(r'''
 ___________________
< Fetchez la vache! >
 -------------------
''')
    potentials_fails.append(r'''
 __________________________
/ We'd better not risk     \
| another frontal assault, |
\ that rabbit's dynamite.  /
 --------------------------
''')
    potentials_fails.append(r'''
 ______________________
/ This is supposed to  \
| be a happy occasion. |
| Let's not bicker and |
| argue about who      |
\ killed who.          /
 ----------------------
''')
    potentials_fails.append(r'''
 _______________________
< You have been borked. >
 -----------------------
''')
    potentials_fails.append(r'''
 __________________
/ We used to dream  \
| of living in a    |
\ corridor!         /
 -------------------
''')
    if not worked:
        msg = random.choice(potentials_fails).strip("\n\r")
        colored_msg = _color_blob(msg, 'red')
    else:
        msg = random.choice(potentials_oks).strip("\n\r")
        colored_msg = _color_blob(msg, 'green')
    return colored_msg


def goodbye(worked):
    if worked:
        cow = COWS['happy']
        eye_fmt = colorizer.color('o', 'green')
        ear = colorizer.color("^", 'green')
    else:
        cow = COWS['unhappy']
        eye_fmt = colorizer.color("o", 'red')
        ear = colorizer.color("v", 'red')
    cow = cow.strip("\n\r")
    header = _goodbye_header(worked)
    msg = cow.format(eye=eye_fmt, ear=ear, header=header)
    print(msg)


def welcome(prog_name='Anvil', version_text=version.version_string()):
    lower = "| %s |" % (version_text)
    welcome_header = _get_welcome_stack()
    max_line_len = len(max(welcome_header.splitlines(), key=len))
    footer = colorizer.color(prog_name, 'green') + ": " + colorizer.color(lower, 'blue', bold=True)
    uncolored_footer = prog_name + ": " + lower
    if max_line_len - len(uncolored_footer) > 0:
        # This format string will center the uncolored text which
        # we will then replace with the color text equivalent.
        centered_str = center_text(uncolored_footer, " ", max_line_len)
        footer = centered_str.replace(uncolored_footer, footer)
    print(welcome_header)
    print(footer)
    real_max = max(max_line_len, len(uncolored_footer))
    slang = center_text(_welcome_slang(), ' ', real_max)
    print(colorizer.color(slang, 'magenta', bold=True))
    return ("-", real_max)
