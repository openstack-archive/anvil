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

import distutils.version
from urlparse import urlunparse

import netifaces
import progressbar
import yaml

from anvil import constants
from anvil import colorizer
from anvil import date
from anvil import exceptions as excp
from anvil import log as logging
from anvil import settings
from anvil import shell as sh
from anvil import version

# The pattern will match either a comment to the EOL, or a
# token to be subbed. The replacer will check which it got and
# act accordingly. Note that we need the MULTILINE flag
# for the comment checks to work in a string containing newlines
PARAM_SUB_REGEX = re.compile(r"#(.*)$|%([\w\d/\.]+?)%", re.MULTILINE)
EXT_COMPONENT = re.compile(r"^\s*([\w-]+)(?:\((.*)\))?\s*$")
MONTY_PYTHON_TEXT_RE = re.compile("([a-z0-9A-Z\?!.,'\"]+)")
DEF_IP = "127.0.0.1"
IP_LOOKER = '8.8.8.8'
DEF_IP_VERSION = constants.IPV4
STAR_VERSION = 0

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


def make_bool(val):
    if type(val) is bool:
        return val
    sval = str(val).lower().strip()
    if sval in ['true', '1', 'on', 'yes', 't']:
        return True
    if sval in ['0', 'false', 'off', 'no', 'f', '']:
        return False
    raise TypeError("Unable to convert %r to a boolean" % (val))


def add_header(fn, contents):
    lines = list()
    if not fn:
        fn = "???"
    lines.append('# Adjusted source file %s' % (fn.strip()))
    lines.append("# On %s" % (date.rcf8222date()))
    lines.append("# By user %s, group %s" % (sh.getuser(), sh.getgroupname()))
    lines.append("")
    if contents:
        lines.append(contents)
    return joinlinesep(*lines)


def make_url(scheme, host, port=None,
                path='', params='', query='', fragment=''):

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

    return urlunparse(pieces)


def get_from_path(items, path, quiet=True):

    LOG.debug("Looking up %r in %s" % (path, items))

    (first_token, sep, remainder) = path.partition('.')

    if len(path) == 0:
        return items

    if len(first_token) == 0:
        if not quiet:
            raise RuntimeError("Invalid first token found in %s" % (path))
        else:
            return None

    if isinstance(items, list):
        index = int(first_token)
        ok_use = (index < len(items) and index >= 0)
        if quiet and not ok_use:
            return None
        else:
            LOG.debug("Looking up index %s in list %s" % (index, items))
            return get_from_path(items[index], remainder)
    else:
        get_method = getattr(items, 'get', None)
        if not get_method:
            if not quiet:
                raise RuntimeError("Can not figure out how to extract an item from %s" % (items))
            else:
                return None
        else:
            LOG.debug("Looking up %r in object %s with method %s" % (first_token, items, get_method))
            return get_from_path(get_method(first_token), remainder)


def load_template(component, template_name):
    templ_pth = sh.joinpths(settings.TEMPLATE_DIR, component, template_name)
    return (templ_pth, sh.load_file(templ_pth))


def execute_template(*cmds, **kargs):
    params_replacements = kargs.pop('params', None)
    ignore_missing = kargs.pop('ignore_missing', False)
    cmd_results = list()
    for cmdinfo in cmds:
        cmd_to_run_templ = cmdinfo["cmd"]
        cmd_to_run = param_replace_list(cmd_to_run_templ, params_replacements, ignore_missing)
        stdin_templ = cmdinfo.get('stdin')
        stdin = None
        if stdin_templ:
            stdin_full = param_replace_list(stdin_templ, params_replacements, ignore_missing)
            stdin = joinlinesep(*stdin_full)
        exec_result = sh.execute(*cmd_to_run,
                                 run_as_root=cmdinfo.get('run_as_root', False),
                                 process_input=stdin,
                                 ignore_exit_code=cmdinfo.get('ignore_failure', False),
                                 **kargs)
        cmd_results.append(exec_result)
    return cmd_results


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


def log_iterable(to_log, header=None, logger=None, do_color=True):
    if not to_log:
        return
    if not logger:
        logger = LOG
    if header:
        if not header.endswith(":"):
            header += ":"
        logger.info(header)
    for c in to_log:
        if do_color:
            c = colorizer.color(c, 'blue')
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


def versionize(input_version, unknown_version="-1.0"):
    if input_version == None:
        return distutils.version.LooseVersion(unknown_version)
    input_version = str(input_version)
    segments = input_version.split(".")
    cleaned_segments = list()
    for piece in segments:
        piece = piece.strip()
        if len(piece) == 0:
            cleaned_segments.append("")
        else:
            piece = piece.strip("*")
            if len(piece) == 0:
                cleaned_segments.append(STAR_VERSION)
            else:
                try:
                    piece = int(piece)
                except ValueError:
                    pass
                cleaned_segments.append(piece)
    if not cleaned_segments:
        return distutils.version.LooseVersion(unknown_version)
    return distutils.version.LooseVersion(".".join([str(p) for p in cleaned_segments]))


