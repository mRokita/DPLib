#!/usr/bin/python3
import asyncio
import shlex
import signal
import subprocess
import os
import sys
from multiprocessing import Process
from shlex import quote
from threading import Thread
from time import time, sleep
import pty

from _socket import timeout

from dplib.server import Server, ServerEvent

# -------------- BEGIN CONFIG SECTION ----------------

LAUNCH_TIMEOUT = 10
PAINTBALL_DIR = '/home/paintball/paintball2/'

SERVERS = {
    'speed': {
        'enabled': True,
        'startup_cvars': {
            'hostname': 'FALUBAZ/devol',
            'public': 1,
            'port': 27911,
            'flagcapendsround': 0,
            'elim': 10,
            'rcon_password': '21fasjkl',
        },
        'startup_commands': [
            ['setmaster', 'dplogin.com'],
            ['map', 'dodgeball'],
        ],
        'event_rcons': {
            ServerEvent.CHAT: 'say on_chat',
            ServerEvent.ELIM: 'say on_elim',
            ServerEvent.RESPAWN: 'say on_respawn',
            ServerEvent.ENTRANCE: 'say Hello, {nick}',
            ServerEvent.FLAG_CAPTURED: 'say on_flag_captured',
            ServerEvent.ELIM_TEAMS_FLAG: 'say on_elim_teams_flag',
            ServerEvent.ROUND_STARTED: 'say on_round_started',
            ServerEvent.TEAM_SWITCHED: 'say on_team_switched',
            ServerEvent.GAME_END: 'say on_game_end',
            ServerEvent.MAPCHANGE: 'say on_mapchange',
            ServerEvent.NAMECHANGE: 'say on_namechange',
        },
        'event_lambdas': {
            ServerEvent.CHAT: lambda **kwargs: print(kwargs),
        }
    }
}

# -------------- END CONFIG SECTION ----------------

managed_servers = dict()


class ManagedServer(Server):

    def __init__(self, server_id: str, config: dict):
        self.config = config
        self.server_id = server_id
        self.pty_master = None
        self.pty_slave = None

    @property
    def running(self) -> bool:
        return self.pid is not None

    def start_event_service(self):
        t = Thread(target=self.run, kwargs={'debug': True, 'make_secure': False})
        t.start()

    def get_event_handler(self, event_type):
        if event_type in self.handlers:
            @asyncio.coroutine
            def handle(**kwargs):
                if event_type in self.config['event_rcons']:
                    self.rcon(self.config['event_rcons'][event_type].format(
                        **kwargs))
                if event_type in self.config['event_lambdas']:
                    self.config['event_lambdas'][event_type](**kwargs)

            return handle
        else:
            return super().get_event_handler(event_type)

    def start_process(self):
        self.kill_running_process()
        if not self.config['enabled']:
            print('[WARNING] Skipping server %s - "enabled" is False' %
                  self.server_id)
            return
        master, slave = os.openpty()

        process = subprocess.Popen(shlex.split(self.get_run_command()),
                                   stdout=slave,
                                   stdin=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL,
                                   preexec_fn=os.setsid,
                                   shell=False)

        self.pid = process.pid
        start_time = time()
        super(ManagedServer, self).__init__(
            hostname='localhost',
            port=self.config['startup_cvars']['port'],
            rcon_password=self.config['startup_cvars']['rcon_password'],
            pty_master=master
        )
        managed_servers[self.server_id] = self
        port = None
        self.make_secure()
        self.start_event_service()
        while not port and time() - start_time < LAUNCH_TIMEOUT:
            try:
                port = self.get_cvar('port')
            except Exception as e:
                pass
        if not port:
            print("[ERROR] Couldn't start server %s" % self.server_id)
            self.kill()
        else:
            print("[SUCCESS] Server %s is running on 127.0.0.1:%s. PID: %d" %
                  (self.server_id, port, self.pid))

    def get_run_command(self) -> str:
        command = './paintball2 +set dedicated 1'
        for v in self.config['startup_cvars']:
            command += ' +set %s "%s"' % (quote(v), quote(str(self.config['startup_cvars'][v])))
        for c in self.config['startup_commands']:
            command += ' +' + ' '.join(quote(i) for i in c)
        print(command)
        return command

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

    def kill(self):
        self.stop_listening()
        if self.pid:
            try:
                self.rcon("quit")
                self.kill_own_process()
            except timeout or ConnectionError:
                if self.pid:
                    self.kill_own_process()
        else:
            self.kill_running_process()
        print('[INFO] Killed server %s' % self.server_id)
        self.pid = None
        if self.server_id in managed_servers:
            del managed_servers[self.server_id]

    def kill_running_process(self):
        file = "%s.pid" % self.server_id
        if file not in os.listdir('.'):
            return False
        with open(file, "r") as fo:
            pid = int(fo.read())
        return self.kill_pid(pid)

    def kill_own_process(self) -> bool:
        return self.kill_pid(self.pid)

    @staticmethod
    def kill_pid(pid):
        try:
            os.killpg(pid, signal.SIGTERM)
            print("Kill", pid)
            return True
        except ProcessLookupError:
            print("Fail", pid)
            return False


def run_servers():
    for s in SERVERS:
        managed_server = ManagedServer(server_id=s, config=SERVERS[s])
        managed_server.start_process()


def kill_all():
    for s in list(managed_servers.values()):
        s.kill()

try:
    if __name__ == '__main__':
        os.chdir(PAINTBALL_DIR)
        run_servers()
        sleep(1)
        print("Enter 'quit' to kill all servers")
        wait = False
        for s in list(managed_servers.values()):
            if s.is_listening:
                wait = True
                break
        if wait:
            try:
                while not input() == 'quit':
                    pass
                kill_all()
            except EOFError:
                pass
except KeyboardInterrupt:
    kill_all()
except Exception as e:
    kill_all()
finally:
    kill_all()
