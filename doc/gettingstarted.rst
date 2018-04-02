Getting Started
===============

Introduction
------------
DPLib is a Python library that makes you able to write scripts that react on some in-game events

Installation
------------
.. code-block:: sh

    git clone https://github.com/mRokita/DPLib.git
    cd DPLib
    python3 -m pip install DPLib # Only python 3 is supported


First steps
-----------
This code is a basic example of how to use DPLib. It uses all the currently available events.
You should definitely play around with it. Simply edit the third line to match your server's config and run it!

.. literalinclude:: ../examples/first_steps.py
    :linenos:


Available event handlers
************************

* :func:`dplib.server.Server.on_elim`
* :func:`dplib.server.Server.on_entrance`
* :func:`dplib.server.Server.on_respawn`
* :func:`dplib.server.Server.on_elim_teams_flag`
* :func:`dplib.server.Server.on_team_switched`
* :func:`dplib.server.Server.on_round_started`
* :func:`dplib.server.Server.on_flag_captured`
* :func:`dplib.server.Server.on_message`
* :func:`dplib.server.Server.on_game_end`
* :func:`dplib.server.Server.on_mapchange`
* :func:`dplib.server.Server.on_namechange`

Waiting for future events
-------------------------
DPLib uses Python's asyncio module so you can wait for incoming events without blocking the whole script.

Here's a script that uses these 'magic' coroutines.

It's a simple spawnkill protection system, it waits for 2 seconds after respawn for elimination event and when the newly respawned player gets killed within these 2 seconds, the spawnkiller gets a warning. After 4 spawnkills she/he gets kicked from the server.

Check out the 10th line.

.. literalinclude:: ../examples/spawnkill_kick.py
    :linenos:

Available coroutines
********************

* :func:`dplib.server.Server.wait_for_elim`
* :func:`dplib.server.Server.wait_for_entrance`
* :func:`dplib.server.Server.wait_for_respawn`
* :func:`dplib.server.Server.wait_for_elim_teams_flag`
* :func:`dplib.server.Server.wait_for_team_switched`
* :func:`dplib.server.Server.wait_for_round_started`
* :func:`dplib.server.Server.wait_for_flag_captured`
* :func:`dplib.server.Server.wait_for_message`
* :func:`dplib.server.Server.wait_for_game_end`
* :func:`dplib.server.Server.wait_for_mapchange`
* :func:`dplib.server.Server.wait_for_namechange`

Examples
--------

Map elim script
***************

.. literalinclude:: ../examples/map_elim.py
    :linenos:

Spawnkill message
*****************

.. literalinclude:: ../examples/spawnkill_message.py
    :linenos:

Streak
******

.. literalinclude:: ../examples/streak.py
    :linenos:

