import re
from enum import Enum
import asyncio
from socket import socket, AF_INET, SOCK_DGRAM


class ServerEvent(Enum):
    TIMEOUT = 0
    CHAT = 1
    ELIM = 2
    RESPAWN = 3
    MAPCHANGE = 4
    DATE = 5
    NAMECHANGE = 6

class ListenerType(Enum):
    PERMANENT = 0
    TRIGGER_ONCE = 1

REGEXPS =  {
    re.compile('^\\[\d\d\\:\d\d\\:\d\d\\]\\ (.*?)\\: (.+).'): ServerEvent.CHAT,
    # [19:54:18] hTml: test
    re.compile('^\\[\d\d\\:\d\d\\:\d\d\\]\\ \\*(.*?)\\ \\((.*?)\\)\\ eliminated\\ \\*(.*?)\\ \\((.*?)\\).'): ServerEvent.ELIM,
    # [18:54:24] *|ACEBot_1| (Spyder SE) eliminated *|herself| (Spyder SE).
    re.compile('^\\[\d\d\\:\d\d\\:\d\d\\]\\ \\*(.*?)\\\'s\\ (.*?)\\ revived\\!'): ServerEvent.RESPAWN,
    # [19:03:57] *Red's ACEBot_6 revived!
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
    :type port: str
    :param logfile: Path to logfile
    :param rcon_password: rcon password
    """
    __ALLOWED_EVENTS = ['on_chat', 'on_elim', 'on_respawn']

    def __init__(self, hostname, port=27910, logfile=None, rcon_password=None):
        self.__rcon_password = rcon_password
        self.__hostname = hostname
        self.__port = port
        self.__logfile_name = logfile
        self.handlers = {
            ServerEvent.CHAT: 'on_chat',
            ServerEvent.ELIM: 'on_elim',
            ServerEvent.RESPAWN: 'on_respawn',
        }
        self.__listeners = {
            ServerEvent.CHAT: [],
            ServerEvent.ELIM: [],
            ServerEvent.RESPAWN: [],
        }
        self.loop = asyncio.get_event_loop()

    @asyncio.coroutine
    def on_chat(self, nick, message):
        """
        On chat, can be overridden using the :func:`.Server.event`.

        :param nick: Player's nick
        :type nick: str
        :param message: Message
        :type message: str
        """
        pass

    @asyncio.coroutine
    def on_elim(self, killer_nick, killer_weapon, victim_nick, victim_weapon):
        """
        On elim can be overridden using the :func:`.Server.event`.

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
    def on_entered(self, nick, ip):
        """
        Not implemented yet.

        :param nick:
        :param ip:
        """
        pass

    @asyncio.coroutine
    def on_respawn(self, team, nick):
        """
        On respawn, can be overridden using the :func:`.Server.event`.

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
            >>> s = Server(hostname='127.0.0.1', port=27910, logfile=r'C:\Games\Paintball2\pball\qconsole27910.log', rcon_password='hello')
            >>> @s.event
            ... def on_chat(nick, message):
            ...     print((nick, message))
            ...
            >>> s.run()
            ('mRokita', 'Hi')
        """
        if func.__name__ in self.__ALLOWED_EVENTS:
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
                'message': args[1]
            }
            self.__perform_listeners(ServerEvent.CHAT, args, kwargs)
        elif event_type == ServerEvent.ELIM:
            kwargs = {
                'killer_nick': args[0],
                'killer_weapon': args[1],
                'victim_nick': args[2],
                'victim_weapon': args[3]
            }
            self.__perform_listeners(ServerEvent.ELIM, args, kwargs)
        elif event_type == ServerEvent.RESPAWN:
            kwargs = {
                'team': args[0],
                'nick': args[1],
            }
            self.__perform_listeners(ServerEvent.RESPAWN, args, kwargs)
        asyncio.async(getattr(self, self.handlers[event_type])(**kwargs))

    @asyncio.coroutine
    def __parse_line(self, line):
        """
        Tries to match line with all event regexps.

        :param line: Line from logs
        """
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
            >>> s = Server(hostname='127.0.0.1', port=27910, logfile=r'C:\Games\Paintball2\pball\qconsole27910.log', rcon_password='hello')
            >>> s.rcon('sv listuserip')
            'ÿÿÿÿprint\\n mRokita [127.0.0.1:9419]\\nadmin is listing IP for mRokita [127.0.0.1:9419]\\n'

        """
        sock = socket(AF_INET, SOCK_DGRAM)
        sock.connect((self.__hostname, self.__port))
        sock.settimeout(3)
        sock.send(bytes('\xFF\xFF\xFF\xFFrcon {} {}\n'.format(self.__rcon_password, command), 'latin-1'))
        return sock.recv(2048).decode('latin-1')

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

        :param message: text, can contain {C} - color char {U} - underline char {I} italic

        :rtype: str
        :return: Rcon response

        :example:
        .. code-block:: python
            :linenos:

            >>> from dplib.server import Server
            >>> s = Server(hostname='127.0.0.1', port=27910, logfile=r'C:\Games\Paintball2\pball\qconsole27910.log', rcon_password='hello')
            >>> s.say('{C}ARed text')
            >>> s.say('{U}Underline{U}')
            >>> s.say('{I}Italic{I}')

        :ingame result:

        .. image:: ..\..\doc\images\say_test.png
        """
        return self.rcon('say "%s"' % message.format(C=chr(136), U=chr(134), I=chr(135)))

    def set_cvar(self, var, value):
        """
        Set a server cvar

        :param var: cvar name
        :param value: value to set

        :return: Rcon response
        :rtype: str
        """
        return self.rcon('set %s "%s"' % (var, value))

    def __get_predicate(self, margs, check):
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
    def wait_for_respawn(self, timeout=None, team=None, nick=None, check=None):
        """
        Waits for respawn event.

        :param timeout: Time to wait for respawn event, if exceeded, returns None.
        :param team:
        :param nick:
        :param check: Check function, ignored if none

        :return: Returns message info dict keys: ('killer_nick', 'message')('killer_nick', 'killer_weapon', 'victim_nick', 'victim_weapon')
        :rtype: dict
        """
        future = asyncio.Future(loop=self.loop)
        margs = (team, nick)
        predicate = self.get_predicate(margs, check)
        self.__listeners[ServerEvent.RESPAWN].append((predicate, future))
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
        :param killer_nick: Killer's nick to match, ignored if None
        :param killer_weapon: Killer's weapon to match, ignored if None
        :param victim_nick:  Victim's nick to match, ignored if None
        :param victim_weapon: Victim's weapon to match, ignored if None
        :param check: Check function, ignored if none

        :return: Returns message info dict keys: ('killer_nick', 'message')('killer_nick', 'killer_weapon', 'victim_nick', 'victim_weapon')
        :rtype: dict
        """
        future = asyncio.Future(loop=self.loop)
        margs = (killer_nick, killer_weapon, victim_nick, victim_weapon)
        predicate = self.get_predicate(margs, check)
        self.__listeners[ServerEvent.ELIM].append((predicate, future))
        try:
            elim_info = yield from asyncio.wait_for(future, timeout,
                                                  loop=self.loop)
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
        :type messsage: str
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
        predicate = self.get_predicate(margs, check)
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
        response = re.findall('(\d+)\\ \\(?(.*?)\\)?\\]\\ \\*\\ (?:OP\\ \d+\\,\\ )?(.+)\\ \\((b\d+)\\)', response)
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
