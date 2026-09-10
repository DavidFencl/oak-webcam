import unittest

import numpy as np

from presets.pointcloud_renderer import PointCloudRenderer, View


class PointCloudTests(unittest.TestCase):
    def renderer(self, **kwargs):
        return PointCloudRenderer(View(yaw=0, pitch=0, distance=2, target=2), width=101, height=61, **kwargs)

    def test_default_view_keeps_near_center_subject_in_frame(self):
        renderer = PointCloudRenderer()
        for distance in (0.2, 0.3, 0.5, 1.0):
            with self.subTest(distance=distance):
                for x in (-0.1, 0, 0.1):
                    for y in (-0.1, 0, 0.1):
                        image = renderer.render([[x, y, distance]])
                        self.assertEqual(np.count_nonzero(np.any(image != renderer.background, axis=2)), 9)

    def test_front_view_preserves_physical_camera_coordinates(self):
        points = np.array([[0.1, 0.1, 0.2], [-0.1, -0.1, 0.3], [0, 0, 0.5]])
        np.testing.assert_allclose(View(yaw=0, pitch=0, distance=2, target=2).transform(points), points, atol=1e-6)

    def test_nearer_point_occludes_farther_regardless_of_order(self):
        renderer = self.renderer()
        near, far = [0, 0, 1], [0, 0, 4]
        expected = renderer.render([near])
        np.testing.assert_array_equal(renderer.render([near, far]), expected)
        np.testing.assert_array_equal(renderer.render([far, near]), expected)
        self.assertEqual(np.count_nonzero(np.any(expected != renderer.background, axis=2)), 9)

    def test_invalid_and_out_of_view_points_leave_background(self):
        renderer = self.renderer()
        points = [[0, 0, 0], [0, 0, -1], [0, 0, 20], [float("nan"), 0, 1],
                  [float("inf"), 0, 1], [1e20, 1e20, 1]]
        np.testing.assert_array_equal(renderer.render(points), renderer.render([]))

    def test_no_scene_dependent_camera_motion(self):
        renderer = self.renderer()
        point = [0.1, 0, 2]
        alone = renderer.render([point])
        outlier = renderer.render([point, [1000, 1000, 5]])
        np.testing.assert_array_equal(alone, outlier)

    def test_fixed_target_stays_at_center_for_rotated_view(self):
        view = View(yaw=35, pitch=-20, distance=3, target=2)
        np.testing.assert_allclose(view.transform(np.array([[0, 0, 2]])), [[0, 0, 3]], atol=1e-6)
        renderer = PointCloudRenderer(view, width=101, height=61, radius=0)
        image = renderer.render([[0, 0, 2]])
        self.assertFalse(np.array_equal(image[30, 50], renderer.background))

    def test_points_behind_virtual_camera_are_clipped(self):
        renderer = PointCloudRenderer(View(yaw=0, pitch=0, target=3, distance=1), width=101, height=61)
        np.testing.assert_array_equal(renderer.render([[0, 0, 1]]), renderer.render([]))

    def test_organized_sampling_is_spatial_and_bounded(self):
        renderer = self.renderer(max_points=20)
        points = np.arange(300, dtype=np.float32).reshape(100, 3)
        sampled = renderer.sample(points, (10, 10))
        self.assertLessEqual(len(sampled), 20)
        np.testing.assert_array_equal(sampled, points.reshape(10, 10, 3)[::3, ::3].reshape(-1, 3))

    def test_invalid_view_is_rejected(self):
        for kwargs in ({"yaw": float("nan")}, {"distance": 0}, {"fov": 180}, {"pitch": 90}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                View(**kwargs)

    def test_rgb_uses_nearest_surface_and_converts_to_bgr(self):
        renderer = self.renderer()
        points = np.array([[0, 0, 4], [0, 0, 1]], dtype=np.float32)
        colors = np.array([[0, 0, 255, 255], [255, 20, 10, 255]], dtype=np.uint8)
        image = renderer.render(points, colors=colors)
        np.testing.assert_array_equal(image[30, 50], [10, 20, 255])
        np.testing.assert_array_equal(image, renderer.render(points[::-1], colors=colors[::-1]))

    def test_rgb_colors_follow_sampling_and_invalid_point_filter(self):
        renderer = self.renderer(max_points=2, radius=0)
        points = np.array([[float("nan"), 0, 1], [0, 0, 1], [0, 0, 2], [0, 0, 1]], dtype=np.float32)
        colors = np.array([[255, 0, 0], [255, 0, 0], [0, 255, 0], [255, 0, 0]], dtype=np.uint8)
        image = renderer.render(points, colors=colors)
        np.testing.assert_array_equal(image[30, 50], [0, 255, 0])

    def test_rgb_depth_ties_are_deterministic(self):
        renderer = self.renderer()
        points = [[0, 0, 1], [0, 0, 1]]
        colors = np.array([[255, 0, 0], [0, 255, 0]], dtype=np.uint8)
        np.testing.assert_array_equal(renderer.render(points, colors=colors),
                                      renderer.render(points, colors=colors[::-1]))

    def test_mismatched_colors_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "one RGB"):
            self.renderer().render([[0, 0, 1]], colors=np.empty((0, 3), dtype=np.uint8))


if __name__ == "__main__":
    unittest.main()
