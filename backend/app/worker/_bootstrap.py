import asyncio


def ensure_event_loop() -> None:
    # arq's Worker.__init__ calls asyncio.get_event_loop() synchronously,
    # before its own asyncio.run(). aiogram sets uvloop as the event loop
    # policy on import, and uvloop's get_event_loop() raises instead of
    # implicitly creating one (unlike stdlib's deprecated fallback).
    asyncio.set_event_loop(asyncio.new_event_loop())
