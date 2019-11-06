#!/usr/bin/python3
import asyncio
import shlex
import signal
import subprocess
import os
from builtins import Exception
from shlex import quote
from threading import Thread
import string
import random
from time import sleep
import aioftp

from _socket import timeout

from dplib.server import Server, GameMode

LAUNCH_TIMEOUT = 10
PAINTBALL_DIR = '/home/paintball/paintball2/'


def get_map_download_path(mapname):
    return os.path.join('pball', 'maps', mapname + '.bsp')


def get_map_server_path(mapname):
    return os.path.join('pball', 'maps', mapname + '.bsp')


class ChatCommand:
    name = None
    arg_names = []
    argc_min = None
    default_help_enabled = True
    help = []
    only_admin = False

    class InvalidArgumentsException(Exception):
        def __init__(self, message):
            super().__init__(message)

    class InsufficientPrivilegesException(Exception):
        def __init__(self, message):
            super().__init__(message)

    class UnhandledException(Exception):
        def __init__(self, message):
            super().__init__(message)

    def __init__(self, managed_server):
        self.managed_server = managed_server

    async def check_privileges(self, nick):
        if self.only_admin:
            is_admin = await self.managed_server.is_admin(nick)
            if not is_admin:
                raise ChatCommand.InsufficientPrivilegesException(
                    "Only server admin can run this command")

    async def check_arguments(self, args):
        if self.argc_min is None or self.argc_min == len(self.arg_names):
            self.argc_min = len(self.arg_names)
            arg_msg = 'exactly %d' % len(self.arg_names)
        elif self.argc_min <= len(self.arg_names):
            arg_msg = 'from %d to %d' % (self.argc_min, len(self.arg_names))
        else:
            raise ValueError("arg_min has to lesser than or equal to len(arg_names)")

        if not (self.argc_min <= len(args) <= len(self.arg_names)):
            raise ChatCommand.InvalidArgumentsException(
                message="This command takes %s arguments (%d given)"
                        % (arg_msg, len(args)))

    async def call(self, nick, *args):
        try:
            await self.check_privileges(nick)
            await self.check_arguments(args)
            await self.process(**dict(zip(self.arg_names, args)))
        except ChatCommand.InvalidArgumentsException as e:
            self.managed_server.say("{C}9%s" % e)
            if self.help:
                self.managed_server.say(
                    "{C}9Type !help %s for help" % self.name)
        except ChatCommand.InsufficientPrivilegesException as e:
            self.managed_server.say("{C}9%s" % e)
        except ChatCommand.UnhandledException as e:
            self.managed_server.say("{C}AERROR: {C}9%s" % e)

    async def process(self, **kwargs):
        pass

    def say_help(self):
        for h in self.help:
            self.managed_server.say(h)
        if self.default_help_enabled:
            self.managed_server.say(
                "{C}9Usage: !%s %s" % (
                    self.name,
                    ' '.join('<%s>' % n for n in self.arg_names)
                )
            )


class KickChatCommand(ChatCommand):
    name = 'kick'
    only_admin = True
    arg_names = ['nick']

    async def process(self, nick=None):
        try:
            print(self.managed_server.kick(nick=nick))
        except ValueError as e:
            raise ChatCommand.UnhandledException(str(e))


class RemoveBotChatCommand(ChatCommand):
    name = 'remove_bot'
    only_admin = True
    arg_names = ['nick']

    async def process(self, nick=None):
        try:
            print(self.managed_server.remove_bot(nick=nick))
        except ValueError as e:
            raise ChatCommand.UnhandledException(str(e))


class AddBotChatCommand(ChatCommand):
    name = 'add_bot'
    only_admin = True
    arg_names = ['nick']
    argc_min = 0

    async def process(self, nick=None):
        print(self.managed_server.add_bot(nick=nick))


class CvarSetChatCommand(ChatCommand):
    name = 'set'
    arg_names = ['cvar', 'value']
    only_admin = True
    enabled_cvars = (
        'elim',
        'fraglimit',
        'timelimit',
        'guntemp_inc',
        'flagcapendsround',
        'floodprotect',
        'sv_gravity',
        'hostname',
        'grenadeffire',
        'ffire',
        'gren_explodeonimpact'
    )

    help = ['{C}9Available cvars:', '{C}9' + ', '.join(enabled_cvars)]

    async def check_arguments(self, args):
        await super().check_arguments(args)
        cvar = args[0]
        if cvar not in self.enabled_cvars:
            raise ChatCommand.InvalidArgumentsException(
                "Setting \"%s\" is not allowed" %cvar)

    def process(self, cvar, value):
        try:
            self.managed_server.set_cvar(cvar, value)
            new_value = self.managed_server.get_cvar(cvar)
            if new_value != value:
                raise ChatCommand.InvalidArgumentsException(
                    "Couldn't set %s" % cvar)
            self.managed_server.say("{C}9%s is now \"%s\"" % (cvar, new_value))
        except NameError:
            raise ChatCommand.InvalidArgumentsException(
                "Cvar \"%s\" does not exist" % cvar)


class MapChatCommand(ChatCommand):
    name = 'map'
    only_admin = True
    argc_min = 1
    arg_names = ['mapname', 'gamemode']

    async def check_arguments(self, args):
        await super().check_arguments(args)
        mapname = args[0]
        if os.path.realpath(get_map_download_path(mapname)).find(
                '/home/paintball/paintball2/pball/maps') != 0:
            raise ChatCommand.InvalidArgumentsException("Nice try, noob")
        if len(args) == 2:
            gamemode = args[1]
            if not GameMode.is_valid(gamemode):
                raise ChatCommand.InvalidArgumentsException(
                    "Invalid gamemode %s. Available gamemodes: %s" %
                    (gamemode,
                    ', '.join(GameMode.get_list()))
                )

    async def process(self, mapname, gamemode=None):
        if os.path.realpath(get_map_download_path(mapname)).find(
                '/home/paintball/paintball2/pball/maps') != 0:
            raise ValueError("Nice try, noob")
        if os.path.exists(get_map_download_path(mapname)):
            self.managed_server.say(
                "{C}9Map {C}A" + mapname + "{C}9 is already on the server, changing")

        else:
            async with aioftp.ClientSession("ic3y.de", 21) as client:
                if await client.exists(get_map_server_path(mapname)):
                    self.managed_server.say(
                        "{C}9Downloading {C}A" + mapname + "{C}9 from ic3y.de...")
                    await client.download(get_map_server_path(mapname),
                                          get_map_download_path(mapname),
                                          write_into=True)
                    self.managed_server.say(
                        "{C}A%s {C}9has been downloaded successfully,"
                        " changing map..." % mapname
                    )
                else:
                    raise ChatCommand.UnhandledException(
                        "Map {C}A %s {C}9 "
                        "is not available at ic3y.de" % mapname)

            maps = []
            for r, d, f in os.walk(
                    os.path.join(PAINTBALL_DIR, 'pball', 'maps')):
                for file in f:
                    fpath = os.path.join(r, file)
                    if '.bsp' in file and 'pbcup.bsp' not in file and mapname + '.bsp' not in fpath:
                        maps.append(fpath)
            if len(maps) > 10:
                for p in maps[10:]:
                    os.remove(p)
        self.managed_server.new_map(mapname, gamemode)


class HelpChatCommand(ChatCommand):
    name = 'help'
    arg_names = ['command']
    argc_min = 0

    async def check_arguments(self, args):
        await super().check_arguments(args)
        if args:
            command = args[0]
            for c in self.managed_server.chat_commands:
                if c.name == command:
                    return
            raise ChatCommand.InvalidArgumentsException(
                "Command !%s does not exist. Use !help to see all commands."
            % command)

    async def process(self, command=None):
        if not command:
            self.managed_server.say(
                "{C}9Available commands:")
            self.managed_server.say(
                '{C}9, '.join(
                    ['{C}G!' + c.name for c in
                     self.managed_server.chat_commands]
                )
            )
            return
        for c in self.managed_server.chat_commands:
            if command == c.name:
                c.say_help()
                return


