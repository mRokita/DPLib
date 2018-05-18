#!/usr/bin/python3
import asyncio
import subprocess
import os
import sys
from multiprocessing import Process
from threading import Thread
from time import time, sleep
import pty
from dplib.server import Server, ServerEvent

# -------------- BEGIN CONFIG SECTION ----------------

LAUNCH_TIMEOUT = 5
PAINTBALL_DIR = '/home/mrokita/Games/paintball2'

SERVERS = {
    'speed': {
        'enabled': True,
        'event_service_enabled': True,
        'init_map': 'midnight',
        'rcon_password': '21fasjkl',
        'port': 27911,
        'config_vars': {
            'hostname': 'FALUBAZ/devol',
            'public': 1,
            'flagcapendsround': 0,
            'elim': 10,
        },
        'startup_commands': [

        ],
        'maplist': [
            'midnight',
            'dodgeball',
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
        self.pid = None
        self.pty_master = None

    @property
    def running(self) -> bool:
        return self.pid is not None

    def start_event_service(self):
        t = Thread(target=self.run)
        t.start()

    def get_event_handler(self, event_type):
        if event_type in self.handlers:
            @asyncio.coroutine
            def handle(**kwargs):
                if event_type in self.config['event_rcons']:
                    self.rcon(self.config['event_rcons'][event_type].format(**kwargs))
                if event_type in self.config['event_lambdas']:
                    self.config['event_lambdas'][event_type](**kwargs)
            return handle
        else:
            return super().get_event_handler(event_type)

    def start_process(self) -> int:
        self.kill()
        if not self.config['enabled']:
            print('[WARNING] Skipping server %s - "enabled" is False' %
                  self.server_id)
            return
        pty_master, pty_slave = pty.openpty()
        self.pty_master = pty_master
        process = subprocess.Popen(self.get_run_command(), stdout=pty_slave,
                                   shell=True)
        start_time = time()
        os.close(pty_slave)
        pid = process.pid
        super(ManagedServer, self).__init__(hostname='localhost',
                         port=self.config['port'],
                         rcon_password=self.config['rcon_password'],
                         pty_master=pty_master)

        managed_servers[self.server_id] = self
        port = None
        while not port and time() - start_time < LAUNCH_TIMEOUT:
            try:
                port = self.get_cvar('port')
            except Exception:
                pass

        if not port:
            print("[ERROR] Couldn't start server %s" % self.server_id)
            self.kill()
        else:
            print("[SUCCESS] Server %s is running on 127.0.0.1:%s. PID: %d" %
                  (self.server_id, port, pid))
            with open("%s.pid" % self.server_id, 'w+') as fo:
                fo.write(str(pid))

    def get_run_command(self) -> str:
        command = './paintball2 +set dedicated 1 +set port %s' \
                  ' +set rcon_password %s' % (self.config['port'],
                                              self.config['rcon_password'])
        for v in self.config['config_vars']:
            command += ' +set %s "%s"' % (v, self.config['config_vars'][v])

        command += ' +map %s' % self.config['init_map']
        return command

    def kill(self):
        if self.pty_master:
            os.close(self.pty_master)
        self.stop_listening()
        if self.pid:
            try:
                self.rcon("quit")
            except Exception:
                if self.pid:
                    try:
                        kill_pid(self.pid)
                    except ProcessLookupError:
                        pass # no server @ pid
        else:
            try:
                kill_pidfile(self.server_id)
            except ProcessLookupError:
                pass # no server @ pid
        print('[INFO] Killed server %s' % self.server_id)
        self.pid = None
        if self.server_id in managed_servers:
            del managed_servers[self.server_id]


def kill_pidfile(server_id):
    file = "%s.pid" % server_id
    if not file in os.listdir('.'):
        return
    with open(file, "r") as fo:
        pid = int(fo.read())
    kill_pid(pid)


def kill_pid(pid):
    os.kill(pid, 15)


def run_servers():
    for s in SERVERS:
        managed_server = ManagedServer(server_id=s, config=SERVERS[s])
        managed_server.start_process()
        managed_server.start_event_service()

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
            except EOFError:
                pass
except KeyboardInterrupt:
    for s in list(managed_servers.values()):
        s.kill()
    sys.exit(0)
except Exception as e:
    for s in list(managed_servers.values()):
        s.kill()
    raise e
