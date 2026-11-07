import unittest
from loom import Scene, SceneStack, InputFrame, ActionMap

class Probe(Scene):
    def __init__(self): self.events=[]; self.frames=[]
    def enter(self, stack): super().enter(stack); self.events.append('enter')
    def exit(self): self.events.append('exit')
    def pause(self): self.events.append('pause')
    def resume(self): self.events.append('resume')
    def update(self, frame, dt): self.frames.append(frame)
    def draw(self, target): target.append(self)

class SceneTests(unittest.TestCase):
    def test_modal_blocks_input_and_update(self):
        root=Probe(); stack=SceneStack(root); modal=Probe()
        stack.push(modal); stack.update(InputFrame(), .1)
        stack.update(InputFrame(pressed=frozenset({'confirm'})), .1)
        self.assertEqual(len(root.frames),1)
        self.assertIn('confirm',modal.frames[0].pressed)
        stack.pop(); stack.update(InputFrame(),.1)
        self.assertEqual(root.events,['enter','pause','resume'])
        self.assertEqual(modal.events,['enter','exit'])
    def test_lower_scene_updates_without_input(self):
        root=Probe(); modal=Probe(); modal.blocks_update_below=False; modal.opaque=False
        stack=SceneStack(root); stack.push(modal); stack.update(InputFrame(),0)
        stack.update(InputFrame(pressed=frozenset({'confirm'})),.1)
        self.assertFalse(root.frames[-1].pressed)
        drawn=[]; stack.draw(drawn); self.assertEqual(drawn,[root,modal])
    def test_conflicting_requests_and_root_pop(self):
        stack=SceneStack(Probe())
        with self.assertRaises(RuntimeError): stack.pop()
        stack.push(Probe())
        with self.assertRaises(RuntimeError): stack.replace(Probe())
    def test_replace_and_cleanup(self):
        a=Probe(); b=Probe(); stack=SceneStack(a)
        stack.replace(b); stack.update(InputFrame(),0); stack.close()
        self.assertEqual(a.events,['enter','exit']); self.assertEqual(b.events,['enter','exit'])
    def test_actions_edges_and_shared_key(self):
        actions=ActionMap({'confirm':(1,2),'other':(1,)})
        calls=[]
        f=actions.sample(lambda k: calls.append(k) or k==1)
        self.assertEqual(calls,[1,2]); self.assertEqual(f.pressed,{'confirm','other'})
        self.assertFalse(actions.sample(lambda k:k==1).pressed)
        self.assertEqual(actions.sample(lambda k:False).released,{'confirm','other'})

    def test_reset_suppresses_held_press(self):
        actions=ActionMap({'confirm':(1,)})
        actions.sample(lambda key:True); actions.reset()
        self.assertFalse(actions.sample(lambda key:True).pressed)
        actions.sample(lambda key:False)
        self.assertEqual(actions.sample(lambda key:True).pressed,{'confirm'})
