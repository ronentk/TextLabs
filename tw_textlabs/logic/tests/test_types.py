# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.


from nose.tools import assert_raises

from tw_textlabs.logic import Type, TypeHierarchy, Variable


#    a
#   / \
#  /   \
# b     c
#  \   /
#   \ /
#    d

hier = TypeHierarchy()
hier.add(Type("a", []))
hier.add(Type("b", ["a"]))
hier.add(Type("c", ["a"]))
hier.add(Type("d", ["b", "c"]))

a = hier.get("a")
b = hier.get("b")
c = hier.get("c")
d = hier.get("d")


def test_type_hierarchy():
    assert list(a.ancestors) == []
    assert list(a.supertypes) == [a]
    assert list(a.descendants) == [b, c, d]
    assert list(a.subtypes) == [a, b, c, d]

    assert list(b.ancestors) == [a]
    assert list(b.supertypes) == [b, a]
    assert list(b.descendants) == [d]
    assert list(b.subtypes) == [b, d]

    assert list(c.ancestors) == [a]
    assert list(c.supertypes) == [c, a]
    assert list(c.descendants) == [d]
    assert list(c.subtypes) == [c, d]

    assert list(d.ancestors) == [b, c, a]
    assert list(d.supertypes) == [d, b, c, a]
    assert list(d.descendants) == []
    assert list(d.subtypes) == [d]

    va = Variable.parse("a")
    assert va.is_a(a)
    assert not va.is_a(b)
    assert not va.is_a(c)
    assert not va.is_a(d)

    vb = Variable.parse("b")
    assert vb.is_a(a)
    assert vb.is_a(b)
    assert not vb.is_a(c)
    assert not vb.is_a(d)

    vc = Variable.parse("c")
    assert vc.is_a(a)
    assert not vc.is_a(b)
    assert vc.is_a(c)
    assert not vc.is_a(d)

    vd = Variable.parse("d")
    assert vd.is_a(a)
    assert vd.is_a(b)
    assert vd.is_a(c)
    assert vd.is_a(d)


def test_multi_closure():
    pairs = list(hier.multi_ancestors((d, d)))

    expected = {
                (b, d), (c, d), (d, b), (d, c),
        (a, d), (b, b), (b, c), (c, b), (c, c), (d, a),
                (a, b), (a, c), (b, a), (c, a),
                            (a, a),
    }

    assert len(pairs) == len(expected)
    assert set(pairs) == expected

    pairs = list(hier.multi_descendants((a, a)))

    expected = {
                (a, b), (a, c), (b, a), (c, a),
        (a, d), (b, b), (b, c), (c, b), (c, c), (d, a),
                (b, d), (c, d), (d, b), (d, c),
                            (d, d),
    }

    assert len(pairs) == len(expected)
    assert set(pairs) == expected
