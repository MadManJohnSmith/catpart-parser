# P2.8 — Object-level `_Position` → instance join on the 10 mesh files (probe, 2026-11-18)

**Verdict: NO HYPOTHESIS PINS. 0/95 instances bind unambiguously.**

The P2.7 probe tested byte-level references and stopped at 73.8% unbound.
This probe tests the three object-level joins on the ten explicit-only
count-consistent `connector_proxy_mesh` files (95 instances). H1 (object
successor) is a real, near-uniform serialization relation — 70/95 by
`obj_id + 1`, 57/95 in the eight files that close completely — but it is
still adjacency, not a reference; it fails on 25/95 and on both V5R21 files. H2
(shared `_Reps`/PRDREP parent, walked transitively) is **0/95**: no object
references both the instance object and its position object. H3 (constraint
frames) is **0/95**: the `CstIndex`/`_hasConnections` objects reference
neither object, and the SP-02 files carry no 129-byte `CATCtorProxyCont`
records at all. Geometric acceptance was run where a part map exists and
**rejects H1** (19/45 penetrating pairs on `322c8e13`, 6/10 on `0d60a2bc`,
5/10 on `1b8c4500`); elsewhere it is blocked by the part→file map, by open
or partial part meshes, by the unproven part-frame assumption, and by the
undecoded constraint→instance-pair map. No binding change, no identity
fallback, no Python/Rust edit.

Probe: [`scripts/triage/p28_object_join_probe.py`](../../scripts/triage/p28_object_join_probe.py)
(`--selftest`, `--report`). Corpus read-only; it imports the committed
pool/position layer (`p27_position_attr_probe`, `fixtures_assembly`).

```bash
export LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH
python3 -I scripts/triage/p28_object_join_probe.py --selftest
python3 -I scripts/triage/p28_object_join_probe.py --report
```

---

## 1. A probe defect that the corrected scan fixes

P2.7's object census used
`re.finditer(b"\xfe\x7c\x05", data)`. `0x7c` is the regex alternation
operator, so the compiled pattern is `\xfe|\x05` and matches single bytes;
the frame checks then accept a subset and over-count (496 "frames" where
the literal scan finds 314 on `590430c6`). The **join conclusion is
unchanged**, but the P2.7 frame/ref counts are not a trustworthy
denominator. This probe scans the literal bytes `7c 05 <u32 len>` and
validates the `7c 06` header; it finds the same objects in both
generations (the older stream prefixes the record with a separator byte,
the V5R21 nested stream prefixes it with a record byte; neither prefix is
part of the object header).

The ten target files and their object generations:

| file | sha16 | instances | object records | explicit `_Position` | named instance objects |
|---|---|---:|---:|---:|---:|
| tensor | `2107dc0a` | 9 | 175 | 9 | 9 |
| Symmetry of Pata | `a5d51be5` | 28 | 791 | 28 | 23 |
| servo 996r_MODIFICADO | `2b6c0970` | 10 | 213 | 10 | 10 |
| SP02_ALPHA_BLOC_PROPU (`CATIA_vol`) | `590430c6` | 14 | 314 | 14 | 14 |
| SP02_BETA_BLOC_AILERONS (`CATIA_vol`) | `1b8c4500` | 5 | 85 | 5 | 5 |
| Fabrication coupleur coiffe | `bad5257b` | 5 | 88 | 5 | 5 |
| Moule coiffe SP02 test | `0d60a2bc` | 5 | 72 | 5 | 5 |
| SP02_ALPHA_BLOC_PARACHUTE | `974ef60f` | 4 | 70 | 4 | 4 |
| SP02_ALPHA_BLOC_PROPU (`catia_lucas`) | `322c8e13` | 10 | 158 | 10 | 10 |
| SP02_BETA_BLOC_AILERONS (`catia_lucas`) | `b96ef5f9` | 5 | 85 | 5 | 5 |

`a5d51be5` has five instances (`Bearing 4x10x4.2`, both `ISO 4032 NUT`
instances, both `ISO 7093-1 WASHER` instances) whose `_InstanceName`
value is the predefined id `0x32` followed by a 4-byte token
(`32 cf 00 00 00`, …), not a pool name-id. **Five instances have no name
join at all** in that file.

---

## 2. H1 — object successor: 70/95, not a reference

H1 asks whether the position object is the successor of the instance
object: `obj_id(position) = obj_id(instance) + 1` (or `ref[0] + 1`), with
the ordinal order matching the instance names.