class ManagedServer(Server):
    port = 27910
    server_id = 'fun_serv'
    chat_commands = [MapChatCommand, CvarSetChatCommand, AddBotChatCommand, RemoveBotChatCommand, HelpChatCommand]
    rcon_password = ''.join(
        random.choice(string.ascii_letters) for i in range(10))

    game_launch_args = [
        ['set', 'public', '1'],
        ['setmaster', 'dplogin.com'],
        ['set', 'rot_file', '""'],
        ['set', 'maxclients', '16'],
        ['map', 'pbcup'],
        ['sv', 'rotation', 'clear'],
        ['sv', 'rotation', 'add', 'pbcup'],
    ]

    default_cvars = {
        'hostname': 'mrokita`s fun serv',
        'flagcapendsround': 0,
        'guntemp_inc': 0,
        'sv_votemapenabled': 0,
        'grenadeffire': 0,
        'elim': 10,
        'ffire': 0,
        'floodprotect': 0,
    }

    def __init__(self):
        self.__pid = None
        self.admins = list()
        self.restart = None
        self.chat_commands = [c(self) for c in self.chat_commands]
        super(ManagedServer, self).__init__(
            hostname='localhost',
            port=self.port,
            rcon_password=self.rcon_password,
        )

    async def is_admin(self, nick=None, player=None):
        player = player or await self.wait_for_ingame_info(nick)
        return (player or nick) in self.admins

    async def new_admin(self, nick=None, player=None):
        player = player or await self.wait_for_ingame_info(
            nick,
            sleep_interval=.2,
            max_tries=5)
        if not player:
            raise ValueError("%s is not on the server." % player)
        if not player.dplogin:
            raise ValueError("%s: A DPLogin is required to be an admin." % nick)
        if player.is_bot:
            raise TypeError("Specified player is bot")
        if await self.is_admin(player, nick):
            raise ValueError("%s is an admin already." % nick)
        self.admins.append(player)
        return player

    def get_game_launch_args(self):
        args = [
            ['set', 'dedicated', '1'],
            ['set', 'rcon_password', self.rcon_password]
        ]
        args.extend(self.game_launch_args)
        return args

    def set_default_cvars(self):
        for c in self.default_cvars:
            self.set_cvar(c, self.default_cvars[c])

    async def on_entrance(self, nick, build, addr):
        if not self.admins:
            if self.admins:
                self.admins = list()
            try:
                admin = await self.new_admin(nick)
                self.say("{C}9" + admin.nick +
                         ' {C}9({C}G' + admin.dplogin
                         + '{C}9) is now admin.')
                self.say('{C}9Type {C}G!help{C}9 for command list.')
            except ValueError as e:
                self.say("{C}9%s" % e)
            except TypeError:
                pass

    async def on_disconnect(self, nick):
        if await self.is_admin(nick):
            if not [p for p in self.get_players() if not p.is_bot]:
                self.kill(restart=True)
                self.admins.remove(nick)
            else:
                self.say("{C}9All admins have disconnected, changing map in 10 seconds...")
                if not await self.wait_for_entrance(10, nick):
                    self.say("{C}9No admin for more than 10 seconds, changing the map")
                    self.set_default_cvars()
                    self.new_map('pbcup')
                    self.admins.remove(nick)

    async def on_chat(self, nick, message):
        if not message.find('!') == 0:
            return
        try:
            command_name, *args = shlex.split(message[1:])
        except ValueError:
            self.say("{C}9Invalid syntax.")
            return
        for command in self.chat_commands:
            if command_name == command.name:
                await command.call(nick, *args)

    def start_event_service(self):
        t = Thread(target=self.run,
                    kwargs={'debug': True, 'make_secure': False})
        t.start()

    def start_server(self):
        self.__kill_game_process()
        self._pty_master, self._pty_slave = os.openpty()
        process = subprocess.Popen(self.get_run_command(),
                                   stdout=self._pty_slave,
                                   stdin=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL,
                                   preexec_fn=os.setsid,
                                   shell=False)

        self.pid = process.pid
        self.make_secure()
        self.start_event_service()
        port = self.get_cvar('port')
        self.set_default_cvars()
        if not port:
            print("[ERROR] Couldn't start server %s" % self.server_id)
            self.__kill_game_process()
        else:
            print("[SUCCESS] Server %s is running on 127.0.0.1:%s. PID: %d" %
                  (self.server_id, port, self.pid))
        print('done')

    def get_run_command(self) -> str:
        command = './paintball2'
        for c in self.get_game_launch_args():
            command += ' +' + ' '.join(quote(i) for i in c)
        print(command)
        return shlex.split(command)

    @property
    def pid(self):
        return self.__pid

    @pid.setter
    def pid(self, pid):
        self.__pid = pid
        if pid is None:
            return
        with open("%s.pid" % self.server_id, 'w+') as fo:
            fo.write(str(self.__pid))

    @asyncio.coroutine
    def _perform_cleanup(self):
        yield from super()._perform_cleanup()
        self.__kill_game_process()
        if self.restart:
            self.start_server()

    def kill(self, restart=False):
        self.restart = restart
        self.stop_listening()

    def __kill_game_process(self):
        if self.is_listening:
            self.stop_listening()
        if self.pid:
            try:
                self.rcon("quit")
                sleep(2)
            except timeout or ConnectionError:
                pass
            finally:
                self.__kill_own_process()
        else:
            self.__kill_external_game_process()
        print('[INFO] Killed server %s' % self.server_id)
        self.pid = None

    def __kill_external_game_process(self):
        file = "%s.pid" % self.server_id
        if file not in os.listdir('.'):
            return False
        with open(file, "r") as fo:
            pid = int(fo.read())
        return self.__kill_pid(pid)

    def __kill_own_process(self) -> bool:
        return self.__kill_pid(self.pid)

    @staticmethod
    def __kill_pid(pid):
        try:
            os.killpg(pid, signal.SIGTERM)
            print("Kill", pid)
            return True
        except ProcessLookupError:
            print("Fail", pid)
            return False


if __name__ == '__main__':
    os.chdir(PAINTBALL_DIR)
    s = ManagedServer()
    try:
        s.start_server()
        print("Enter ^C to kill all servers")
        wait = False
        while True:
            sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
        s.kill()
    except Exception as e:
        print("Shutting down, exception occurred...")
        s.kill()
        while s.is_listening:
            pass
        raise e