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
from asyncio import sleep

from dplib.server import Server

s = Server(hostname='127.0.0.1', port=27911, logfile=r'C:\Games\Paintball2\pball\qconsole27911.log', rcon_password='hello')

map_settings = {
    'airtime': {
        'command': 'set elim 10;set timelimit 10;',
        'message': '{C}9Special settings for airtime {C}Aenabled'
    },
    'shazam33': {
        'command': 'set elim 10;set timelimit 10;',
        'message': '{C}9Special settings for shazam33 {C}Aenabled'
    },
    'default_settings': {
        'command': 'set elim 20;set timelimit 20;',
        'message': '{C}9No special settings for map {I}<mapname>{I}, using defaults'
    }
}

@s.event
def on_mapchange(mapname):
    if mapname not in map_settings:
        settings = map_settings['default_settings']
    else:
        settings = map_settings[mapname]
    command = settings.get('command', None)
    message = settings.get('message', None)
    if message:
        message = mapname.join(message.split('<mapname>'))
    if command:
        for c in command.split(';'):
            s.rcon(c)
    if message:
        yield from sleep(3)
        s.say(message)

s.run()