"""Microbenchmark, not a frame-rate or Steam hardware certification."""

import json
import platform
import statistics
import time
import tracemalloc
from loom import InputFrame, Scene, SceneStack
from loom.ui import Column, Button, UIInput


def bench(call, count=10000):
    for _ in range(1000):
        call()
    times = []
    for _ in range(count):
        start = time.perf_counter_ns()
        call()
        times.append(time.perf_counter_ns() - start)
    times.sort()
    return {
        "p50_us": statistics.median(times) / 1000,
        "p95_us": times[int(count * 0.95)] / 1000,
    }


frame = InputFrame()
scene = Scene()
stack = SceneStack(scene)
panel = Column([Button(str(i), lambda: None) for i in range(20)])
ui = UIInput()
long_panel = Column(
    [Button(str(i), lambda: None) for i in range(1000)], viewport_height=240
)
outside = UIInput(500, 500)
results = {
    "python": platform.python_version(),
    "platform": platform.platform(),
    "direct_empty_update": bench(lambda: scene.update(frame, 1 / 60)),
    "stack_empty_update": bench(lambda: stack.update(frame, 1 / 60)),
    "retained_ui_20_buttons": bench(lambda: panel.update(ui)),
    "scroll_ui_1000_buttons_pointer_outside": bench(lambda: long_panel.update(outside)),
}
tracemalloc.start()
for _ in range(10000):
    stack.update(frame, 1 / 60)
    panel.update(ui)
first = tracemalloc.get_traced_memory()[0]
for _ in range(10000):
    stack.update(frame, 1 / 60)
    panel.update(ui)
results["python_heap_delta_second_10000_updates_bytes"] = (
    tracemalloc.get_traced_memory()[0] - first
)
results["layout_passes"] = panel.layout_count
print(json.dumps(results, indent=2))
