import unittest

from loom import Camera2D, CameraView, Viewport


class CameraTests(unittest.TestCase):
    def test_snap_half_away_and_coordinate_inverse(self):
        camera = Camera2D((20, 10))
        for position, origin in (
            (-0.5, -1),
            (0.5, 1),
            (-1.5, -2),
            (1.5, 2),
            (-0.49, 0),
            (0.49, 0),
        ):
            camera.move_to(position, position)
            self.assertEqual(camera.origin, (origin, origin))
            point = camera.view_to_world(3.25, 4.5)
            self.assertEqual(camera.world_to_view(*point), (3.25, 4.5))
            self.assertEqual(camera.visible_rect.x, origin)
        self.assertIsNone(camera.view_to_world(-0.1, 0))
        self.assertIsNone(camera.view_to_world(20, 0))
        self.assertIsNone(camera.view_to_world(0, 10))
        self.assertEqual(camera.world_to_view(-100, 0), (-100, 0))

    def test_bounded_world_look_at_resize_and_small_world_center(self):
        camera = Camera2D((20, 10), world_size=(100, 60))
        camera.move_to(-20, 100)
        self.assertEqual(camera.position, (0, 50))
        camera.look_at(50, 30)
        self.assertEqual(camera.position, (40, 25))
        camera.resize((90, 55))
        self.assertEqual(camera.position, (10, 5))
        camera.resize((103, 63))
        self.assertEqual(camera.position, (-1.5, -1.5))
        self.assertEqual(camera.origin, (-2, -2))
        self.assertEqual(camera.view_to_world(0, 0), (-2, -2))
        camera.move_to(100, 200)
        self.assertEqual(camera.position, (-1.5, -1.5))
        self.assertEqual(camera.visible_rect.width, 103)

    def test_pixel_exact_range_and_atomic_boundary_resize(self):
        camera = Camera2D((8, 3), position=(2**24 - 8, -(2**24)))
        self.assertEqual(camera.view_to_world(7, 0), (2**24 - 1, -(2**24)))
        previous = camera.position, camera.origin, camera.surface_size
        for position in ((2**24 - 7, 0), (-(2**24) - 1, 0), (16777217, 0)):
            with self.assertRaises(ValueError):
                camera.move_to(*position)
            self.assertEqual(
                (camera.position, camera.origin, camera.surface_size), previous
            )
        with self.assertRaises(ValueError):
            camera.resize((9, 3))
        self.assertEqual(
            (camera.position, camera.origin, camera.surface_size), previous
        )

    def test_letterbox_composition_uses_surface_not_output_pixels(self):
        viewport = Viewport.fit((20, 10), (100, 80))
        camera = Camera2D((20, 10), position=(10.5, -3.5))
        self.assertIsNone(viewport.to_local(0, 0))
        world = (17, 0)
        output = viewport.to_output(*camera.world_to_view(*world))
        local = viewport.to_local(*output)
        self.assertEqual(camera.view_to_world(*local), world)

    def test_validation_readonly_snapshot_and_atomic_mutation(self):
        size = [20, 10]
        camera = Camera2D(size, position=(4, 5))
        size[0] = 100
        self.assertEqual(camera.surface_size, (20, 10))
        for bad in ((0, 10), (1.5, 2), (True, 1), (10**1000, 10), (1,)):
            with self.assertRaises(ValueError):
                camera.resize(bad)
            self.assertEqual(camera.surface_size, (20, 10))
            self.assertEqual(camera.position, (4, 5))
        for bad in (float("nan"), float("inf"), True, 10**1000, "1"):
            for method in (
                camera.move_to,
                camera.look_at,
                camera.world_to_view,
                camera.view_to_world,
            ):
                with self.assertRaises(ValueError):
                    method(bad, 0)
            self.assertEqual(camera.position, (4, 5))
        for huge in (1e100, 2**31, -(2**31) - 1):
            with self.assertRaises(ValueError):
                camera.move_to(huge, 0)
            self.assertEqual(camera.position, (4, 5))
            self.assertEqual(camera.origin, (4, 5))
        with self.assertRaises(AttributeError):
            camera.position = (1, 2)


class Target:
    width, height = 20, 10

    def __init__(self):
        self.offset = (0, 0)
        self.calls = []

    def camera(self, *origin):
        self.calls.append(origin)
        self.offset = origin


class CameraViewTests(unittest.TestCase):
    def test_nested_distinct_cameras_restore_previous_and_zero_on_error(self):
        target = Target()
        view = CameraView(target)
        first = Camera2D((20, 10), position=(4.5, -3.5))
        second = Camera2D((20, 10), position=(-2, 3))
        with self.assertRaisesRegex(RuntimeError, "outer"):
            with view.apply(first) as image:
                self.assertIs(image, target)
                self.assertEqual(target.offset, (5, -4))
                with self.assertRaisesRegex(RuntimeError, "inner"):
                    with view.apply(second):
                        self.assertEqual(target.offset, (-2, 3))
                        raise RuntimeError("inner")
                self.assertEqual(target.offset, (5, -4))
                raise RuntimeError("outer")
        self.assertEqual(target.offset, (0, 0))
        self.assertEqual(target.calls, [(5, -4), (-2, 3), (5, -4), (0, 0)])

    def test_wrong_surface_rejected_without_changing_target(self):
        target = Target()
        with self.assertRaises(ValueError):
            with CameraView(target).apply(Camera2D((1, 1))):
                self.fail("must not enter")
        self.assertEqual(target.calls, [])
