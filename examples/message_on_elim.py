from time import time

from dplib.parse import escape_braces
from dplib.server import Server

s = Server(hostname='127.0.0.1', port=27910, logfile=r'C:\Games\Paintball2\pball\qconsole27910.log', rcon_password='hello')

spawnkills = dict()
spawnkill_last_times = dict()

@s.event
def on_elim(killer_nick, killer_weapon, victim_nick, victim_weapon):
    s.say('{C}A%s sucks at DP' % escape_braces(victim_nick))
    s.cprint('{C}A%s NOOB' % escape_braces(victim_nick))

s.run()