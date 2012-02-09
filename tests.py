from unittest import TestCase
from mock import Mock
from time import sleep
from rediset import (
    Rediset,
    RedisWrapper,
    SetNode,
    IntersectionNode,
    SortedIntersectionNode,
    SortedUnionNode,
)


class KeyGenerationTestCase(TestCase):

    def test_key_generation(self):
        rc = RedisWrapper(key_prefix='some-prefix')
        key = rc.create_key('foo')
        self.assertEqual(key, 'some-prefix:foo')


class RedisTestCase(TestCase):

    PREFIX = 'rediset-tests'

    def setUp(self):
        self.rediset = Rediset(key_prefix=self.PREFIX)
        self.rediset.redis = Mock(wraps=self.rediset.redis)

    def tearDown(self):
        redis = self.rediset.redis.redis
        keys = redis.keys('%s*' % self.PREFIX)
        if keys:
            redis.delete(*keys)


class SetTestCase(RedisTestCase):

    def test_basic_set(self):
        s = self.rediset.Set('key')

        s.add('a')
        s.add('b')
        s.add('c')

        self.assertEqual(len(s), 3)
        self.assertEqual(s.members(), set(['a', 'b', 'c']))
        self.assertTrue(s.contains('a'))
        self.assertFalse(s.contains('d'))

        s.remove('a')
        self.assertFalse(s.contains('a'))
        s.remove('b', 'c')
        self.assertEqual(len(s), 0)


class SortedSetTestCase(RedisTestCase):

    def test_basic_sorted_set(self):
        s = self.rediset.SortedSet('key')

        s.add(('a', 1))
        s.add(('b', 2), ('c', 3))

        self.assertEqual(len(s), 3)
        self.assertEqual(s.members(), ['a', 'b', 'c'])
        self.assertEqual(set(s), set(['a', 'b', 'c']))
        self.assertTrue('a' in s)
        self.assertFalse('d' in s)

        s.remove('a')
        self.assertFalse(s.contains('a'))
        s.remove('b', 'c')
        self.assertEqual(len(s), 0)

    def test_get_members(self):
        s = self.rediset.SortedSet('key')
        s.add(('a', 1), ('b', 2), ('c', 3))
        self.assertEqual(s.members(), ['a', 'b', 'c'])
        self.assertEqual(s.members(withscores=True), [('a', 1), ('b', 2), ('c', 3)])

    def test_get_item(self):
        s = self.rediset.SortedSet('key')
        s.add(('a', 1), ('b', 2), ('c', 3))

        self.assertEqual(s.get(0), 'a')
        self.assertEqual(s.get(2), 'c')
        self.assertTrue(s.get(3) is None)
        self.assertEqual(s.get(0, withscores=True), ('a', 1.0))

        self.assertEqual(s[0], 'a')
        self.assertEqual(s[2], 'c')
        with self.assertRaises(IndexError):
            s[3]

    def test_get_range(self):
        s = self.rediset.SortedSet('key')
        s.add(('a', 1), ('b', 2), ('c', 3))

        self.assertEqual(s.range(0, 1), ['a', 'b'])
        self.assertEqual(s.range(1, 2), ['b', 'c'])
        self.assertEqual(s.range(2, 10), ['c'])

        self.assertEqual(s.range(0, 2, withscores=True), [('a', 1), ('b', 2), ('c', 3)])

        self.assertEqual(s[0:1], ['a', 'b'])

        self.assertEqual(s[1:], ['b', 'c'])
        self.assertEqual(s[:1], ['a', 'b'])
        self.assertEqual(s[0:10], ['a', 'b', 'c'])

    def test_iteration(self):
        s = self.rediset.SortedSet('key')
        s.add(('a', 1), ('b', 2), ('c', 3))

        results = [item for item in s]
        self.assertEqual(results, ['a', 'b', 'c'])

        self.assertEqual(self.rediset.redis.zrange.call_count, 1)


class SortedSetOperationTestCase(RedisTestCase):

    def test_sorted_set_intersection(self):
        s1 = self.rediset.SortedSet('key1')
        s2 = self.rediset.SortedSet('key2')

        i = self.rediset.Intersection(s1, s2)
        self.assertTrue(isinstance(i, SortedIntersectionNode))

    def test_sorted_set_union(self):
        s1 = self.rediset.SortedSet('key1')
        s2 = self.rediset.SortedSet('key2')

        u = self.rediset.Union(s1, s2)
        self.assertTrue(isinstance(u, SortedUnionNode))

    def test_sorted_set_difference(self):
        s1 = self.rediset.SortedSet('key1')
        s2 = self.rediset.SortedSet('key2')

        with self.assertRaises(TypeError):
            d = self.rediset.Difference(s1, s2)



