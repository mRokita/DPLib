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