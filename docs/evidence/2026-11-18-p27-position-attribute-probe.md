# P2.7 — Which `8d 81` streams are the real `_Position` transforms? (probe, 2026-11-18)

**Verdict: PARTIAL — the name table pins; the instance join does not.**

The interned attribute-name reference *is* decodable, and it selects the
`_Position` streams exactly, including rejecting the camera/view matrix that
sits in the same file with the same 12-float encoding. But the object that
carries `_Position` is not joined to the object that carries
`_InstanceName` by any decoded reference: no shared persistent id survives,
only stream adjacency (`ref[0] + 1`, or "next object"). Binding by that is
the ordinal guess the ticket forbids, so **this probe stops here: no
Python/Rust binding change, no identity fallback** (§6).

Probe: [`scripts/triage/p27_position_attr_probe.py`](../../scripts/triage/p27_position_attr_probe.py)
(`--selftest`, `--report`, `--sha16 <hex>`). Corpus read-only; imports the
committed P2 framing/pool layer (`p2_pool_pairing`), re-derives nothing.

```bash
python3 -I scripts/triage/p27_position_attr_probe.py --selftest
python3 -I scripts/triage/p27_position_attr_probe.py --report
python3 -I scripts/triage/p27_position_attr_probe.py --sha16 81b1fe655b83f7ee
```

---

## 1. The name table — decoded (deliverable 1)

### 1.1 Layout

The structure pool is the file's interned name table: a `fe 7c 02` record
whose payload tiles into Law-B items (`src/catpart/product/*`, P2):

```
fe 7c 02 <u32 ln> <tail> <item>*
item  := <u8 L> <L-1 payload bytes>          (Law B; L>=1)
```

An attribute entry in the serialized object stream references an item by
**one id byte**:

```
02 <class-id> 7c 07 <u32 rec_len> <chunk>* fe
chunk := <attr-id: u8> <value> fe
```

**Law P27-1 (name-id base).**

```
attr-id = 0x34 + ordinal0(name)          # 0-based item ordinal
        = 0x35 + ordinal1(name)          # 1-based item ordinal
name    = pool[attr-id - 0x34]           # ids < 0x34 are predefined, not in the pool
```

Both bases are exact; only the 0-based form is used below. The base is
constant across every file checked, and the *pool order is not* — that is
what makes the law a decode rather than an ordinal.

### 1.2 The law on `_Position` and on neighbours

| file | pool items | `_Position` ordinal0 | predicted id | bytes in the object | observed |
|---|---|---|---|---|---|
| `81b1fe655b83f7ee` coso | 79 | 25 | `0x4d` | `4d d4 3e e8 f4 07 37 8d 81 …` | 7/7 matrices |
| servo `STS3215_03a v1` | 65 | 34 | `0x56` | `56 d4 34 e8 f4 07 37 8d 81 …` | 4/4 matrices |
| `9a9d8a85ae5e59b6` head | 202 | 28 | `0x50` | `50 … e8 f4 07 37 8d 81 …` | 19/19 matrices |
| `Product1` SP-02 (283 items) | 283 | 25 | `0x4d` | `4d … 8d 81 …` | 53/53 matrices |
| `Product1` SP-02 (123 items) | 123 | 89 | `0x8d` | `8d … 8d 81 …` | 3/3 matrices |

The neighbouring attributes obey the same law, which is the independent
check: `_InstanceName` (`0x34 + 23 = 0x4b` in coso, `0x34 + 32 = 0x54` in
servo) and `_DescriptionInst` (`0x34 + 30 = 0x52` in servo).

### 1.3 The two worked value entries

coso, object `ea 08 00 00 00` at `0xdad`:

```
fe 7c 05 6b 00 00 00                      frame, len 0x6b
00 7c 06 27 00 00 00 00 00 46 47          object header record (len 0x27)
ea 08 00 00 00                            object id 8
80 ab 3c b8 6c 00  80 14 2d 7e 3d         persistent refs
80 03 97 ad 6a     80 df 6f ad 6a
02 fd 83                                  property set, class id fd 83
7c 07 3d 00 00 00                         property record, len 0x3d
4d d4 3e e8 f4 07 37 8d 81 <12 floats> fe _Position: id 0x4d = 0x34+25
49 81 e8 e0 1a 37 fe fe
```

same file, object `ea 07` at `0xd2b` (the instance identity):

