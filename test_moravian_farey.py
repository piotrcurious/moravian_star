import unittest
from fractions import Fraction
import math

from moravian_farey import (
    Vector,
    canonical_key,
    vector_from_key,
    angle_between,
    primitive_int_vector,
    farey_sequence,
    canonical_rays,
    farey_rays,
    farey_mediant_rays,
    compare_ray_sets,
    nearest_canonical_angles,
)


class TestMoravianFarey(unittest.TestCase):

    def test_vector_fallback(self):
        v1 = Vector((1, 2, 3))
        v2 = Vector((0, 1, 0))
        self.assertEqual(v1.x, 1.0)
        self.assertEqual(v1.y, 2.0)
        self.assertEqual(v1.z, 3.0)
        self.assertEqual(len(v1), 3)

        self.assertAlmostEqual(v1.dot(v2), 2.0)
        cross = v1.cross(v2)
        self.assertAlmostEqual(cross.x, -3.0)
        self.assertAlmostEqual(cross.y, 0.0)
        self.assertAlmostEqual(cross.z, 1.0)

        v_norm = v1.normalized()
        self.assertAlmostEqual(v_norm.length(), 1.0)

        v_add = v1 + v2
        self.assertEqual(v_add.values, [1.0, 3.0, 3.0])

        v_sub = v1 - v2
        self.assertEqual(v_sub.values, [1.0, 1.0, 3.0])

        v_mul = v1 * 2
        self.assertEqual(v_mul.values, [2.0, 4.0, 6.0])

    def test_canonical_key(self):
        k1 = canonical_key((1, 0, 0))
        self.assertEqual(k1, (Fraction(1, 1), Fraction(0, 1), Fraction(0, 1)))

        k2 = canonical_key((2, 2, 0))
        self.assertEqual(k2, (Fraction(1, 1), Fraction(1, 1), Fraction(0, 1)))

        k3 = canonical_key((0.5, -0.5, 1.0))
        self.assertEqual(k3, (Fraction(1, 2), Fraction(-1, 2), Fraction(1, 1)))

        with self.assertRaises(ValueError):
            canonical_key((0, 0, 0))

    def test_farey_sequence(self):
        f1 = farey_sequence(1)
        self.assertEqual(f1, [Fraction(0, 1), Fraction(1, 1)])

        f2 = farey_sequence(2)
        self.assertEqual(f2, [Fraction(0, 1), Fraction(1, 2), Fraction(1, 1)])

        f3 = farey_sequence(3)
        self.assertEqual(
            f3,
            [
                Fraction(0, 1),
                Fraction(1, 3),
                Fraction(1, 2),
                Fraction(2, 3),
                Fraction(1, 1),
            ],
        )

        with self.assertRaises(ValueError):
            farey_sequence(0)

    def test_canonical_rays(self):
        rays = canonical_rays()
        self.assertEqual(len(rays), 26)

    def test_farey_rays(self):
        f1_rays = farey_rays(1)
        self.assertEqual(len(f1_rays), 26)
        self.assertEqual(f1_rays, canonical_rays())

        f2_rays = farey_rays(2)
        self.assertEqual(len(f2_rays), 98)

    def test_farey_mediant_rays(self):
        depth0 = farey_mediant_rays(0)
        self.assertEqual(len(depth0), 26)
        self.assertEqual(depth0, canonical_rays())

        depth1 = farey_mediant_rays(1)
        self.assertEqual(len(depth1), 98)

    def test_compare_ray_sets(self):
        canon = canonical_rays()
        f1 = farey_rays(1)
        comp = compare_ray_sets(canon, f1)
        self.assertTrue(comp["exact_match"])
        self.assertEqual(comp["canonical_count"], 26)
        self.assertEqual(comp["test_count"], 26)

        f2 = farey_rays(2)
        comp2 = compare_ray_sets(canon, f2)
        self.assertFalse(comp2["exact_match"])
        self.assertEqual(len(comp2["only_test"]), 72)

    def test_nearest_canonical_angles(self):
        canon = canonical_rays()
        angles = nearest_canonical_angles(canon, canon)
        for a in angles:
            self.assertAlmostEqual(a, 0.0)

    def test_primitive_int_vector(self):
        key = (Fraction(1, 2), Fraction(-1, 2), Fraction(1, 1))
        p = primitive_int_vector(key)
        self.assertEqual(p, (1, -1, 2))


if __name__ == "__main__":
    unittest.main()
