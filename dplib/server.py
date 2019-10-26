# DPLib - Asynchronous bot framework for Digital Paint: Paintball 2 servers
# Copyright (C) 2017  Michał Rokita
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re
from collections import OrderedDict
from enum import Enum
import asyncio
import os
from socket import socket, AF_INET, SOCK_DGRAM
from dplib.parse import render_text, decode_ingame_text


class ServerEvent(Enum):
    TIMEOUT = 0
    CHAT = 1
    ELIM = 2
    RESPAWN = 3
    MAPCHANGE = 4
    DATE = 5
    NAMECHANGE = 6
    ENTRANCE = 7
    FLAG_CAPTURED = 8
    ELIM_TEAMS_FLAG = 9
    ROUND_STARTED = 10
    TEAM_SWITCHED = 11
    GAME_END = 12
    DISCONNECT = 13
    FLAG_GRAB = 14
    FLAG_DROP = 15
    ROUND_END = 16
    GAMEMODE = 17   

class BadRconPasswordError(Exception):
    pass

class ListenerType(Enum):
    PERMANENT = 0
    TRIGGER_ONCE = 1


REGEXPS = OrderedDict([
    (re.compile('^\\[\d\d:\d\d:\d\d\\] (?:(?:\\[OBS\\] )|(?:\\[ELIM\\] ))?(.*?): (.*?)\r?\n'), ServerEvent.CHAT),
    # [19:54:18] hTml: test
    (re.compile(
        '^\\[\d\d:\d\d:\d\d\\] \\*(.*?) (?:\\((.*?)\\) eliminated \\*(.*?) \\((.*?)\\)\\.\r?\n|'
        'eliminated ((?:himself)|(?:herself)) with a paintgren\\.\r?\n)'), ServerEvent.ELIM),
    # [18:54:24] *|ACEBot_1| (Spyder SE) eliminated *|herself| (Spyder SE).
    # [12:25:44] *whoa eliminated herself with a paintgren.
    # [12:26:09] *whoa eliminated himself with a paintgren.

    (re.compile('^\\[\d\d:\d\d:\d\d\\] \\*(.*?)\\\'s (.*?) revived!\r?\n'), ServerEvent.RESPAWN),
    # [19:03:57] *Red's ACEBot_6 revived!
    (re.compile('^\\[\d\d:\d\d:\d\d\\] (.*?) entered the game \\((.*?)\\) \\[(.*?)\\]\r?\n'), ServerEvent.ENTRANCE),
    # [19:03:57] mRokita entered the game (build 41) [127.0.0.1:22345]
    (re.compile('^\\[\d\d:\d\d:\d\d\\] \\*(.*?)\\\'s (.*?) returned the(?: \\*(.*?))? flag!\r?\n'), ServerEvent.FLAG_CAPTURED),
    # [18:54:24] *Red's hTml returned the *Blue flag!
    (re.compile('^\\[\d\d:\d\d:\d\d\\] \\*(.*?)\\\'s (.*?) earned (\d+) points for possesion of eliminated teams flag!\r?\n'),
        ServerEvent.ELIM_TEAMS_FLAG),
    # [19:30:23] *Blue's mRokita earned 3 points for possesion of eliminated teams flag!
    (re.compile('^\\[\d\d:\d\d:\d\d\\] Round started\\.\\.\\.\r?\n'), ServerEvent.ROUND_STARTED),
    # [10:20:11] Round started...
    (re.compile(
        '(?:^\\[\d\d:\d\d:\d\d\\] (.*?) switched from \\*((?:Red)|(?:Purple)|(?:Blue)|(?:Yellow))'
        ' to \\*((?:Red)|(?:Purple)|(?:Blue)|(?:Yellow))\\.\r?\n)|'
        '(?:^\\[\d\d:\d\d:\d\d\\] (.*?) joined the \\*((?:Red)|(?:Purple)|(?:Blue)|(?:Yellow)) team\\.\r?\n)|'
        '(?:^\\[\d\d:\d\d:\d\d\\] (.*?) is now (observing)?\\.\r?\n)'), ServerEvent.TEAM_SWITCHED),
    # [10:20:11] mRokita switched from Blue to Red.
    # [10:20:11] mRokita is now observing.
    # [10:20:11] mRokita is now observing.
    (re.compile('^\\[\d\d:\d\d:\d\d\\] 0:00 left in match\\.\r?\n'), ServerEvent.GAME_END),
    # [10:20:11] == Map Loaded: airtime ==
    (re.compile('^\\[\d\d:\d\d:\d\d\\] == Map Loaded: (.+) ==\r?\n'), ServerEvent.MAPCHANGE),
    # [19:54:54] name1 changed name to name2.
    (re.compile('^\\[\d\d:\d\d:\d\d\\] (.*?) changed name to (.*?)\\.\r?\n'), ServerEvent.NAMECHANGE),
    (re.compile('^\\[\d\d:\d\d:\d\d\\] (.*?) disconnected\\.\r?\n'), ServerEvent.DISCONNECT),
    # [19:03:57] whoa disconnected.
    (re.compile('^\\[\d\d:\d\d:\d\d\\] \\*(.*?) got the(?: \\*(.*?))? flag\\!\r?\n'), ServerEvent.FLAG_GRAB),
    # [19:03:57] *whoa got the *Red flag!
    (re.compile('^\\[\d\d:\d\d:\d\d\\] \\*(.*?) dropped the flag\\!\r?\n'), ServerEvent.FLAG_DROP),
    # [19:03:57] *whoa dropped the flag!
    (re.compile('^\\[\d\d:\d\d:\d\d\\] (.*?) team wins the round\\!\r?\n'), ServerEvent.ROUND_END),
    # [14:38:50] Blue team wins the round!
    (re.compile('^\\[\d\d:\d\d:\d\d\\] === ((?:Deathmatch)|(?:Team Flag CTF)|(?:Single Flag CTF)|(?:Team Siege)|(?:Team Elim)|(?:Team Siege)|(?:Team Deathmatch)|(?:Team KOTH)|(?:Pong)) ===\r?\n'), ServerEvent.GAMEMODE),
])


class Player(object):
    """
    Player info from sv players command

    :Attributes:

        * dplogin - dplogin.com account id, None when Player has no account
        * nick - nickname:
        * build - game build
        * server - an instance of :class:`Server`
    """
    def __init__(self, server, id, dplogin, nick, build):
        self.server = server
        self.id = id
        self.dplogin = dplogin
        self.nick = nick
        self.build = build


class Server(object):
    """
    Represents a DP:PB2 server

    :param hostname: Server hostname, for example '127.0.0.1'
    :type hostname: str
    :param port: Server port, default 27910
    :type port: int
    :param logfile: Path to logfile
    :param rcon_password: rcon password
    :param init_vars: Send come commands used for security
    """

    def __init__(self, hostname, port=27910, logfile=None, rcon_password=None, pty_master=None, init_vars=True):
        self.__rcon_password = rcon_password
        self.__hostname = hostname
        self.__init_vars = init_vars
        self.__port = port
        self.__log_file = None
        self.__alive = False
        self.__logfile_name = logfile if not pty_master else None
        self.__pty_master = pty_master

        self.handlers = {
            ServerEvent.CHAT: 'on_chat',
            ServerEvent.ELIM: 'on_elim',
            ServerEvent.RESPAWN: 'on_respawn',
            ServerEvent.ENTRANCE: 'on_entrance',
            ServerEvent.FLAG_CAPTURED: 'on_flag_captured',
            ServerEvent.ELIM_TEAMS_FLAG: 'on_elim_teams_flag',
            ServerEvent.ROUND_STARTED: 'on_round_started',
            ServerEvent.TEAM_SWITCHED: 'on_team_switched',
            ServerEvent.GAME_END: 'on_game_end',
            ServerEvent.MAPCHANGE: 'on_mapchange',
            ServerEvent.NAMECHANGE: 'on_namechange',
            ServerEvent.DISCONNECT: 'on_disconnect',
            ServerEvent.FLAG_GRAB: 'on_flag_grab',
            ServerEvent.FLAG_DROP: 'on_flag_drop',
            ServerEvent.ROUND_END: 'on_round_end',
            ServerEvent.GAMEMODE: 'gamemode',
        }
        self.__listeners = {
            ServerEvent.CHAT: [],
            ServerEvent.ELIM: [],
            ServerEvent.RESPAWN: [],
            ServerEvent.ENTRANCE: [],
            ServerEvent.FLAG_CAPTURED: [],
            ServerEvent.ELIM_TEAMS_FLAG: [],
            ServerEvent.ROUND_STARTED: [],
            ServerEvent.TEAM_SWITCHED: [],
            ServerEvent.GAME_END: [],
            ServerEvent.MAPCHANGE: [],
            ServerEvent.NAMECHANGE: [],
            ServerEvent.DISCONNECT: [],
            ServerEvent.FLAG_GRAB: [],
            ServerEvent.FLAG_DROP: [],
            ServerEvent.ROUND_END: [],
            ServerEvent.GAMEMODE: [],
        }
        self.loop = asyncio.get_event_loop()

    def is_listening(self):
        """
        Check if the main loop is running.

        :rtype: bool
        """
        return self.__alive

    @asyncio.coroutine
    def on_chat(self, nick, message):
        """
        On chat, can be overridden using the :func:`.Server.event` decorator.

        :param nick: Player's nick.
        :type nick: str
        :param message: Message.
        :type message: str
        """
        pass

    @asyncio.coroutine
    def on_flag_captured(self, team, nick, flag):
        """
        On flag captured, can be overridden using the :func:`.Server.event` decorator.

        :param team: Player's team.
        :type team: str
        :param nick: Player's nick.
        :type nick: str
        :param flag: Captured flag (Blue|Red|Yellow|Purple|White)
        :type flag: str
        """
        pass

    @asyncio.coroutine
    def on_team_switched(self, nick, old_team, new_team):
        """
        On team switched, can be overridden using the :func:`.Server.event` decorator.

        :param nick: Player's nick
        :type nick: str
        :param old_team: Old team (Blue|Red|Yellow|Purple|Observer)
        :type old_team: str
        :param new_team: New team (Blue|Red|Yellow|Purple|Observer)
        :type new_team: str
        """
        pass

    @asyncio.coroutine
    def on_round_started(self):
        """
        On round started, can be overridden using the :func:`.Server.event` decorator.
        """
        pass

    @asyncio.coroutine
    def on_elim_teams_flag(self, team, nick, points):
        """
        On scored points for possession of eliminated teams flag, can be overridden using the :func:`.Server.event` decorator.

        :param team: Player's team.
        :type team: str
        :param nick: Player's nick.
        :type nick: str
        :param points: Points earned.
        :type points: int
        """
        pass

    @asyncio.coroutine
    def on_entrance(self, nick, build, addr):
        """
        On entrance, can be overriden using the :func:`.Server.event` decorator.

        :param nick: Player's nick
        :type nick: str
        :param build: Player's game version ('build 41' for example
        :type build: str
        :param addr: Player's address, IP:PORT ('127.0.0.1:23414' for example)
        :type addr: str
        """
        pass

    @asyncio.coroutine
    def on_game_end(self, score_blue, score_red, score_yellow, score_purple):
        """
        On game end, can be overriden using the :func:`.Server.event` decorator.

        :param score_blue: Blue's score - None if there was no Blue team.
        :param score_red: Red's score - None if there was no Red team.
        :param score_yellow: Yellow's score - None if there was no Yellow team.
        :param score_purple: Purple's score - None if there was no Purple team.
        """
        pass

    @asyncio.coroutine
    def on_elim(self, killer_nick, killer_weapon, victim_nick, victim_weapon, suicide):
        """
        On elim can be overridden using the :func:`.Server.event` decorator.

        :param killer_nick: Killer's nick
        :type killer_nick: str
        :param killer_weapon: Killer's weapon
        :type killer_weapon: str
        :param victim_nick: Victim's nick
        :type victim_nick: str
        :param victim_weapon: Victim's weapon
        :type victim_weapon: str
        """
        pass

    @asyncio.coroutine
    def on_respawn(self, team, nick):
        """
        On respawn, can be overridden using the :func:`.Server.event` decorator.

        :param team: Player's team (Blue|Red|Yellow|Purple)
        :type team: str
        :param nick: Player's nick
        :type nick: str
        """
        pass

    @asyncio.coroutine
    def on_mapchange(self, mapname):
        """
        On mapcange, can be overridden using the :func:`.Server.event` decorator.

        :param mapname: Mapname
        :type mapname: str
        """
        pass


    @asyncio.coroutine
    def on_namechange(self, old_nick, new_nick):
        """
        On name change, can be overridden using the :func:`.Server.event` decorator.

        :param old_nick: Old nick
        :type old_nick: str
        :param new_nick: Old nick
        :type new_nick: str
        """
        pass

    @asyncio.coroutine
    def on_disconnect(self, nick):
        """
        On disconnect, can be overridden using the :func:`.Server.event`decorator.

        :param nick: Disconnected player's nick
        :type nick: str
        """
        pass
    
    @asyncio.coroutine
    def on_flag_grab(self, nick, flag):
        """
        On flag grab, can be overridden using the :func:`.Server.event` decorator.
       
        :param nick: Player's nick
        :type nick: str
        :param team: Flag color (Blue|Red|Yellow|Purple)
        :type team: str
        """
        pass
    
    @asyncio.coroutine
    def on_flag_drop(self, nick):
        """
        On flag grab, can be overridden using the :func:`.Server.event` decorator.
       
        :param nick: Player's nick
        :type nick: str
        :param team: Flag color (Blue|Red|Yellow|Purple)
        :type team: str
        """
        pass
        
    @asyncio.coroutine
    def on_round_end(self):
        """
        Onround end, can be overridden using the :func:`.Server.event` decorator.
       
        """
        pass
        
    @asyncio.coroutine
    def gamemode(self, gamemode):
        """
        Onround end, can be overridden using the :func:`.Server.event` decorator.
        
        :param gamemode: map's gamemode
        :type gamemode: str
        """
        pass

    def event(self, func):
        """
        Decorator, used for event registration.

        :param func: function to register

        :rtype: builtin_function_or_method

        :example:
        .. code-block:: python
            :linenos:

            >>> from dplib.server import Server
            >>> s = Server(hostname='127.0.0.1', port=27910, logfile=r'qconsole27910.log', rcon_password='hello')
            >>> @s.event
            ... def on_chat(nick, message):
            ...     print((nick, message))
            ...
            >>> s.run()
            ('mRokita', 'Hi')
        """
        if func.__name__ in self.handlers.values():
            setattr(self, func.__name__, asyncio.coroutine(func))
            return func
        else:
            raise Exception('Event \'%s\' doesn\'t exist' % func.__name__)

    def stop_listening(self):
        """
        Stop the main loop
        """
        self.__alive = False

    def __perform_listeners(self, event_type, args, kwargs):
        """
        Performs all pending listeners.

        :param event_type: Event type, one of members :class:`ServerEvent`
        :param args: Event info
        :type args: tuple
        :param kwargs: Event info
        :type kwargs: dict
        """
        to_remove = list()
        for i, (check, future) in enumerate(self.__listeners[event_type]):
            if not future.cancelled() and not future.done():
                if check(*args):
                    future.set_result(kwargs)
            else:
                to_remove.append(i)
        for i in reversed(to_remove):
            self.__listeners[event_type].pop(i)


    def nicks_valid(self, *nicks):

        nicks_ingame = [p.nick for p in self.get_players()]
        for nick in nicks:
            if not nick in nicks_ingame:
                return False
        return True

    @asyncio.coroutine
    def __handle_event(self, event_type, args):
        """
        Handles an event.

        :param event_type: Event type, one of members :class:`ServerEvent`
        :param args: Event info (re.findall() results)
        """
        kwargs = dict()
        if event_type == ServerEvent.CHAT:
            if args[0] not in [p.nick for p in self.get_players()]:
                return
            kwargs = {
                'nick': args[0],
                'message': args[1],
            }
            self.__perform_listeners(ServerEvent.CHAT, args, kwargs)
        elif event_type == ServerEvent.ELIM:
            kwargs = {
                    'killer_nick': args[0],
                    'killer_weapon': args[1],
                    'victim_nick': args[2],
                    'victim_weapon': args[3],
                    'suicide': args[4],
                    
            }
            self.__perform_listeners(ServerEvent.ELIM, args, kwargs)
        elif event_type == ServerEvent.RESPAWN:
            kwargs = {
                'team': args[0],
                'nick': args[1],
            }
            self.__perform_listeners(ServerEvent.RESPAWN, args, kwargs)
        elif event_type == ServerEvent.ENTRANCE:
            kwargs = {
                'nick': args[0],
                'build': args[1],
                'addr': args[2],
            }
            self.__perform_listeners(ServerEvent.ENTRANCE, args, kwargs)
        elif event_type == ServerEvent.FLAG_CAPTURED:
            kwargs = {
                'team': args[0],
                'nick': args[1],
                'flag': args[2],
            }
            self.__perform_listeners(ServerEvent.FLAG_CAPTURED, args, kwargs)
        elif event_type == ServerEvent.ELIM_TEAMS_FLAG:
            kwargs = {
                'team': args[0],
                'nick': args[1],
                'points': int(args[2]),
            }
            self.__perform_listeners(ServerEvent.ELIM_TEAMS_FLAG, args, kwargs)
        elif event_type == ServerEvent.ROUND_STARTED:
            kwargs = dict()
            self.__perform_listeners(ServerEvent.ROUND_STARTED, args, kwargs)
        elif event_type == ServerEvent.TEAM_SWITCHED:
            new_args = tuple([arg for arg in args if arg])
            kwargs = {
                'nick': new_args[0],
                'old_team': new_args[1] if len(new_args) > 2 else 'Observer',
                'new_team': new_args[2] if len(new_args) > 2 else new_args[1]
            }
            if kwargs['new_team'] == 'observing':
                kwargs['new_team'] = 'Observer'
                kwargs['old_team'] = None
            self.__perform_listeners(ServerEvent.TEAM_SWITCHED, new_args, kwargs)
        elif event_type == ServerEvent.GAME_END:
            kwargs = {
                'score_blue': None,
                'score_red': None,
                'score_purple': None,
                'score_yellow': None,
            }
            teams = args.split(',')
            for t in teams:
                data = t.split(':')
                if data[0] == 'Blue':
                    kwargs['score_blue'] = data[1]
                elif data[0] == 'Red':
                    kwargs['score_red'] = data[1]
                elif data[0] == 'Yellow':
                    kwargs['score_yellow'] = data[1]
                elif data[0] == 'Purple':
                    kwargs['score_purple'] = data[1]
            self.__perform_listeners(ServerEvent.GAME_END,
                                     (kwargs['score_blue'],
                                      kwargs['score_red'],
                                      kwargs['score_yellow'],
                                      kwargs['score_purple']), kwargs)
        elif event_type == ServerEvent.MAPCHANGE:
            kwargs = {
                'mapname': args
            }
            self.__perform_listeners(ServerEvent.MAPCHANGE, (kwargs['mapname'],), kwargs)
        elif event_type == ServerEvent.NAMECHANGE:
            kwargs = {
                'old_nick': args[0],
                'new_nick': args[1]
            }
            self.__perform_listeners(ServerEvent.NAMECHANGE, (kwargs['old_nick'], kwargs['new_nick']), kwargs)

        elif event_type == ServerEvent.DISCONNECT:
            kwargs = {
                'nick': args
            }
            self.__perform_listeners(ServerEvent.DISCONNECT, (kwargs['nick'],), kwargs)
        
        elif event_type == ServerEvent.FLAG_GRAB:
            kwargs = {
                'nick': args[0],
                'flag': args[1],
            }
            self.__perform_listeners(ServerEvent.FLAG_GRAB, (kwargs['nick'], kwargs['flag']), kwargs)
        
        elif event_type == ServerEvent.FLAG_DROP:
            kwargs = {
                'nick': args
            }
            self.__perform_listeners(ServerEvent.FLAG_GRAB, (kwargs['nick'],), kwargs)
            
        elif event_type == ServerEvent.ROUND_END:
            kwargs = dict()
            self.__perform_listeners(ServerEvent.ROUND_END, args, kwargs)
            
        elif event_type == ServerEvent.GAMEMODE:
            kwargs = {
                'gamemode': args
            }
            self.__perform_listeners(ServerEvent.GAMEMODE, args, kwargs)

        asyncio.async(self.get_event_handler(event_type)(**kwargs))

    def get_event_handler(self, event_type):
        return getattr(self, self.handlers[event_type])

    @asyncio.coroutine
    def __parse_line(self, line):
        """
        Tries to match line with all event regexps.

        :param line: Line from logs
        """
        for r in REGEXPS:
            results = r.findall(line)
            e = REGEXPS[r]
            for res in results:
                if e == ServerEvent.CHAT: # For security reasons
                    if self.nicks_valid(res[0]):
                        yield from self.__handle_event(event_type=e, args=res)
                        return
                    else:
                        continue
                yield from self.__handle_event(event_type=e, args=res)

    def rcon(self, command):
        """
        Execute a console command using RCON.

        :param command: Command

        :return: Response from server

        :rtype: str

        :example:
        .. code-block:: python
            :linenos:

            >>> from dplib.server import Server
            >>> s = Server(hostname='127.0.0.1', port=27910, logfile=r'qconsole27910.log', rcon_password='hello')
            >>> s.rcon('sv listuserip')
            'ÿÿÿÿprint\\n mRokita [127.0.0.1:9419]\\nadmin is listing IP for mRokita [127.0.0.1:9419]\\n'

        """
        sock = socket(AF_INET, SOCK_DGRAM)
        sock.connect((self.__hostname, self.__port))
        sock.settimeout(3)
        sock.send(bytes('\xFF\xFF\xFF\xFFrcon {} {}\n'.format(self.__rcon_password, command), 'latin-1'))
        ret = sock.recv(2048).decode('latin-1')
        if ret == '\xFF\xFF\xFF\xFFprint\nBad rcon_password.\n':
            raise BadRconPasswordError('Bad rcon password')
        return ret

    def status(self):
        """
        Execute status query.

        :return: Status string
        :rtype: str
        """
        sock = socket(AF_INET, SOCK_DGRAM)
        sock.connect((self.__hostname, self.__port))
        sock.settimeout(3)
        sock.send(b'\xFF\xFF\xFF\xFFstatus\n')
        return sock.recv(2048).decode('latin-1')

    def permaban(self, ip=None):
        """
        Bans IP address or range of adresses and saves ban list to disk.

        :param ip: IP address to ban

        :return: Rcon response
        :rtype: str

        """
        if ip:
            resp = self.rcon('addip %s' % ip)
            resp += '\n' + self.rcon('writeban')
            return resp
        else:
            raise TypeError('IP address is required.')

    def remove_permaban(self, ip=None):
        """
        Removes ban on IP address and saves ban list to disk.

        :param ip: IP address to unban

        :return: Rcon response
        :rtype: str
        """
        if ip:
            resp = self.rcon('removeip %s' % ip)
            resp += '\n' + self.rcon('writeban')
            return resp
        else:
            raise TypeError('IP address is required.')

    def tempoban(self, id=None, nick=None, duration=3):
        """
        Temporarily bans a player with specified id using rcon

        :param id: Player's id
        :param nick: Player's nick
        :param duration: Ban duration in minutes (defaults to 3)
        
        :return: Rcon response
        :rtype: str
        """
        if type(duration) != int:
            raise TypeError('Ban duration should be an integer, not a ' + str(type(duration)))
        if nick:
            id = self.get_ingame_info(nick).id
        if id:
            return self.rcon('tban %s %s' % (id, str(duration)))
        else:
            raise TypeError('Player id or nick is required.')

    def remove_tempobans(self):
        """
        Removes all temporary bans

        :return: Rcon response
        :rtype: str
        """
        return self.rcon("removetbans")

    def kick(self, id=None, nick=None):
        """
        Kicks a player with id using rcon.

        :param id: Player's id
        :param nick: Player's nick

        :return: Rcon response
        :rtype: str
        """
        if nick:
            id = self.get_ingame_info(nick).id
        if id:
            return self.rcon('kick %s' % id)
        else:
            raise TypeError('Player id or nick is required.')

    def say(self, message):
        """
        Say a message

        :param message: Text, can contain {C} - color char {U} - underline char {I} italic.
        Remember to escape user input using :func:`dplib.parse.escape_braces`.

        :rtype: str
        :return: Rcon response

        :example:

        .. code-block:: python
            :linenos:

            >>> from dplib.server import Server
            >>> s = Server(hostname='127.0.0.1', port=27910, logfile=r'qconsole27910.log', rcon_password='hello')
            >>> s.say('{C}ARed text')
            >>> s.say('{U}Underline{U}')
            >>> s.say('{I}Italic{I}')

        :ingame result:

        .. image:: ..\..\doc\images\say_test.png
        """
        return self.rcon('say "%s"' % render_text(message))

    def cprint(self, message):
        """
        Cprints a message.

        :param message: Text, can contain {C} - color char {U} - underline char {I} italic.
        Remember to escape user input using :func:`dplib.parse.escape_brac

        :return: Rcon response
        :rtype: str
        """
        return self.rcon('sv cprint "%s"' % render_text(message))

    def set_cvar(self, var, value):
        """
        Set a server cvar

        :param var: cvar name
        :param value: value to set

        :return: Rcon response
        :rtype: str
        """
        return self.rcon('set %s "%s"' % (var, value))

    def get_cvar(self, var):
        """
        Gets cvar value

        :param var: Variable name
        :type var: str

        :return: Cvar value
        :rtype: str
        """
        res = self.rcon('"%s"' % var)
        if re.match('^....print\\\nUnknown command \\"%s"\\.\\\n' % re.escape(var), res):
            raise NameError('Cvar "%s" does not exist' % var)
        return re.findall('^....print\\\n\\"%s\\" is \\"(.*?)\\"\\\n' % re.escape(var), res)[0]

    @staticmethod
    def __get_predicate(margs, check):
        """
        Returns a comparator.

        :param margs: Args to check
        :param check: Check function

        :return: Returns a function that compiles the check function and comparision strings
        """
        def predicate(*args):
            if len(args) != len(margs):
                raise TypeError('predicate() takes %d positional arguments but %d were given' % (len(margs), len(args)))
            result = True
            for i, a in enumerate(margs):
                if a:
                    result = result and a == args[i]
            if callable(check):
                result = result and check(*args)
            return result
        return predicate

    @asyncio.coroutine
    def wait_for_entrance(self, timeout=None, nick=None, build=None, addr=None, check=None):
        """
        Waits for entrance.

        :param timeout:  Time to wait for entrance event, if exceeded, returns None.
        :param nick: Player's nick.
        :param build: Player's build.
        :param addr: Player's address (IP:PORT)
        :return:
        """
        future = asyncio.Future(loop=self.loop)
        margs = (nick, build, addr)
        predicate = self.__get_predicate(margs, check)
        self.__listeners[ServerEvent.ENTRANCE].append((predicate, future))
        try:
            data = yield from asyncio.wait_for(future, timeout,
                                               loop=self.loop)
        except asyncio.TimeoutError:
            data = None
        return data

    @asyncio.coroutine
    def wait_for_respawn(self, timeout=None, team=None, nick=None, check=None):
        """
        Waits for respawn event.

        :param timeout: Time to wait for respawn event, if exceeded, returns None.
        :param team: Player's team.
        :param nick: Player's nick.
        :param check: Check function, ignored if none.

        :return: Returns message info dict keys: ('team', 'nick').
        :rtype: dict
        """
        future = asyncio.Future(loop=self.loop)
        margs = (team, nick)
        predicate = self.__get_predicate(margs, check)
        self.__listeners[ServerEvent.RESPAWN].append((predicate, future))
        try:
            data = yield from asyncio.wait_for(future, timeout,
                                               loop=self.loop)
        except asyncio.TimeoutError:
            data = None
        return data

    @asyncio.coroutine
    def wait_for_elim_teams_flag(self, timeout=None, team=None, nick=None, points=None, check=None):
        """
        Waits for elim teams flag event.

        :param timeout: Time to wait for event, if exceeded, returns None.
        :param team: Player's team.
        :param nick: Player's nick.
        :param points: Points scored.
        :type points: int
        :param check: Check function, ignored if none.

        :return: Returns message info dict keys: ('team', 'nick', 'points').
        :rtype: dict
        """
        future = asyncio.Future(loop=self.loop)
        margs = (team, nick, points)
        predicate = self.__get_predicate(margs, check)
        self.__listeners[ServerEvent.ELIM_TEAMS_FLAG].append((predicate, future))
        try:
            data = yield from asyncio.wait_for(future, timeout,
                                               loop=self.loop)
        except asyncio.TimeoutError:
            data = None
        return data

    @asyncio.coroutine
    def wait_for_team_switched(self, timeout=None, nick=None, old_team=None, new_team=None, check=None):
        """
        Waits for team switch event.

        :param timeout: Time to wait for event, if exceeded, returns None.
        :param old_team: Player's old team.
        :param new_team: Player's new team.
        :param nick: Player's nick.
        :param check: Check function, ignored if none.

        :return: Returns message info dict keys: ('nick', 'old_team', 'new_nick').
        :rtype: dict
        """
        future = asyncio.Future(loop=self.loop)
        margs = (nick, old_team, new_team)
        predicate = self.__get_predicate(margs, check)
        self.__listeners[ServerEvent.TEAM_SWITCHED].append((predicate, future))
        try:
            data = yield from asyncio.wait_for(future, timeout,
                                               loop=self.loop)
        except asyncio.TimeoutError:
            data = None
        return data

    @asyncio.coroutine
    def wait_for_round_started(self, timeout=None, check=None):
        """
        Waits for round start.

        :param timeout: Time to wait for event, if exceeded, returns None.
        :param check: Check function, ignored if none.

        :return: Returns an empty dict.
        :rtype: dict
        """
        future = asyncio.Future(loop=self.loop)
        margs = tuple()
        predicate = self.__get_predicate(margs, check)
        self.__listeners[ServerEvent.ROUND_STARTED].append((predicate, future))
        try:
            data = yield from asyncio.wait_for(future, timeout,
                                               loop=self.loop)
        except asyncio.TimeoutError:
            data = None
        return data

    @asyncio.coroutine
    def wait_for_flag_captured(self, timeout=None, team=None, nick=None, flag=None, check=None):
        """
        Waits for flag capture.

        :param timeout: Time to wait for event, if exceeded, returns None.
        :param team: Player's team.
        :param nick: Player's nick.
        :param flag: Captured flag.
        :param check: Check function, ignored if none.

        :return: Returns an empty dict.
        :rtype: dict
        """
        future = asyncio.Future(loop=self.loop)
        margs = (team, nick, flag)
        predicate = self.__get_predicate(margs, check)
        self.__listeners[ServerEvent.FLAG_CAPTURED].append((predicate, future))
        try:
            data = yield from asyncio.wait_for(future, timeout,
                                               loop=self.loop)
        except asyncio.TimeoutError:
            data = None
        return data

    @asyncio.coroutine
    def wait_for_game_end(self, timeout=None, score_blue=None, score_red=None, score_yellow=None, score_purple=None, check=None):
        """
        Waits for game end.

        :param timeout: Time to wait for event, if exceeded, returns None.
        :param score_blue: Blue score
        :param score_red: Red score.
        :param score_yellow: Yellow score.
        :param score_purple: Purple score.
        :param check: Check function, ignored if none.

        :return: Returns an empty dict.
        :rtype: dict
        """
        future = asyncio.Future(loop=self.loop)
        margs = (score_blue, score_red, score_yellow, score_purple)
        predicate = self.__get_predicate(margs, check)
        self.__listeners[ServerEvent.GAME_END].append((predicate, future))
        try:
            data = yield from asyncio.wait_for(future, timeout,
                                               loop=self.loop)
        except asyncio.TimeoutError:
            data = None
        return data

    @asyncio.coroutine
    def wait_for_elim(self, timeout=None, killer_nick=None, killer_weapon=None, victim_nick=None, victim_weapon=None,
                      check=None):
        """
        Waits for elimination event.

        :param timeout: Time to wait for elimination event, if exceeded, returns None.
        :param killer_nick: Killer's nick to match, ignored if None.
        :param killer_weapon: Killer's weapon to match, ignored if None.
        :param victim_nick:  Victim's nick to match, ignored if None.
        :param victim_weapon: Victim's weapon to match, ignored if None.
        :param check: Check function, ignored if None.

        :return: Returns message info dict keys: ('killer_nick', 'killer_weapon', 'victim_nick', 'victim_weapon')
        :rtype: dict
        """
        future = asyncio.Future(loop=self.loop)
        margs = (killer_nick, killer_weapon, victim_nick, victim_weapon)
        predicate = self.__get_predicate(margs, check)
        self.__listeners[ServerEvent.ELIM].append((predicate, future))
        try:
            elim_info = yield from asyncio.wait_for(future, timeout, loop=self.loop)
        except asyncio.TimeoutError:
            elim_info = None
        return elim_info

    @asyncio.coroutine
    def wait_for_mapchange(self, timeout=None, mapname=None, check=None):
        """
        Waits for mapchange.

        :param timeout: Time to wait for elimination event, if exceeded, returns None.
        :param mapname: Killer's nick to match, ignored if None.
        :param check: Check function, ignored if None.

        :return: Returns message info dict keys: ('killer_nick', 'killer_weapon', 'victim_nick', 'victim_weapon')
        :rtype: dict
        """
        future = asyncio.Future(loop=self.loop)
        margs = (mapname,)
        predicate = self.__get_predicate(margs, check)
        self.__listeners[ServerEvent.MAPCHANGE].append((predicate, future))
        try:
            mapchange_info = yield from asyncio.wait_for(future, timeout, loop=self.loop)
        except asyncio.TimeoutError:
            mapchange_info = None
        return mapchange_info

    @asyncio.coroutine
    def wait_for_namechange(self, timeout=None, old_nick=None, new_nick=None, check=None):
        """
        Waits for mapchange.

        :param timeout: Time to wait for elimination event, if exceeded, returns None.
        :param mapname: Killer's nick to match, ignored if None.
        :param check: Check function, ignored if None.

        :return: Returns message info dict keys: ('killer_nick', 'killer_weapon', 'victim_nick', 'victim_weapon')
        :rtype: dict
        """
        future = asyncio.Future(loop=self.loop)
        margs = (old_nick, new_nick)
        predicate = self.__get_predicate(margs, check)
        self.__listeners[ServerEvent.NAMECHANGE].append((predicate, future))
        try:
            mapchange_info = yield from asyncio.wait_for(future, timeout, loop=self.loop)
        except asyncio.TimeoutError:
            mapchange_info = None
        return mapchange_info

    @asyncio.coroutine
    def wait_for_message(self, timeout=None, nick=None, message=None, check=None):
        """
        Waits for a message.

        :param timeout: Time to wait for message, if exceeded, returns None.
        :param nick: Player's nick to match, ignored if None
        :type nick: str
        :param message: Message text to match, ignored if None
        :type message: str
        :param check: Check function, ignored if None
        :return: Returns message info dict keys: ('nick', 'message')
        :rtype: dict

        :example:

        .. code-block:: python
            :linenos:

            @s.event
            def on_chat(nick, message):
                if message == '!start' and not elim_active:
                    msg = yield from s.wait_for_message(check=lambda n, m: m.startswith('!hi '))
                    s.say('Hi ' + msg['message'].split('!hi ')[1] + '!')

        """
        future = asyncio.Future(loop=self.loop)
        margs = (nick, message)
        predicate = self.__get_predicate(margs, check)
        self.__listeners[ServerEvent.CHAT].append((predicate, future))
        try:
            message = yield from asyncio.wait_for(future, timeout,
                                                  loop=self.loop)
        except asyncio.TimeoutError:
            message = None
        return message

    @asyncio.coroutine
    def wait_for_flag_drop(self, timeout=None, nick=None, check=None):
        """
        Waits for flag drop.

        :param timeout: Time to wait for event, if exceeded, returns None.
        :param nick: Player's nick.
        :param flag: dropped flag.
        :param check: Check function, ignored if none.

        :return: Returns an empty dict.
        :rtype: dict
        """
        future = asyncio.Future(loop=self.loop)
        margs = (nick)
        predicate = self.__get_predicate(margs, check)
        self.__listeners[ServerEvent.FLAG_DROP].append((predicate, future))
        try:
            data = yield from asyncio.wait_for(future, timeout,
                                               loop=self.loop)
        except asyncio.TimeoutError:
            data = None
        return data

    def start(self, scan_old=False, realtime=True, debug=False):
        """
        Main loop.

        :param scan_old: Scan present logfile data
        :type scan_old: bool
        :param realtime: Wait for incoming logfile data
        :type realtime: bool
        """
        if not (self.__logfile_name or self.__pty_master):
            raise AttributeError("Logfile name or PTY slave is required.")
        self.__alive = True
        self.__log_file = open(self.__logfile_name, 'rb') if self.__logfile_name else None
        if not scan_old and self.__log_file:
            self.__log_file.readlines()
        if self.__pty_master:
            buf = ''
        if realtime:
            while self.__alive:
                if self.__log_file:
                    line = self.__log_file.readline().decode('latin-1')
                elif self.__pty_master:
                    if '\n' not in buf:
                        buf += os.read(self.__pty_master, 128).decode('latin-1')
                    l = buf.splitlines(keepends=True)
                    if l and '\n' in l[0]:
                        line = l[0]
                        buf = ''.join(l[1:])
                    else:
                        line = None
                if line:
                    if debug:
                        print("[DPLib] %s" % line.strip())
                    yield from self.__parse_line(line)
                yield from asyncio.sleep(0.05)

        if self.__log_file:
            self.__log_file.close()

    def get_players(self):
        """
        Gets playerlist.

        :return: List of :class:`.Player` instances
        :rtype: list
        """
        response = self.rcon('sv players')
        response = re.findall('(\d+) \\(?(.*?)\\)?\\] \\* (?:OP \d+, )?(.+) \\((b\d+)\\)', response)
        players = list()
        for p_data in response:
            player = Player(nick=p_data[2],
                            id=p_data[0],
                            dplogin=p_data[1],
                            build=p_data[3],
                            server=self)
            players.append(player)
        return players

    def get_simple_playerlist(self):
        """
        Get a list of player names

        :return: List of nicks
        :rtype: list
        """
        status = self.get_status()
        players = status['players']
        playerlist = []
        for p in players:
            playerlist.append(p['name'])
        return playerlist

    def get_status(self):
        """
        Gets server status

        :example:
        .. code-block:: python
            :linenos:

            >>> s = Server(hostname='127.0.0.1', port=27910, logfile=r'C:\Games\Paintball2\pball\qconsole27910.log', rcon_password='hello')
            >>> s.get_status()
            {'players': [{'score': '0', 'ping': '13', 'name': 'mRokita'}], 'sv_certificated': '1', 'mapname': 'beta/wobluda_fix', 'TimeLeft': '20:00', '_scores': 'Red:0 Blue:0 ', 'gamename': 'Digital Paint Paintball 2 v1.930(186)', 'gameversion': 'DPPB2 v1.930(186)', 'sv_login': '1', 'needpass': '0', 'gamedate': 'Aug 10 2015', 'protocol': '34', 'version': '2.00 x86 Aug 10 2015 Win32 RELEASE (41)', 'hostname': 'asdfgh', 'elim': 'airtime', 'fraglimit': '50', 'timelimit': '20', 'gamedir': 'pball', 'game': 'pball', 'maxclients': '8'}

        :return: status dict
        :rtype: dict
        """
        dictionary = {}
        players = []
        response = self.status().split('\n')[1:]
        variables = response[0]
        players_str = (response[1:])
        for i in players_str:
            if not i:
                continue
            temp_dict = {}
            cleaned_name = decode_ingame_text(i)
            separated = cleaned_name.split(' ')
            temp_dict['score'] = separated[0]
            temp_dict['ping'] = separated[1]
            temp_dict['name'] = cleaned_name.split("%s %s " % (separated[0], separated[1]))[1][1:-1]
            players.append(temp_dict)
        dictionary['players'] = players
        variables = variables.split('\\')[1:]
        for i in range(0, len(variables), 2):
            dictionary[variables[i]] = variables[i + 1]
        return dictionary

    def get_ingame_info(self, nick):
        """
        Get ingame info about a player with nickname

        :param nick: Nick

        :return: An instance of :class:`.Player`
        """
        players = self.get_players()
        for p in players:
            if p.nick == nick:
                return p
        return None

    def run(self, scan_old=False, realtime=True, debug=False):
        """
        Runs the main loop using asyncio.

        :param scan_old: Scan present logfile data
        :type scan_old: bool
        :param realtime: Wait for incoming logfile data
        :type realtime: bool
        """
        if self.__init_vars and self.__rcon_password:
            blockednames = self.get_cvar('sv_blockednames')
            if not 'maploaded' in blockednames.split(','):
                # A player with name "maploaded" would block the mapchange event
                self.set_cvar('sv_blockednames', ','.join([blockednames, 'maploaded']))
        self.loop.run_until_complete(self.start(scan_old, realtime, debug))
