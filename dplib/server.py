import re
from enum import Enum
import asyncio
from socket import socket, AF_INET, SOCK_DGRAM

from dplib.parse import render_text


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


class ListenerType(Enum):
    PERMANENT = 0
    TRIGGER_ONCE = 1


REGEXPS = {
    re.compile('^\\[\d\d:\d\d:\d\d\\] (?:(?:\\[OBS\\] )|(?:\\[ELIM\\] ))?(.*?): (.+).'): ServerEvent.CHAT,
    # [19:54:18] hTml: test
    re.compile('^\\[\d\d:\d\d:\d\d\\] \\*(.*?) \\((.*?)\\) eliminated \\*(.*?) \\((.*?)\\).'): ServerEvent.ELIM,
    # [18:54:24] *|ACEBot_1| (Spyder SE) eliminated *|herself| (Spyder SE).
    re.compile('^\\[\d\d:\d\d:\d\d\\] \\*(.*?)\\\'s (.*?) revived!'): ServerEvent.RESPAWN,
    # [19:03:57] *Red's ACEBot_6 revived!
    re.compile('^\\[\d\d:\d\d:\d\d\\] (.*?) entered the game \\((.*?)\\) \\[(.*?)\\]'): ServerEvent.ENTRANCE,
    # [19:03:57] mRokita entered the game (build 41) [127.0.0.1:22345]
    re.compile('^\\[\d\d:\d\d:\d\d\\] \\*(.*?)\\\'s (.*?) returned the(?: \\*(.*?))? flag!'): ServerEvent.FLAG_CAPTURED,
    # [18:54:24] *Red's hTml returned the *Blue flag!
    re.compile('^\\[\d\d:\d\d:\d\d\\] \\*(.*?)\\\'s (.*?) earned (\d+) points for possesion of eliminated teams flag!'):
        ServerEvent.ELIM_TEAMS_FLAG,
    # [19:30:23] *Blue's mRokita earned 3 points for possesion of eliminated teams flag!
    re.compile('^\\[\d\d:\d\d:\d\d\\] Round started\\.\\.\\.'): ServerEvent.ROUND_STARTED,
    # [10:20:11] Round started...
    re.compile(
        '(?:^\\[\d\d:\d\d:\d\d\\] (.*?) switched from \\*((?:Red)|(?:Purple)|(?:Blue)|(?:Yellow))'
        ' to \\*((?:Red)|(?:Purple)|(?:Blue)|(?:Yellow))\\.)|'
        '(?:^\\[\d\d:\d\d:\d\d\\] (.*?) joined the \\*((?:Red)|(?:Purple)|(?:Blue)|(?:Yellow)) team\\.)|'
        '(?:^\\[\d\d:\d\d:\d\d\\] (.*?) is now (observing)?\\.)'): ServerEvent.TEAM_SWITCHED,
    # [10:20:11] mRokita switched from Blue to Red.
    # [10:20:11] mRokita is now observing.
    # [10:20:11] mRokita joined the Blue team.


}

CHAR_TAB = ['\0', '-', '-', '-', '_', '*', 't', '.', 'N', '-', '\n', '#', '.', '>', '*', '*',
            '[', ']', '@', '@', '@', '@', '@', '@', '<', '>', '.', '-', '*', '-', '-', '-',
            ' ', '!', '\"', '#', '$', '%', '&', '\'', '(', ')', '*', '+', ',', '-', '.', '/',
            '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', ':', ';', '<', '=', '>', '?',
            '@', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O',
            'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '[', '\\', ']', '^', '_',
            '`', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o',
            'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', '{', '|', '}', '~', '<',
            '(', '=', ')', '^', '!', 'O', 'U', 'I', 'C', 'C', 'R', '#', '?', '>', '*', '*',
            '[', ']', '@', '@', '@', '@', '@', '@', '<', '>', '*', 'X', '*', '-', '-', '-',
            ' ', '!', '\"', '#', '$', '%', '&', '\'', '(', ')', '*', '+', ',', '-', '.', '/',
            '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', ':', ';', '<', '=', '>', '?',
            '@', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O',
            'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '[', '\\', ']', '^', '_',
            '`', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O',
            'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '{', '|', '}', '~', '<']


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
    """

    def __init__(self, hostname, port=27910, logfile=None, rcon_password=None):
        self.__rcon_password = rcon_password
        self.__hostname = hostname
        self.__port = port
        self.__logfile_name = logfile
        self.__log_file = None
        self.__alive = False
        self.handlers = {
            ServerEvent.CHAT: 'on_chat',
            ServerEvent.ELIM: 'on_elim',
            ServerEvent.RESPAWN: 'on_respawn',
            ServerEvent.ENTRANCE: 'on_entrance',
            ServerEvent.FLAG_CAPTURED: 'on_flag_captured',
            ServerEvent.ELIM_TEAMS_FLAG: 'on_elim_teams_flag',
            ServerEvent.ROUND_STARTED: 'on_round_started',
            ServerEvent.TEAM_SWITCHED: 'on_team_switched',
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
        }
        self.loop = asyncio.get_event_loop()

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
        :type flag: int
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
    def on_elim(self, killer_nick, killer_weapon, victim_nick, victim_weapon):
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

    @asyncio.coroutine
    def __handle_event(self, event_type, args):
        """
        Handles an event.

        :param event_type: Event type, one of members :class:`ServerEvent`
        :param args: Event info (re.findall() results)
        """
        kwargs = dict()
        if event_type == ServerEvent.CHAT:
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
            new_args = [arg for arg in args if arg]
            kwargs = {
                'nick': new_args[0],
                'old_team': new_args[1] if len(new_args) > 2 else 'Observer',
                'new_team': new_args[2] if len(new_args) > 2 else new_args[1]
            }
            if kwargs['new_team'] == 'observing':
                kwargs['new_team'] = 'Observer'
                kwargs['old_team'] = None
            self.__perform_listeners(ServerEvent.TEAM_SWITCHED, new_args, kwargs)
        asyncio.async(getattr(self, self.handlers[event_type])(**kwargs))

    @asyncio.coroutine
    def __parse_line(self, line):
        """
        Tries to match line with all event regexps.

        :param line: Line from logs
        """
        print([line])
        for r in REGEXPS:
            results = r.findall(line)
            for res in results:
                yield from self.__handle_event(event_type=REGEXPS[r], args=res)

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
        margs = tuple()
        predicate = self.__get_predicate(margs, check)
        self.__listeners[ServerEvent.FLAG_CAPTURED].append((predicate, future))
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

    def start(self, scan_old=False, realtime=True):
        """
        Main loop.

        :param scan_old: Scan present logfile data
        :type scan_old: bool
        :param realtime: Wait for incoming logfile data
        :type realtime: bool
        """
        self.__alive = True
        self.__log_file = open(self.__logfile_name, 'rb')
        if not scan_old:
            self.__log_file.readlines()
        if realtime:
            while self.__alive:
                line = self.__log_file.readline()
                while line and line.decode('latin-1')[-1] != '\n':
                    yield from asyncio.sleep(0.05)
                    line += self.__log_file.readline()
                if line:
                    yield from self.__parse_line(line.decode('latin-1'))

                yield from asyncio.sleep(0.05)
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

    def run(self, scan_old=False, realtime=True):
        """
        Runs the main loop using asyncio.

        :param scan_old: Scan present logfile data
        :type scan_old: bool
        :param realtime: Wait for incoming logfile data
        :type realtime: bool
        """
        self.loop.run_until_complete(self.start(scan_old, realtime))
