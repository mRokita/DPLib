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

from time import time

from dplib.server import Server

s = Server(hostname='127.0.0.1', port=27910, logfile=r'C:\Games\Paintball2\pball\qconsole27910.log', rcon_password='hello')

spawnkills = dict()
spawnkill_last_times = dict()

@s.event
def on_respawn(team, nick):
    kill = yield from s.wait_for_elim(victim_nick=nick, timeout=2)
    if not kill:
        return
    if not kill['killer_nick'] in spawnkills or time()-spawnkill_last_times[kill['killer_nick']] > 10:
        spawnkills[kill['killer_nick']] = 0
    spawnkills[kill['killer_nick']] += 1
    spawnkill_last_times[kill['killer_nick']] = time()
    s.say('{C}9%s, {C}A{U}STOP SPAWNKILLING{U}' % kill['killer_nick'])
    if spawnkills[kill['killer_nick']] > 3:
        s.kick(nick=kill['killer_nick'])
s.run()