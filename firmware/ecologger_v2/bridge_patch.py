"""Patch only RouterBridge's known updater loop; reject unknown library layouts."""

ORIGINAL = '''        if (Bridge) {
            Bridge.update();
        }
        k_yield();'''
PREVIOUS = '''        // Logger patch: serve requests even before $/reset completes.
        Bridge.update();
        k_yield();'''
PATCHED = '''        // Logger patch: serve requests even before $/reset completes.
        Bridge.update();
        // Yield alone cannot schedule the lower-priority SD writer under load.
        k_msleep(1);'''


def patch_update_loop(source):
    # Unconditional update is safe only after both RPC endpoints exist.
    client=source.index('client = new RPCClient(')
    server=source.index('server = new RPCServer(')
    thread=source.index('upd_tid = k_thread_create(')
    if not client < server < thread:
        raise ValueError('Unexpected RouterBridge startup order')
    start=source.index('inline void updateEntryPoint(')
    end=source.index('\n}',start)+2
    body=source[start:end]
    if PATCHED in body:
        return source
    for old in (ORIGINAL,PREVIOUS):
        if body.count(old)==1:
            return source[:start]+body.replace(old,PATCHED)+source[end:]
    raise ValueError('Unexpected RouterBridge updater; check installed library before building')