```
… ea 07 00 00 00 80 aa 3c b8 6c 00 82 80 05 2d 7e 3d 80 03 97 ad 6a 80 df 6f ad 6a
02 fd 82 7c 07 54 …
4b 82 e8 c0 12 37 4c fe                 _InstanceName: id 0x4b = 0x34+23
                                        value name-id 0x4c = 0x34+24 -> pool[24] = "Part4.1"
```

servo, object `ea 05` at `0xcb9` and object `ea 04` at `0xc31`:

```
ea 04 … 54 83 e8 c0 12 37 55 fe          _InstanceName id 0x54 = 0x34+32,
                                         value 0x55 = 0x34+33 -> pool[33] = "ac2_1"
ea 05 … 56 d4 34 e8 f4 07 37 8d 81 …     _Position id 0x56 = 0x34+34
```

### 1.4 Enumeration — only `_Position`, and the camera is excluded

A matrix chunk counts as `_Position` only when its **attribute id** is the
predicted one. The value type tag is a necessary but *not sufficient*
discriminator: 461 of 3,477 valid matrices carry another attribute id, and
8 of those still carry the transform tag.

| consumer (attribute id) | valid 12-float matrices | tag |
|---|---|---|
| `_Position` (`0x34+ord`) | **3,016** | `e8 f4 07 37` (2,560), `e9 f4 07 04 37` (327), `e8 f4 07 36` (88), `e8 e4 07 37` (29), … |
| camera/view (`0x3a` in coso) | 371 + 28 | `e8 e0 07 37` / `e8 e0 07 36` |
| other transform-bearing attributes | 62 | mixed `f4 07 …`, `e4 07 …` |

coso is the clean demonstration: 8 valid matrices, **7 are `_Position`**
(the seven instance placements), and the 8th at `0x4c57` is the camera:

```
02 81 7c 07 c5 00 00 00 3a d2 5c e8 e0 07 37 8d 81 …
^ attr 0x3a          ^ tag e8 e0 07 37   ^ T = (-154.211, -48.438, 96.881)
```

The camera is rejected by *two* independent facts: attr `0x3a ≠ 0x4d`, and
type tag `e0 07 37 ≠ f4 07 37`.

---

## 2. The join — what decodes and what does not (deliverable 2)

### 2.1 What decodes

* `_InstanceName` → name-id → pool string → dot-shaped instance name
  (`0x4c → "Part4.1"`, `0x55 → "ac2_1"`). 603 distinct dot names resolve
  corpus-wide.
* `_Position` → 12-float matrix → `[tx,ty,tz]` + SO(3) rotation, as in P6-R15.
* The pool's instance → `PRDREP` chain is the existing textual pairing
  (`<PN> _InstanceName <IN> _Position PRDREP`), unchanged from P2.

### 2.2 The blocker: two objects, no join key

In every file inspected the position and the instance name are written on
**different** `fe 7c 05` objects. coso:

```
instance  ea 07  refs = 0x6cb83caa, 0x3d7e2d05, 0x6aad9703, 0x6aad6fdf   _InstanceName -> Part4.1
position  ea 08  refs = 0x6cb83cab, 0x3d7e2d14, 0x6aad9703, 0x6aad6fdf   _Position -> T(-10.137, 11.301, 2.082)
```

servo:

```
instance  ea 04  refs = 0x4f3749d5, 0x432a6f57, 0x6abc0fe1, 0x6abc0fe1   _InstanceName -> ac2_1
position  ea 05  refs = 0x4f3749d6, 0x432ad640, 0x6ac7f7fd, 0x6aea768c   _Position -> T(...)
```

The only relation is `ref[0](position) = ref[0](instance) + 1` in coso and
servo (and two refs shared in coso), i.e. *serialization adjacency*. It is
not a reference: the other handles differ, no field names the counterpart,
and the relation does not hold corpus-wide.

Measured over the 243 files whose table names `_Position` (3,016
`_Position` objects):

| link | objects | share |
|---|---|---|
| same object carries `_InstanceName` | 31 | 1.0% |
| `ref[0]-1` predecessor carries `_InstanceName` | 759 | 25.2% |
| **no byte-level instance link** | **2,226** | **73.8%** |

### 2.3 Count check — not 1:1

| quantity | count |
|---|---|
| CATProduct files scanned | 571 |
| files with a decodable name table | 356 |
| files whose table names `_Position` | 243 |
| valid 12-float matrices | 3,477 |
| … attributed `_Position` by P27-1 | 3,016 |
| … other attributes (camera/rep/…) | 461 |
| distinct dot-shaped `_InstanceName` values resolved | 603 |
| `_Position` objects with a byte-level instance link | 790 / 3,016 (26.2%) |

