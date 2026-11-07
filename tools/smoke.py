"""Native headless smoke: real Pyxel buffers and scene/UI transitions, no OS GUI claim."""
import json
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'examples'))
import pyxel
from loom import InputFrame, SceneStack
from loom.display import PyxelDisplay, DisplayConfig
from showcase import Menu, Arcade, Turns, CubeRoom

output_dir = Path(sys.argv[1]).resolve() if len(sys.argv)>1 else None
pyxel.init(960,540,headless=True,capture_sec=0)
display=PyxelDisplay(pyxel)
stack=SceneStack(Menu())
results={}
for index, kind in enumerate((Arcade,Turns,CubeRoom)):
    # Navigate retained UI, not an out-of-band scene push.
    for _ in range(1):
        stack.update(InputFrame(pressed=frozenset({'next'})),0)
    stack.update(InputFrame(pressed=frozenset({'confirm'})),0)
    assert isinstance(stack.current,kind)
    if kind is Arcade:
        stack.update(InputFrame(pressed=frozenset({'confirm'})),0)
        assert type(stack.current).__name__=='Pause'
        stack.update(InputFrame(pressed=frozenset({'cancel'})),0)
        assert isinstance(stack.current,Arcade)
    if kind is Turns:
        from loom.storage import SaveStore
        # Never touch a real user's profile during CI or capture.
        temp = tempfile.TemporaryDirectory()
        stack.current.store=SaveStore(temp.name)
        stack.current.advance(); stack.current.save(); stack.current.turn=0
        stack.current.load(); assert stack.current.turn==1
        temp.cleanup()
    durations=[]
    for i in range(120):
        start=time.perf_counter_ns()
        stack.update(InputFrame(held=frozenset({'right'}) if i<30 else frozenset()),1/60)
        stack.draw(display)
        durations.append((time.perf_counter_ns()-start)/1e6)
    if kind is CubeRoom:
        assert any(display.world.pget(x,y)==12 for y in range(180) for x in range(320)), 'Cube is not visible'
    durations.sort()
    results[kind.__name__]={'p50_ms':durations[60],'p95_ms':durations[114]}
    if output_dir is not None:
        path=output_dir; path.mkdir(parents=True,exist_ok=True)
        # Snapshot screen through a separate Image; output files aren't committed.
        screen=pyxel.Image(960,540)
        for y in range(540):
            for x in range(960): screen.pset(x,y,pyxel.pget(x,y))
        screen.save(str(path/f'{kind.__name__}.png'),1)
    stack.pop();stack.update(InputFrame(),0)
stack.close()
try:
    import resource
    results['peak_rss_native_units'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    results['rss_unit'] = 'bytes' if sys.platform=='darwin' else 'KiB'
except ImportError:
    pass
print(json.dumps(results,indent=2))