| file | id + 1 | ref[0] + 1 | shared refs ≥1 | shared refs ≥2 | order = names |
|---|---:|---:|---:|---:|---|
| `2107dc0a` | 9/9 | 6/9 | 1/9 | 0 | yes |
| `a5d51be5` | 8/23 | 0/23 | 8/23 | 1 | no (5 names unresolvable) |
| `2b6c0970` | 5/10 | 0/10 | 0/10 | 0 | yes |
| `590430c6` | 14/14 | 12/14 | 0/14 | 0 | yes |
| `1b8c4500` | 5/5 | 4/5 | 0/5 | 0 | yes |
| `bad5257b` | 5/5 | 3/5 | 5/5 | 0 | yes |
| `0d60a2bc` | 5/5 | 3/5 | 5/5 | 2 | yes |
| `974ef60f` | 4/4 | 3/4 | 4/4 | 0 | yes |
| `322c8e13` | 10/10 | 10/10 | 10/10 | 3 | yes |
| `b96ef5f9` | 5/5 | 4/5 | 5/5 | 0 | yes |
| **total** | **70/95** | **45/95** | **38/95** | **6/95** | **9/10 files** |

Eight files close completely (57/95): every instance object is immediately
followed by its position object, the position object carries `_Reps` +
`_Position`, and the sequence of names is the pool order. The two V5R21
files do **not** close: `2b6c0970` has five gaps of +3 (`c8→cb`, `e0→e3`,
`f8→fb`, `108→10b`, `118→11b`), and `a5d51be5` has five unnamed instances
and only 8/23 successes.

More importantly, the relation is not a reference. The position object's
own handle (e.g. `a7d90b97` on `322c8e13`) appears in its `refs[0]` and in
**no other object's references or attribute values**. The instance's
`refs[0]` is likewise owned only by itself. `obj_id + 1` is serialization
adjacency: it is the same class of evidence P2.7 rejected, now stated at
the object level. It is also not stable corpus-wide (25/95 miss).

`590430c6` is the clearest illustration that `ref[0] + 1` is a red
herring: it holds 14/14 by object id but 0/14 shared references, while
`322c8e13` holds 10/10 with 1–2 shared document handles. The shared
handles are document-scope constants (`0x691b6ed3`, `0x691b6da0`), shared
by dozens of objects; they do not join a pair.

---

## 3. H2 — shared `_Reps`/PRDREP parent: 0/95

The instance object, its connector, the position object and the PRDREP
object were walked with **all** handle slots, including the 4-byte values
inside attribute chunks (the `_Connectors` / `_ShapeConnector` /
`_ToConnectors` values), not only `refs[]`. Worked example `322c8e13`,
instance `SP02_ALPHA_PROPU.1`:

```
instance obj 4  refs = a7d90b96, 431ef617, 691b6ed3, 691b6da0
               _Connectors value = 431ef616
connector obj 2f refs = ba25833b, 431ef616, 691b6ed3, 691b6ed3
               _ToConnectors (obj 32) value = 431ef616
position obj 5  refs = a7d90b97, 431ef619, 691b6ed3, 691b6da0
               _Position + _Reps
```

The instance→connector edge is real (`_Connectors 431ef616` ↔ connector
`refs[1]`). The position side is not: `431ef619` is owned only by the
position object, and no object (frame ref or attribute value) references
the position object's own handle `a7d90b97`. A transitive walk from the
constraint objects (`CstIndex`/`_hasConnections`) reaches **0** instance
objects and **0** position objects at depth ≤ 4 on all ten files. The
shared document handles make the graph connected but carry no pair
information.