class IntersectionTestCase(RedisTestCase):

    def test_basic_intersection(self):
        s1 = self.rediset.Set('key1')
        s2 = self.rediset.Set('key2')

        s1.add('a', 'b')
        s2.add('b', 'c')

        i = self.rediset.Intersection(s1, s2)
        self.assertEqual(len(i), 1)
        self.assertEqual(i.members(), set(['b']))

        i2 = s1.intersection(s2)
        self.assertEqual(i.members(), i2.members())

    def test_intersection_tree(self):
        s1 = self.rediset.Set('key1')
        s2 = self.rediset.Set('key2')
        s3 = self.rediset.Set('key3')

        s1.add('a', 'b', 'c')
        s2.add('b', 'c', 'd')
        s3.add('b', 'z', 'x')

        i1 = self.rediset.Intersection(s1, s2)
        self.assertEqual(len(i1), 2)

        i2 = self.rediset.Intersection(i1, s3)
        self.assertEqual(len(i2), 1)
        self.assertEqual(i2.members(), set(['b']))

    def test_key_generation(self):
        i1 = self.rediset.Intersection('a', 'b', 'c')
        i2 = self.rediset.Intersection('c', 'b', 'a')
        i3 = self.rediset.Intersection('b' ,'c', 'a')
        self.assertTrue(i1.key == i2.key == i3.key)

    def test_sorted_set_intersection(self):
        s1 = self.rediset.SortedSet('key1')
        s2 = self.rediset.SortedSet('key2')

        s1.add(('a', 2), ('b', 2))
        s2.add(('b', 1), ('c', 2))

        i = self.rediset.Intersection(s1, s2)
        self.assertEqual(len(i), 1)
        self.assertEqual(i.members(), ['b'])

        i2 = s1.intersection(s2)
        self.assertEqual(i.members(), i2.members())

class UnionTestCase(RedisTestCase):

    def test_basic_union(self):
        s1 = self.rediset.Set('key1')
        s2 = self.rediset.Set('key2')

        s1.add('a', 'b')
        s2.add('b', 'c')

        u = self.rediset.Union(s1, s2)
        self.assertEqual(len(u), 3)
        self.assertEqual(u.members(), set(['a', 'b', 'c']))

        u2 = s1.union(s2)
        self.assertEqual(u.members(), u2.members())

    def test_union_tree(self):
        s1 = self.rediset.Set('key1')
        s2 = self.rediset.Set('key2')
        s3 = self.rediset.Set('key3')

        s1.add('a', 'b', 'c')
        s2.add('b', 'c', 'd')
        s3.add('b', 'z', 'x')

        i1 = self.rediset.Union(s1, s2)
        self.assertEqual(len(i1), 4)

        i2 = self.rediset.Union(i1, s3)
        self.assertEqual(len(i2), 6)
        self.assertEqual(i2.members(), set(['a', 'b', 'c', 'd', 'z', 'x']))

    def test_key_generation(self):
        i1 = self.rediset.Union('a', 'b', 'c')
        i2 = self.rediset.Union('c', 'b', 'a')
        i3 = self.rediset.Union('b' ,'c', 'a')
        self.assertTrue(i1.key == i2.key == i3.key)

    def test_sorted_set_union(self):
        s1 = self.rediset.SortedSet('key1')
        s2 = self.rediset.SortedSet('key2')

        s1.add(('a', 1), ('b', 2))
        s2.add(('b', 2), ('c', 4))

        u = self.rediset.Union(s1, s2)
        self.assertEqual(len(u), 3)
        self.assertEqual(u.members(), ['a', 'b', 'c'])

        u2 = s1.union(s2)
        self.assertEqual(u.members(), u2.members())


