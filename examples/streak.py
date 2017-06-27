import asyncio

from dplib.server import Server

s = Server(hostname='127.0.0.1', port=27910, logfile=r'C:\Games\Paintball2\pball\qconsole27910.log', rcon_password='hello')


@asyncio.coroutine
def streak(killer_nick):
    for i in range(1, 3):
        print(killer_nick, i)
        yield from s.wait_for_elim(killer_nick=killer_nick)


ALREADY_WAITING = set()
@s.event
def on_elim(killer_nick, killer_weapon, victim_nick, victim_weapon):
    if killer_nick in ALREADY_WAITING:
        return
    ALREADY_WAITING.add(killer_nick)
    try:
        print('New listener for ' + killer_nick)
        yield from asyncio.wait_for(streak(killer_nick), timeout=20)
        s.say('{U}%s ZABUJCA!{U}' % killer_nick)
    except asyncio.TimeoutError:
        print('Timeout for '+ killer_nick)
    ALREADY_WAITING.remove(killer_nick)