The population the ticket quotes (142 files / 1,853 instances) is a
*different* partition from the 243 files / 3,016 `_Position` streams: the
surplus is root-product positions, duplicate serializations (the same matrix
bytes re-emitted in the tail copy), and `_Position` attributes on
non-instance objects. The id law does not produce the ticket's 1:1 count,
so a count-fit cannot be used to close the join.

---

## 3. coso (81b1fe65) — what the law gives, and why acceptance is not run

The seven `_Position` matrices the law selects:

| offset | T (mm) | rotation |
|---|---|---|
| `0xde9` | (-10.137, 11.301, 2.082) | identity |
| `0xf93` | (0, 0, 0) | identity |
| `0x1363` | (9.863, 11.301, 6.582) | identity |
| `0x168b` | (-9.087, 46.186, 11.082) | 180°-class about Z |
| `0x17f6` | (-16.242, -18.609, 2.082) | ~-41° about Z |
| `0x2273` | (-5.721, -6.555, 6.582) | identity |
| `0x2396` | (-1.450, 32.127, 6.582) | ~123° about Z |

That is exactly one per declared instance (7), and the camera matrix is
excluded. This is a genuine improvement on the 129-B ordinal read (8 records,
root+sequential, which produced the 9.0 mm cluster with four coincident
pairs).

**The acceptance is not run** for one reason: the law gives seven matrices
and seven instance names but no *pairing*. The instance-name objects
resolved in coso are `Part4.1`, `Part5.1.2`, `Part7.1`, `Part7.2`,
`Part5.1.1`, `Part5.1.1.1` (six; `Part5.1` is serialized in the bare-pair
form and needs the P2 pairing rule to name). Pairing the seven matrices to
those names by stream order is precisely the ordinal binding the ticket says
is unproven, and a geometric "no interpenetration" check cannot distinguish
a permutation that happens to fit (the matrices are mostly collinear along
the cable axis). Running it would manufacture evidence, not read it.

---

## 4. Deliverable 6 — the exact blocker

1. **Resolved:** attribute-name ids in the framed generation
   (`id = 0x34 + ordinal0`, §1.1), so `_Position` streams *are* enumerable by
   attribute (§1.4) — the question in the title is answered.
2. **Blocked:** the object→instance join. The `_Position` value and the
   `_InstanceName` value are on different `fe 7c 05` objects; the only
   decoded relation is `ref[0]` successor / adjacent serialization
   (§2.2), which is ordinal adjacency, not a reference. 73.8% of
   `_Position` objects have no byte-level link at all.
3. **Not adopted:** no Python `src/catpart/product/` change, no Rust
   `port/src/product/` change, no `pkg`/viewer sync, no identity fallback.
   The existing strict behaviour (constraint-mesh mismatch →
   `undecodable`, `transform: None`) is untouched.

What would unblock the join, in order of expected cost:

* decode the `fd 82` / `fd 83` class-id header of the `7c 07` record (it
  distinguishes the instance property set from the position property set)
  and find the field that names the sibling object;
* or find the object-table entry that maps the position object's `ea` id to
  its owner, in the stream directory that follows the container table;
* or pin the per-instance `CtorProxy` tag in `CATCtorProxyCont` to the same
  object id — the P26 record layer already carries per-instance tags for
  42 files, but not for these 243.

---

## 5. Machine-readable claims

`docs/evidence/data/p27-position-attribute-claims.csv`:

| claim | statement | population | rate | label |
|---|---|---|---|---|
| P27-1 | name-id base: `attr-id = 0x34 + ordinal0(pool item)` | 243/243 files naming `_Position` | 100% | fact |
| P27-2 | `_Position` streams are exactly the `7c 07` chunks whose attr id is `0x34 + ordinal0('_Position')` | 3,016/3,477 valid matrices | 86.7% | fact |
| P27-3 | camera/view matrices are excluded by attr id and by type tag (`e0 07 xx` vs `f4 07 xx`) | 399/399 camera/view matrices | 100% | fact |
| P27-4 | object→instance join: no decoded reference; only `ref[0]` successor adjacency | 759/3,016 (`+1`), 31/3,016 (same object), 2,226/3,016 unbound | 26.2% linked | negative |
| P27-5 | count check: `_Position` streams do not match the declared-instance population | 3,016 streams vs 1,853 instances | — | negative |
