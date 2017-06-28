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
    def __init__(self, server, id, dplogin, nick, build):
        self.server = server
        self.id = id
        self.dplogin = dplogin
        self.nick = nick
        self.build = build

class Server(object):
    __ALLOWED_EVENTS = ['on_chat', 'on_elim', 'on_respawn']

    def __init__(self, hostname, port, logfile=None, rcon_password=None):
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
        pass

    @asyncio.coroutine
    def on_elim(self, killer_nick, killer_weapon, victim_nick, victim_weapon):
        pass

    @asyncio.coroutine
    def on_entered(self, nick, ip):
        pass

    @asyncio.coroutine
    def on_respawn(self, team, nick):
        print(team, nick)

    def event(self, func):
        if func.__name__ in self.__ALLOWED_EVENTS:
            setattr(self, func.__name__, asyncio.coroutine(func))
            return func
        else:
            raise Exception('Event \'%s\' doesn\'t exist' % func.__name__)

    def stop_listening(self):
        self.__alive = False

    def perform_listeners(self, event_type, args, kwargs):
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
        kwargs = dict()
        if event_type == ServerEvent.CHAT:
            kwargs = {
                'nick': args[0],
                'message': args[1]
            }
            self.perform_listeners(ServerEvent.CHAT, args, kwargs)
        elif event_type == ServerEvent.ELIM:
            kwargs = {
                'killer_nick': args[0],
                'killer_weapon': args[1],
                'victim_nick': args[2],
                'victim_weapon': args[3]
            }
            self.perform_listeners(ServerEvent.ELIM, args, kwargs)
        elif event_type == ServerEvent.RESPAWN:
            kwargs = {
                'team': args[0],
                'nick': args[1],
            }
            self.perform_listeners(ServerEvent.RESPAWN, args, kwargs)
        asyncio.async(getattr(self, self.handlers[event_type])(**kwargs))

    @asyncio.coroutine
    def __parse_line(self, line):
        for r in REGEXPS:
            results = r.findall(line)
            for res in results:
                yield from self.__handle_event(event_type=REGEXPS[r], args=res)

    def rcon(self, command):
        sock = socket(AF_INET, SOCK_DGRAM)
        sock.connect((self.__hostname, self.__port))
        sock.settimeout(3)
        sock.send(bytes('\xFF\xFF\xFF\xFFrcon {} {}\n'.format(self.__rcon_password, command), 'latin-1'))
        return sock.recv(2048).decode('latin-1')

    def kick(self, id=None, nick=None):
        if nick:
            id = self.get_ingame_info(nick).id
        if id:
            self.rcon('kick %s' % id)
        else:
            raise TypeError('Player id or nick is required.')

    def say(self, message):
        self.rcon('say "%s"' % message.format(C=chr(136), U=chr(134), I=chr(135)))

    def set_cvar(self, var, value):
        self.rcon('set %s "%s"' % (var, value))

    def get_predicate(self, margs, check):
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

        :param scan_old:
        :param realtime:
        :return:
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
        players = self.get_players()
        for p in players:
            if p.nick == nick:
                return p
        return None

    def run(self):
        self.loop.run_until_complete(self.start())
