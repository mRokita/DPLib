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

from dplib.server import Server

s = Server(hostname='127.0.0.1', port=27910, logfile=r'C:\Games\Paintball2\pball\qconsole27910.log', rcon_password='hello')

elim_active = False

@s.event
def on_chat(nick, message):
    global elim_active
    if message == '!map elim' and not elim_active:
        elim_active = True
        maps = ['beta/wobluda_fix', 'beta/daylight_b1', 'airtime']
        s.say('{C}AType \'!elim <mapname>\' to eliminate a map.')
        while len(maps) > 1:
            s.say('{C}9Available maps: ' + ', '.join(maps))
            msg = yield from s.wait_for_message(check=lambda n, m: m.startswith('!elim '))
            mapname = msg['message'].split('!elim ')[1]
            if mapname not in maps:
                s.say('{C}9Invalid map.')
                s.say('{C}9Available maps: ' + ', '.join(maps))
            else:
                maps.remove(mapname)
        s.rcon('sv newmap '+maps[0])
        elim_active = False

s.run()