H2 as stated ("both objects are referenced by the same `_Reps`/PRDREP
parent") is therefore false: **0/95**.

---

## 4. H3 — constraint frames name the pair: 0/95

The `CstIndex` / `_hasConnections` objects are present (1–8 per file) and
carry the identity `_Position` frame (`e9 f4 07 04 37`) described by P3.
They reference **neither** the instance handle nor the position handle:
0/95. The same holds for the `CONNECTION`/`CONNECTOR` objects in the tail
copy: their `_ToConnectors` / `_ToConnectorsFamily` / `_ToProxies` values
name connector handles (e.g. `431ef616` / `431ef618`), never the instance
or position object.

The 129-byte `CATCtorProxyCont` fallback is also unavailable on these
files: `parse_129b_transform_records` finds **0** records on all ten
SP-02 files (only `2107dc0a` carries 26 records, and their ids `0x4, 0xd,
0x42, …` do not include the nine position object ids). There is no
constraint-proxy tag to join.

---

## 5. Geometric acceptance — run where possible, rejected; blocked elsewhere

The acceptance rule was: transform the decoded part meshes by the H1
position, require no interpenetration and at least one touching pair per
declared constraint. It fails before and after the geometry:

### 5.1 Part → file map (name-only catalog, ambiguous)

The product carries `_PartNumber` strings; the repository resolves parts
by stem. The same stem exists in several corpus folders with **different
geometry**, and there is no decoded document key to choose:

| file | unique part numbers | same-folder exact stem | ambiguity |
|---|---:|---:|---|
| `322c8e13` | 6 | 6/6 | 6 stems exist in 3 folders; e.g. `AILERON` 12 tris (open) vs 28 tris (closed), `BAGUE_0` 1056 vs 4152 tris, `PROPU` 472 vs 1368 tris |
| `590430c6` | 9 | 8/9 | `Support clavier` has **no** CATPart anywhere in the corpus; `Vis-Retrein`/`Bague-Vissage-Propu` have failing variants |
| `2107dc0a` | 8 | 0/8 | the folder has `base`, `brazo_1`, `rodamiento`, `rodamiento_menor`; `Part1/2/3/4/6`, `Part8`, `Part9`, `694zz` have no file in it. Corpus-wide stem hits are unrelated parts in other repos |
| `0d60a2bc` | 5 | 4/5 | `SP02_BETA_COIFFE` is a sibling folder; `Pièce1`/`Piece1` accent variant maps two instances to one file (unproven) |
| `1b8c4500`, `b96ef5f9` | 2 | 2/2 | `Placement_Ailerons` 1824 tris (open) vs 88 tris (open), `AILERON` 12 tris |
| `974ef60f` | 4 | 3/4 | `ST3215_Servo` has 3 different files (3.4k/22.2k/30.6k tris), `Trappe_Parachute` 4 vs 112 tris |
| `bad5257b` | 4 | 2/4 | `COUPLEUR`/`COIFFE` are in a sibling folder; all four meshes are open except `COIFFE` |
| `a5d51be5` | 11 | 5/11 | 5 instance names are predefined ids (see §1); `servo 996r`, `M3x20`, `Bearing`, screws have no same-folder file |
| `2b6c0970` | 7 | 4/7 | only `MIDDLE_SIDE`, `TOP_SIDE`, `Tapa servo`, `ROUND_MOUNT`; the six screw instances have no file |
| coso (`81b1fe65`) | 3 | 0/3 | the folder has 4 CATParts (`base`, `brazo_1`, `rodamiento`, `rodamiento_menor`) for 3 part numbers; no decoded key assigns them |

The four "coso plus three" files the ticket names are therefore not all
mappable: coso is 0/3 by name, tensor is 0/8, and only the SP-02
products have a defensible exact-stem map — and even they have duplicate
variants.

### 5.2 Mesh completeness

Every candidate product has at least one open or partial part mesh, so a
"no interpenetration" pass over the whole assembly is not a pass over the
whole part:

| file | open / partial part meshes (boundary edges) |
|---|---|
| `322c8e13` | `PROPU` 326/2215, `RETREINT` 466/9665, `AILERON` 12 tris open (two variants) |
| `590430c6` | `PROPU`, `RETREINT`, `Vis-Retrein` 790/…, `Bague-Vissage` 98/… |
| `0d60a2bc` | `Piece1` 474/…, `coiffymax_sp` 451/… |
| `1b8c4500` / `b96ef5f9` | `Placement_Ailerons` 1824/… (or 88/…), `AILERON` 12 tris |
| `974ef60f` | `Cage_Para` 943/…, `BAGUE_2` 62/…, `ST3215_Servo` 929/…, `Trappe` 8/… |
| `bad5257b` | `COUPLEUR` 1636/…, `Moule-Coupleur` 2186/…, `Moule-Negatif` 1279/… |

### 5.3 The unproven frame

The placement applies `T + R·v` to the exported mesh (the viewer's
`composeCatiaMatrix` convention). There is no decoded evidence that the
exported CATPart mesh is in the part's placement frame rather than a local
axis system. This assumption is not tested or documented anywhere in the
repo; a wrong frame makes every interpenetration test meaningless. It is a
blocker in its own right.

### 5.4 The runs

Triangle-level (Möller intersection; coplanar overlap classified as
contact), parts mapped by exact stem, H1 document order:

| file | part variant | pairs | penetrating | touching | verdict |
|---|---|---:|---:|---:|---|
| `322c8e13` | `CATIA_vol` | 45 | 19 | 22 | reject |
| `322c8e13` | `catia_lucas` | 45 | 21 | 24 | reject |
| `322c8e13` | `CATIA_vol`, reverse order | 45 | 26 | 32 | worse |
| `0d60a2bc` | `Usinage` + `SP02_BETA` | 10 | 6 | 7 | reject |
| `1b8c4500` | `CATIA_vol/SP02_BETA` | 10 | 5 | 5 | reject |

Some of these crossings are nominal fits, not real interpenetration:
`BAGUE_1` (annulus r 29..50) sits on `TUBE_PROPU` (annulus r 27..29) and
the two independently tessellated r=29 surfaces cross by fractions of a
millimetre — 1200 triangle pairs on `322c8e13` are that artifact. A raw
triangle test cannot separate nominal contact from penetration without a
penetration-depth tolerance, which the ticket does not define. The
`AILERON` parts, however, cross the tube across tens of millimetres; that
is either a wrong pairing, a wrong part variant, or a bad 12/28-triangle
mesh. In all three readings, no file passes.

### 5.5 Constraint → pair map

"At least one touching pair **per declared constraint**" cannot be
evaluated: H3 shows the constraint objects do not name their instances,
and no constraint→instance-pair map is decoded anywhere in the repo. The
pool's `Coïncidence.N` / `Contact surfacique.N` strings are a flat name
table, not a graph; the connector handles they would need are not joined
to the position side (§3).

---

## 6. The exact blocker

1. **H1 is adjacency, not a reference.** `obj_id + 1` is exact on 8/10
   files (57/95), but the position object is not referenced by any object;
   the relation breaks on 25/95 and on both V5R21 files. Binding by it
   would be the serialization-order guess the ticket forbids, now with a
   better denominator.
2. **H2 is false.** No `_Reps`/PRDREP/constraint object references the
   position object; the instance's connector edge (`_Connectors` ↔
   connector `refs[1]`) exists but the position side is orphaned.