class DifferenceTestCase(RedisTestCase):

    def test_basic_difference(self):
        s1 = self.rediset.Set('key1')
        s2 = self.rediset.Set('key2')
        s3 = self.rediset.Set('key3')

        s1.add('a', 'b', 'c', 'x')
        s2.add('b')
        s3.add('c', 'd')

        d = self.rediset.Difference(s1, s2, s3)
        self.assertEqual(len(d), 2)
        self.assertEqual(d.members(), set(['a', 'x']))

        d2 = s1.difference(s2, s3)
        self.assertEqual(d.members(), d2.members())

    def test_difference_tree(self):
        s1 = self.rediset.Set('key1')
        s2 = self.rediset.Set('key2')
        s3 = self.rediset.Set('key3')

        s1.add('a', 'b', 'c')
        s2.add('b', 'd', 'e')
        s3.add('c', 'z', 'x')

        d1 = self.rediset.Difference(s1, s2)
        self.assertEqual(len(d1), 2)
        self.assertEqual(d1.members(), set(['a', 'c']))

        d2 = self.rediset.Difference(d1, s3)
        self.assertEqual(len(d2), 1)
        self.assertEqual(d2.members(), set(['a']))

    def test_key_generation(self):
        d1 = self.rediset.Difference('a', 'b', 'c')
        d2 = self.rediset.Difference('a', 'c', 'b')
        d3 = self.rediset.Difference('b' ,'c', 'a')
        self.assertEqual(d1.key, d2.key)
        self.assertNotEqual(d1.key, d3.key)


class ShortcutTestCase(RedisTestCase):

    def test_string_shortcuts(self):
        s1 = self.rediset.Set('key1')
        s2 = self.rediset.Set('key2')

        s1.add('a', 'b')
        s2.add('b', 'c')

        intersection = self.rediset.Intersection('key1', s2)

        for child in intersection.children:
            self.assertTrue(isinstance(child, SetNode))

        self.assertEqual(len(intersection), 1)

    def test_single_item(self):
        s1 = self.rediset.Set('key1')
        s1.add('a', 'b')
        intersection = self.rediset.Intersection(s1)
        self.assertTrue(isinstance(intersection, SetNode))

        intersection = self.rediset.Intersection('key1')
        self.assertTrue(isinstance(intersection, SetNode))

        s2 = self.rediset.Set('key2')
        s2.add('b', 'c')
        intersection = self.rediset.Intersection(s1, s2)
        union = self.rediset.Union(intersection)
        self.assertTrue(isinstance(union, IntersectionNode))


class CombinationTestCase(RedisTestCase):

    def test_complex_tree(self):
        s1 = self.rediset.Set('key1')
        s2 = self.rediset.Set('key2')
        s3 = self.rediset.Set('key3')
        s4 = self.rediset.Set('key4')
        s5 = self.rediset.Set('key5')

        s1.add('a', 'b')
        s2.add('b', 'c')
        s3.add('b', 'd')
        s4.add('e', 'f')
        s5.add('b', 'z')

        result = self.rediset.Union(
            self.rediset.Intersection(
                s1,
                s2,
                s3
            ),
            s4,
            s5
        )

        self.assertEqual(len(result), 4)
        self.assertEqual(result.members(), set(['b', 'e', 'f', 'z']))


class ConversionTestCase(RedisTestCase):

    def test_iterable(self):
        s1 = self.rediset.Set('key1')
        s1.add('a', 'b', 'c')
        self.assertEqual(set(s1), set(['a', 'b', 'c']))

    def test_contains(self):
        s1 = self.rediset.Set('key1')
        s1.add('a', 'b', 'c')
        self.assertTrue('a' in s1)
        self.rediset.redis.sismember.assert_called_with('key1', 'a')
        self.assertFalse('x' in s1)
        self.rediset.redis.sismember.assert_called_with('key1', 'x')


class CachingTestCase(RedisTestCase):

    def test_default_caching_and_override(self):
        self.rediset = Rediset(key_prefix=self.PREFIX, default_cache_seconds=10)
        s1 = self.rediset.Set('key1')
        s2 = self.rediset.Set('key2')

        intersection = self.rediset.Intersection(s1, s2)
        self.assertEqual(intersection.cache_seconds, 10)

        intersection = self.rediset.Intersection(s1, s2, cache_seconds=5)
        self.assertEqual(intersection.cache_seconds, 5)

    def test_caching(self):
        s1 = self.rediset.Set('key1')
        s2 = self.rediset.Set('key2')

        s1.add('a', 'b')
        s2.add('b', 'c')

        intersection = self.rediset.Intersection(s1, s2, cache_seconds=1)

        len(intersection)
        len(intersection)

        self.assertEqual(intersection.rediset.redis.sinterstore.call_count, 1)

        sleep(2)

        len(intersection)

        self.assertEqual(intersection.rediset.redis.sinterstore.call_count, 2)

    def test_caching_empty_sets(self):
        s1 = self.rediset.Set('key1')
        s2 = self.rediset.Set('key2')

        s1.add('a', 'b')
        s2.add('c', 'd')

        intersection = self.rediset.Intersection(s1, s2, cache_seconds=1)

        len(intersection)
        len(intersection)

        self.assertEqual(intersection.rediset.redis.sinterstore.call_count, 1)