def sort_versions(versions, descending=True):
    if not versions:
        return list()
    version_cleaned = list()
    for v in versions:
        version_cleaned.append(versionize(v))
    versions_sorted = sorted(version_cleaned)
    if not descending:
        versions_sorted.reverse()
    return versions_sorted


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
        csock.connect((IP_LOOKER, 80))
        (addr, _) = csock.getsockname()
        csock.close()
        ip = addr
    except socket.error:
        pass
    # Attempt to find it
    if not ip:
        interfaces = get_interfaces()
        for (_, net_info) in interfaces.items():
            ip_info = net_info.get(DEF_IP_VERSION)
            if ip_info:
                a_ip = ip_info.get('addr')
                if a_ip:
                    ip = a_ip
                    break
    # Just return a localhost version then
    if not ip:
        ip = DEF_IP
    return ip


def get_interfaces():
    interfaces = dict()
    for intfc in netifaces.interfaces():
        interface_info = dict()
        interface_addresses = netifaces.ifaddresses(intfc)
        ip6 = interface_addresses.get(netifaces.AF_INET6)
        if ip6:
            # Just take the first
            interface_info[constants.IPV6] = ip6[0]
        ip4 = interface_addresses.get(netifaces.AF_INET)
        if ip4:
            # Just take the first
            interface_info[constants.IPV4] = ip4[0]
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


def get_class_names(objects):
    return map((lambda i: i.__class__.__name__), objects)


def param_replace_list(values, replacements, ignore_missing=False):
    new_values = list()
    if not values:
        return new_values
    for v in values:
        if v is not None:
            new_values.append(param_replace(str(v), replacements, ignore_missing))
        else:
            new_values.append(v)
    return new_values


def find_params(text):
    params_found = set()
    if not text:
        text = ''

    def finder(match):
        param_name = match.group(2)
        if param_name is not None and param_name not in params_found:
            params_found.add(param_name)
        # Just finding, not modifying...
        return match.group(0)

    PARAM_SUB_REGEX.sub(finder, text)
    return params_found


def prettify_yaml(obj):
    formatted = yaml.dump(obj,
                    line_break="\n",
                    indent=4,
                    explicit_start=True,
                    explicit_end=True,
                    default_flow_style=False,
                    )
    return formatted


def param_replace_deep(root, replacements, ignore_missing=False):
    if isinstance(root, list):
        new_list = []
        for v in root:
            new_list.append(param_replace_deep(v, replacements, ignore_missing))
        return new_list
    elif isinstance(root, basestring):
        return param_replace(root, replacements, ignore_missing)
    elif isinstance(root, dict):
        mapped_dict = {}
        for (k, v) in root.items():
            mapped_dict[k] = param_replace_deep(v, replacements, ignore_missing)
        return mapped_dict
    elif isinstance(root, set):
        mapped_set = set()
        for v in root:
            mapped_set.add(param_replace_deep(v, replacements, ignore_missing))
        return mapped_set
    else:
        return root


def param_replace(text, replacements, ignore_missing=False):

    if not replacements:
        replacements = dict()

    if not text:
        text = ""

    if ignore_missing:
        LOG.debug("Performing parameter replacements (ignoring missing) on text %r" % (text))
    else:
        LOG.debug("Performing parameter replacements (not ignoring missing) on text %r" % (text))

    possible_params = find_params(text)
    LOG.debug("Possible replacements are: %r" % (", ".join(possible_params)))
    LOG.debug("Given substitutions are: %s" % (replacements))

    def replacer(match):
        org_txt = match.group(0)
        # Its a comment, leave it be
        if match.group(1) is not None:
            return org_txt
        param_name = match.group(2)
        # Find the replacement, if we can
        replacer = get_from_path(replacements, param_name)
        if replacer is None and ignore_missing:
            replacer = org_txt
        elif replacer is None and not ignore_missing:
            msg = "No replacement found for parameter %r in %r" % (param_name, org_txt)
            raise excp.NoReplacementException(msg)
        else:
            LOG.debug("Replacing %r with %r in %r", param_name, replacer, org_txt)
        return str(replacer)

    replaced_text = PARAM_SUB_REGEX.sub(replacer, text)
    LOG.debug("Replacement/s resulted in text %r", replaced_text)
    return replaced_text


def _get_welcome_stack():
    possibles = list()
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


def center_text(text, fill, max_len):
    return '{0:{fill}{align}{size}}'.format(text, fill=fill, align="^", size=max_len)


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
    potentials_oks = list()
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
    potentials_fails = list()
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


def welcome(prog_name=constants.PROG_NAME.upper(), version_text=version.version_string()):
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