3. **H3 is false.** `CstIndex`/`_hasConnections` reference neither object;
   the SP-02 files carry no 129-byte `CATCtorProxyCont` records, and
   `2107dc0a`'s 26 record ids do not include the position ids.
4. **Geometric acceptance cannot be run as specified.** The part→file map
   is name-only and ambiguous (0/3 for coso, 0/8 for tensor, 8/9 for
   `590430c6`); every candidate product has an open/partial part mesh; the
   part placement frame is unproven; and no constraint→instance-pair map
   exists. Where it was run (3 files), H1 is rejected.
5. **No code change.** No Python `src/catpart/` edit, no Rust
   `port/src/product/` edit, no `pkg`/viewer sync, no identity fallback.
   The strict `undecodable` / `transform: None` behaviour is untouched.

What would unblock the join, in order of expected cost:

* decode the `_Reps`/`_RepresentedBy` values as a reference and find the
  object that owns the position handle (the position side is the orphan);
* decode the `CATCtorProxyCont` per-instance tags on the V5R21 nested
  files and join them to the object ids (the SP-02 files have no records);
* decode a part-document key (the `_RefProduct` value or the catalog
  entry) so the part→file map is not a stem guess;
* define a penetration-depth tolerance and a part-frame law, then rerun
  the geometric gate — without them the raw triangle test is not
  acceptance evidence.

---

## 7. Machine-readable register

- `docs/evidence/data/p28-object-join-files-claims.csv` — 10 rows, one
  per file: instances, explicit positions, named objects, id+1, ref0+1,
  shared refs, order, H2, H3, outcome.
- `docs/evidence/data/p28-object-join-claims.csv` — 7 corpus-wide claims:

| claim | statement | rate | label |
|---|---|---|---|
| P28-1 | H1 object successor (`obj_id + 1`) | 70/95 = 73.68% (8 files 57/57; `2b6c0970` 5/10; `a5d51be5` 8/28) | negative (adjacency, not a reference) |
| P28-2 | H1 first-reference successor (`ref[0] + 1`) | 45/95 = 47.37% | negative |
| P28-3 | H2 same `_Reps`/PRDREP parent references both objects | 0/95 | negative |
| P28-4 | H3 `CstIndex`/`_hasConnections` names the pair | 0/95 | negative |
| P28-5 | instance order equals object order | 9/10 files (5 names unresolvable on `a5d51be5`) | negative (ordinal) |
| P28-6 | geometric acceptance (no interpenetration) | 0/3 runnable files pass | negative |
| P28-7 | part→file resolution by exact stem | 6/10 files fully resolvable anywhere; coso 0/3, tensor same-folder 0/8, `590430c6` 8/9 | blocked |

---

## 8. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH

python3 -I scripts/triage/p28_object_join_probe.py --selftest
python3 -I scripts/triage/p28_object_join_probe.py --report

# geometric runs (temporary probe, not committed):
#   triangle intersection over the placed part meshes; see §5.4
```

The corpus is read-only; no binaries are committed. The probe writes
nothing.
