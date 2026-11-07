import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from loom import Scene, InputFrame
from loom.runtime import GameApp
from loom.display import DisplayConfig, PyxelDisplay
from loom.input import ActionMap
from loom.app import SceneStack

class Probe(Scene):
    def update(self, frame, dt): self.last=frame
    def exit(self): self.closed=True

class RuntimeTests(unittest.TestCase):
    def make_app(self):
        scene=Probe(); app=GameApp('test',scene)
        engine=SimpleNamespace(mouse_x=3,mouse_y=1,btn=lambda key:False,
                               Image=lambda w,h:(w,h), resize=lambda *args:None,
                               quit=lambda:None)
        app.display=PyxelDisplay(engine,DisplayConfig((20,20),(4,2)))
        app.actions=ActionMap({}); app.scenes=SceneStack(scene,app.request_quit)
        return app,scene,engine
    def test_world_pointer_and_letterbox(self):
        app,scene,engine=self.make_app()
        with patch.dict(sys.modules,{'pyxel':engine}):
            app._update();self.assertIsNone(scene.last.world_pointer)
            engine.mouse_y=10;app._update()
            self.assertEqual(scene.last.world_pointer,(.6,1.0))
    def test_quit_closes_scene_before_native_exit(self):
        app,scene,engine=self.make_app()
        engine.quit=lambda:self.assertTrue(scene.closed)
        app.request_quit()
        with patch.dict(sys.modules,{'pyxel':engine}): app._update()
    def test_without_preserves_coordinates(self):
        frame=InputFrame(pressed=frozenset({'shoot'}),world_pointer=(1,2))
        self.assertEqual(frame.without({'shoot'}).world_pointer,(1,2))
        self.assertFalse(frame.without({'shoot'}).pressed)
