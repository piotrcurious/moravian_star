import math
from fractions import Fraction
from itertools import product

# ============================================================
# MORAVIAN / HERRNHUT STAR — FAREY HYPOTHESIS TEST
#
# Hypothesis:
#
#   The 26 directions of the canonical Moravian star may be
#   interpreted as a low-order Farey-type rational-direction
#   construction.
#
# This script tests that idea by constructing 3D rays from
# Farey fractions and comparing them exactly against the
# canonical 26 directions.
#
# Canonical directions:
#
#       x,y,z in {-1,0,+1}, excluding (0,0,0)
#
#       => 3^3 - 1 = 26 rays
#
# Farey construction:
#
#       take Farey fractions F_n
#       use their absolute values as normalized coordinates
#       and allow independent signs.
#
#       At n=1:
#           F_1 = {0,1}
#
#       therefore coordinates are {-1,0,+1}
#
#       => exactly the canonical 26 directions.
#
# The script tests whether this relation continues for n>1.
# ============================================================

try:
    import bpy
    import bmesh
    import mathutils
    Vector = mathutils.Vector
    HAS_BLENDER = True
except ImportError:
    HAS_BLENDER = False
    bpy = None
    bmesh = None

    class Vector:
        """Fallback 3D Vector implementation when running outside Blender."""

        def __init__(self, values):
            if isinstance(values, Vector):
                self.values = list(values.values)
            elif isinstance(values, (list, tuple)):
                self.values = [float(x) for x in values]
            else:
                self.values = [float(values)]

        @property
        def x(self):
            return self.values[0]

        @property
        def y(self):
            return self.values[1]

        @property
        def z(self):
            return self.values[2]

        def __len__(self):
            return len(self.values)

        def __getitem__(self, idx):
            return self.values[idx]

        def length(self):
            return math.sqrt(sum(v ** 2 for v in self.values))

        def normalized(self):
            l = self.length()
            if l == 0:
                return Vector([0.0] * len(self.values))
            return Vector([v / l for v in self.values])

        def dot(self, other):
            o = other.values if isinstance(other, Vector) else other
            return sum(a * b for a, b in zip(self.values, o))

        def cross(self, other):
            a = self.values
            b = other.values if isinstance(other, Vector) else other
            return Vector([
                a[1] * b[2] - a[2] * b[1],
                a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0]
            ])

        def __add__(self, other):
            o = other.values if isinstance(other, Vector) else other
            return Vector([a + b for a, b in zip(self.values, o)])

        def __radd__(self, other):
            return self.__add__(other)

        def __sub__(self, other):
            o = other.values if isinstance(other, Vector) else other
            return Vector([a - b for a, b in zip(self.values, o)])

        def __mul__(self, scalar):
            return Vector([v * float(scalar) for v in self.values])

        def __rmul__(self, scalar):
            return self.__mul__(scalar)

        def __repr__(self):
            return f"Vector(({self.x}, {self.y}, {self.z}))"


# ============================================================
# USER PARAMETERS
# ============================================================

FAREY_ORDERS = [1, 2, 3, 4]

INNER_RADIUS = 1.0
TIP_RADIUS = 2.7

# Width of pyramid bases
BASE_SIZE = 0.42

# Separate stars spatially along X for visual comparison
STAR_SPACING = 7.0

# Maximum number of rays to render per star.
# None = render everything.
MAX_RENDER_RAYS = None

CREATE_CORE = True
CREATE_SPIKES = True

# Show labels in Blender viewport
CREATE_TEXT_LABELS = True


# ============================================================
# MATERIALS
# ============================================================

def make_material(name, color, metallic=0.0, roughness=0.45):
    if not HAS_BLENDER:
        return None

    mat = bpy.data.materials.get(name)

    if mat is None:
        mat = bpy.data.materials.new(name)

    mat.diffuse_color = (*color, 1.0)
    mat.metallic = metallic
    mat.roughness = roughness

    return mat


if HAS_BLENDER:
    MAT_CORE = make_material("Star Core", (0.12, 0.20, 0.35), metallic=0.25)
    MAT_SPIKE = make_material("Star Spikes", (0.75, 0.35, 0.08), metallic=0.15)
    MAT_FAREY = make_material("Farey Construction", (0.15, 0.60, 0.30), metallic=0.10)
    MAT_TEXT = make_material("Text", (1.0, 1.0, 1.0), metallic=0.0)
else:
    MAT_CORE = MAT_SPIKE = MAT_FAREY = MAT_TEXT = None


# ============================================================
# GENERAL UTILITIES
# ============================================================

def clear_scene():
    if not HAS_BLENDER:
        return

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    # Remove orphan meshes
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def _to_fraction(val):
    if isinstance(val, Fraction):
        return val
    if isinstance(val, float):
        return Fraction(val).limit_denominator()
    return Fraction(val)


def canonical_key(v):
    """
    Exact rational/integer normalized representation.

    Scale vector so maximum absolute coordinate = 1.
    This treats vectors differing only by positive scale
    as the same geometric direction.
    """

    fx, fy, fz = (_to_fraction(val) for val in v)

    m = max(abs(fx), abs(fy), abs(fz))

    if m == 0:
        raise ValueError("Zero vector")

    return (
        fx / m,
        fy / m,
        fz / m,
    )


def vector_from_key(k):
    return Vector((
        float(k[0]),
        float(k[1]),
        float(k[2]),
    )).normalized()


def angle_between(a, b):
    a = Vector(a).normalized()
    b = Vector(b).normalized()

    d = max(-1.0, min(1.0, a.dot(b)))

    return math.degrees(math.acos(d))


def primitive_int_vector(key):
    """Convert rational canonical key to primitive integer vector tuple."""
    lcm = math.lcm(key[0].denominator, key[1].denominator, key[2].denominator)
    return (int(key[0] * lcm), int(key[1] * lcm), int(key[2] * lcm))


# ============================================================
# FAREY SEQUENCE
# ============================================================

def farey_sequence(order):
    """
    Return Farey sequence F_n.

    Example:

        F_1 = [0, 1]

        F_2 = [0, 1/2, 1]

        F_3 = [0, 1/3, 1/2, 2/3, 1]
    """

    if order < 1:
        raise ValueError("Farey order must be >= 1")

    a, b, c, d = 0, 1, 1, order
    seq = [Fraction(a, b)]

    while c <= order:
        k = (order + b) // d
        a, b, c, d = c, d, k * c - a, k * d - b
        seq.append(Fraction(a, b))

    return seq


# ============================================================
# CANONICAL MORAVIAN STAR RAYS
# ============================================================

def canonical_rays():
    rays = set()

    for x in (-1, 0, 1):
        for y in (-1, 0, 1):
            for z in (-1, 0, 1):

                if x == 0 and y == 0 and z == 0:
                    continue

                k = canonical_key((x, y, z))

                rays.add(k)

    return sorted(rays)


# ============================================================
# FAREY -> 3D RAYS
# ============================================================

def farey_rays(order):
    """
    Construct 3D rational directions from Farey fractions.

    Every coordinate belongs to F_n.

    At least one coordinate is exactly 1 after normalization.

    Independent signs are applied.

    This is intentionally a simple/natural lift of Farey
    fractions into projective 3D directions.

    For n=1:

        F_1 = {0,1}

    therefore:

        coordinates ∈ {-1,0,+1}

    yielding exactly the 26 canonical rays.
    """

    F = farey_sequence(order)

    rays = set()

    for a, b, c in product(F, repeat=3):

        if a == 0 and b == 0 and c == 0:
            continue

        # Require at least one coordinate to be exactly 1.
        #
        # This fixes projective scale.
        if not (a == 1 or b == 1 or c == 1):
            continue

        for sx, sy, sz in product((-1, 1), repeat=3):

            # Don't create signed zeros as conceptually
            # different vectors.
            x = a * sx
            y = b * sy
            z = c * sz

            k = canonical_key((x, y, z))

            rays.add(k)

    return sorted(rays)


# ============================================================
# FAREY MEDIANT SUBDIVISION RAYS
# ============================================================

def farey_mediant_rays(depth=1, max_neighbor_angle=55.0):
    """
    Construct 3D directions using vector mediants on adjacent rays.

    At depth 0, returns canonical rays.
    For depth > 0, computes vector mediant u + v for adjacent pairs (u, v)
    with angular separation <= max_neighbor_angle degrees.
    """
    current_rays = canonical_rays()

    for _ in range(depth):
        p_vecs = [primitive_int_vector(k) for k in current_rays]
        next_rays = set(current_rays)

        num_vecs = len(p_vecs)
        for i in range(num_vecs):
            v1 = p_vecs[i]
            for j in range(i + 1, num_vecs):
                v2 = p_vecs[j]
                if angle_between(v1, v2) <= max_neighbor_angle:
                    mediant = (v1[0] + v2[0], v1[1] + v2[1], v1[2] + v2[2])
                    if any(c != 0 for c in mediant):
                        next_rays.add(canonical_key(mediant))

        current_rays = sorted(next_rays)

    return current_rays


# ============================================================
# RAY COMPARISON
# ============================================================

def compare_ray_sets(canonical, test):
    canonical = set(canonical)
    test = set(test)

    intersection = canonical & test
    only_canonical = canonical - test
    only_test = test - canonical

    return {
        "canonical_count": len(canonical),
        "test_count": len(test),
        "intersection": intersection,
        "only_canonical": only_canonical,
        "only_test": only_test,
        "exact_match": canonical == test,
    }


def nearest_canonical_angles(test_rays, canonical_rays):
    """
    For every Farey ray find the angular distance to the nearest
    canonical ray.

    Because these are radial directions, this provides a useful
    geometric measure of how much the Farey construction diverges
    from the real 26-point star.
    """

    canonical_vectors = [
        vector_from_key(k)
        for k in canonical_rays
    ]

    results = []

    for k in test_rays:

        v = vector_from_key(k)

        best = 180.0

        for c in canonical_vectors:

            a = angle_between(v, c)

            if a < best:
                best = a

        results.append(best)

    return results


# ============================================================
# CREATE MESH
# ============================================================

def create_mesh_object(name, vertices, faces, material=None):
    if not HAS_BLENDER:
        return None

    mesh = bpy.data.meshes.new(name + "_Mesh")

    mesh.from_pydata(vertices, [], faces)
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)

    bpy.context.collection.objects.link(obj)

    if material:
        obj.data.materials.append(material)

    return obj


# ============================================================
# LOCAL BASIS
# ============================================================

def tangent_basis(direction):
    """
    Generate two orthogonal tangent vectors perpendicular
    to direction.
    """

    d = Vector(direction).normalized()

    # Choose a vector not parallel to d.
    if abs(d.z) < 0.8:
        ref = Vector((0, 0, 1))
    else:
        ref = Vector((0, 1, 0))

    u = d.cross(ref).normalized()
    v = d.cross(u).normalized()

    if u.cross(v).dot(d) < 0:
        v = v * -1.0

    return u, v


# ============================================================
# CREATE SPIKE
# ============================================================

def create_spike_base_vertices(key, d, base_radius, poly_sides=None):
    """
    Construct base vertices for a spike according to canonical Moravian star geometry.

    For the canonical 26-point star (rhombicuboctahedron faces):
    - Support 1 (6 axial spikes): square base aligned with coordinate axes.
    - Support 2 (12 edge spikes): square base aligned with coordinate axes/edges.
    - Support 3 (8 triangular spikes): equilateral triangle base aligned with coordinate projections.
    - Higher order Farey rays / dual polyhedra: polygon base matched to poly_sides.
    """
    x, y, z = float(key[0]), float(key[1]), float(key[2])
    abs_coords = (abs(x), abs(y), abs(z))
    center = d * base_radius

    nz = [i for i, val in enumerate(abs_coords) if val != 0]

    if poly_sides is not None:
        sides = poly_sides
    elif len(nz) == 3 and abs_coords[0] == abs_coords[1] == abs_coords[2]:
        sides = 3
    else:
        sides = 4

    if len(nz) == 1 and sides == 4:
        # Axial square spike
        idx = nz[0]
        if idx == 0:
            u, v = Vector((0, 1, 0)), Vector((0, 0, 1))
        elif idx == 1:
            u, v = Vector((1, 0, 0)), Vector((0, 0, 1))
        else:
            u, v = Vector((1, 0, 0)), Vector((0, 1, 0))

        if u.cross(v).dot(d) < 0:
            u, v = v, u

        half = BASE_SIZE
        verts = [
            center + u * half + v * half,
            center - u * half + v * half,
            center - u * half - v * half,
            center + u * half - v * half,
        ]
        return verts, 4

    elif len(nz) == 2 and sides == 4:
        # Edge square spike
        zero_idx = (set([0, 1, 2]) - set(nz)).pop()
        if zero_idx == 0:
            v_axis = Vector((1, 0, 0))
        elif zero_idx == 1:
            v_axis = Vector((0, 1, 0))
        else:
            v_axis = Vector((0, 0, 1))

        u_axis = d.cross(v_axis).normalized()
        if u_axis.cross(v_axis).dot(d) < 0:
            u_axis = u_axis * -1.0

        half = BASE_SIZE
        verts = [
            center + u_axis * half + v_axis * half,
            center - u_axis * half + v_axis * half,
            center - u_axis * half - v_axis * half,
            center + u_axis * half - v_axis * half,
        ]
        return verts, 4

    elif len(nz) == 3 and abs_coords[0] == abs_coords[1] == abs_coords[2] and sides == 3:
        # Canonical body diagonal triangular spike
        ex = Vector((1.0 if x > 0 else -1.0, 0, 0))
        ey = Vector((0, 1.0 if y > 0 else -1.0, 0))
        ez = Vector((0, 0, 1.0 if z > 0 else -1.0))

        px = (ex - d * ex.dot(d)).normalized()
        py = (ey - d * ey.dot(d)).normalized()
        pz = (ez - d * ez.dot(d)).normalized()

        if (py - px).cross(pz - px).dot(d) < 0:
            py, pz = pz, py

        scale = BASE_SIZE * 1.2
        verts = [
            center + px * scale,
            center + py * scale,
            center + pz * scale,
        ]
        return verts, 3

    else:
        # General Farey ray polygon base
        u, v = tangent_basis(d)
        verts = []
        for i in range(sides):
            theta = 2.0 * math.pi * i / sides
            p = center + u * (math.cos(theta) * BASE_SIZE) + v * (math.sin(theta) * BASE_SIZE)
            verts.append(p)
        return verts, sides


def create_spike(
    name,
    key,
    direction,
    base_radius,
    tip_distance,
    poly_sides=None,
    material=None
):
    """
    Create a pyramid whose base is tangent to the spherical
    core and whose tip lies further along the radial direction.
    """
    if not HAS_BLENDER:
        return None

    d = Vector(direction).normalized()
    tip = d * tip_distance

    base_verts, sides = create_spike_base_vertices(key, d, base_radius, poly_sides=poly_sides)

    vertices = [tuple(p) for p in base_verts]
    tip_index = len(vertices)
    vertices.append(tuple(tip))

    faces = []

    # Base face (pointing inward towards origin)
    faces.append(tuple(reversed(range(sides))))

    # Side faces (pointing outward)
    for i in range(sides):
        j = (i + 1) % sides
        faces.append((i, j, tip_index))

    return create_mesh_object(
        name,
        vertices,
        faces,
        material
    )


# ============================================================
# CREATE CENTRAL CORE
# ============================================================

def create_core(name, radius, ray_keys):
    if not HAS_BLENDER:
        return None

    mesh = bpy.data.meshes.new(name + "_Mesh")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()

    # Start with a large bounding cube
    bmesh.ops.create_cube(bm, size=radius * 10.0)

    # Slice the volume with planes perpendicular to each Farey ray.
    # This generates the exact dual polyhedron / intersection of half-spaces.
    for key in ray_keys:
        d = vector_from_key(key).normalized()

        res = bmesh.ops.bisect_plane(
            bm,
            geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
            plane_co=d * radius,
            plane_no=d,
            clear_outer=True
        )

        edges_cut = [e for e in res.get('geom_cut', []) if isinstance(e, bmesh.types.BMEdge)]
        if edges_cut:
            bmesh.ops.edgenet_fill(bm, edges=edges_cut)

    bm.to_mesh(mesh)
    bm.free()

    obj.data.materials.append(MAT_CORE)

    # Flat shading to emphasize the mathematical facets
    for poly in mesh.polygons:
        poly.use_smooth = False

    return obj


# ============================================================
# CREATE STAR
# ============================================================

def create_star(
    name,
    ray_keys,
    origin,
    material,
    render_limit=None
):
    if not HAS_BLENDER:
        return None

    root = bpy.data.objects.new(name, None)
    root.location = Vector(origin)
    bpy.context.collection.objects.link(root)

    rays = list(ray_keys)

    if render_limit is not None:
        rays = rays[:render_limit]

    core_obj = None
    ray_face_sides = {}

    if CREATE_CORE:
        # Pass the Farey rays down to carve the core
        core_obj = create_core(name + "_Core", INNER_RADIUS, rays)
        core_obj.parent = root
        core_obj.location = (0, 0, 0)

        # Inspect dual polyhedral faces on core to match polygon sides for each spike
        if core_obj and core_obj.data and len(core_obj.data.polygons) > 0:
            bm_core = bmesh.new()
            bm_core.from_mesh(core_obj.data)
            for key in rays:
                d = vector_from_key(key).normalized()
                best_face = max(bm_core.faces, key=lambda f: (f.normal.x * d.x + f.normal.y * d.y + f.normal.z * d.z))
                ray_face_sides[key] = len(best_face.verts)
            bm_core.free()

    for index, key in enumerate(rays):

        d = vector_from_key(key)
        poly_sides = ray_face_sides.get(key, None)

        obj = create_spike(
            f"{name}_Spike_{index:04d}",
            key,
            d,
            INNER_RADIUS,
            TIP_RADIUS,
            poly_sides=poly_sides,
            material=material
        )

        obj.parent = root
        obj.location = (0, 0, 0)

    return root


# ============================================================
# LABELS
# ============================================================

def add_text(
    text,
    location,
    size=0.55
):
    if not HAS_BLENDER:
        return None

    bpy.ops.object.text_add(
        location=location,
        rotation=(math.radians(90), 0, 0)
    )

    obj = bpy.context.object

    obj.data.body = text
    obj.data.align_x = 'CENTER'
    obj.data.align_y = 'CENTER'

    obj.data.size = size

    obj.data.materials.append(MAT_TEXT)

    return obj


# ============================================================
# REPORT
# ============================================================

def print_report():

    canonical = canonical_rays()

    print("")
    print("=" * 72)
    print("MORAVIAN STAR / FAREY HYPOTHESIS TEST")
    print("=" * 72)

    print("")
    print("Canonical Moravian ray count:")
    print(len(canonical))

    print("")
    print("Canonical rays consist of:")
    print("  axes:              6")
    print("  edge directions:  12")
    print("  body diagonals:    8")
    print("  --------------------")
    print("  total:            26")

    print("")
    print("Farey sequences (Coordinate lifting):")
    print("")

    for order in FAREY_ORDERS:

        F = farey_sequence(order)
        rays = farey_rays(order)

        comparison = compare_ray_sets(
            canonical,
            rays
        )

        angles = nearest_canonical_angles(
            rays,
            canonical
        )

        avg_angle = (
            sum(angles) / len(angles)
            if angles else 0
        )

        max_angle = max(angles) if angles else 0

        print(
            f"F_{order}:"
        )

        print(
            f"    Farey fractions : {len(F)}"
        )

        print(
            f"    3D rays         : {len(rays)}"
        )

        print(
            f"    exact overlap   : "
            f"{len(comparison['intersection'])}"
        )

        print(
            f"    extra rays      : "
            f"{len(comparison['only_test'])}"
        )

        print(
            f"    missing rays    : "
            f"{len(comparison['only_canonical'])}"
        )

        print(
            f"    exact match     : "
            f"{comparison['exact_match']}"
        )

        print(
            f"    mean angle      : "
            f"{avg_angle:.6f} degrees"
        )

        print(
            f"    maximum angle   : "
            f"{max_angle:.6f} degrees"
        )

        print("")

    print("Farey Mediant Subdivision (Geometric recursion):")
    print("")

    for depth in [0, 1]:
        m_rays = farey_mediant_rays(depth)
        m_comparison = compare_ray_sets(canonical, m_rays)

        print(f"Mediant Subdivision Depth {depth}:")
        print(f"    3D rays         : {len(m_rays)}")
        print(f"    exact overlap   : {len(m_comparison['intersection'])}")
        print(f"    extra rays      : {len(m_comparison['only_test'])}")
        print(f"    exact match     : {m_comparison['exact_match']}")
        print("")

    print("=" * 72)

    print(
        "INTERPRETATION:"
    )

    print(
        "If F_1 produces exactly 26 rays, while F_n for n>1 "
        "produces additional rational directions, the result "
        "supports a Farey-like interpretation of the 26-ray "
        "configuration, but not the claim that the Moravian "
        "star itself is literally a Farey sequence."
    )

    print("=" * 72)
    print("")


# ============================================================
# BUILD SCENE
# ============================================================

def build_scene():

    canonical = canonical_rays()

    print_report()

    if not HAS_BLENDER:
        print("[Notice] Blender environment not detected. Visual scene creation skipped, report complete.")
        return

    clear_scene()

    # --------------------------------------------------------
    # Canonical star
    # --------------------------------------------------------

    x = 0

    create_star(
        "CANONICAL_26_POINT",
        canonical,
        origin=(x, 0, 0),
        material=MAT_SPIKE,
        render_limit=MAX_RENDER_RAYS
    )

    if CREATE_TEXT_LABELS:

        add_text(
            "Canonical\n26-point star",
            (x, -4.5, 0)
        )

    # --------------------------------------------------------
    # Farey stars
    # --------------------------------------------------------

    for i, order in enumerate(FAREY_ORDERS):

        rays = farey_rays(order)

        x = (i + 1) * STAR_SPACING

        create_star(
            f"FAREY_ORDER_{order}",
            rays,
            origin=(x, 0, 0),
            material=MAT_FAREY,
            render_limit=MAX_RENDER_RAYS
        )

        if CREATE_TEXT_LABELS:

            add_text(
                f"Farey F_{order}\n{len(rays)} rays",
                (x, -4.5, 0)
            )

    # --------------------------------------------------------
    # World setup
    # --------------------------------------------------------

    bpy.context.scene.world.color = (
        0.015,
        0.015,
        0.015
    )

    center_x = STAR_SPACING * (len(FAREY_ORDERS) / 2)

    # Camera looking at all stars from front-above
    bpy.ops.object.camera_add(
        location=(
            center_x,
            -32.0,
            12.0
        )
    )

    camera = bpy.context.object
    bpy.context.scene.camera = camera

    # Point camera toward center of row
    target = Vector((center_x, 0, 0))
    direction = target - camera.location

    camera.rotation_euler = direction.to_track_quat(
        '-Z',
        'Y'
    ).to_euler()

    # Sun Light for even illumination across all stars
    bpy.ops.object.light_add(
        type='SUN',
        location=(center_x, -10, 20)
    )
    sun = bpy.context.object
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(45), math.radians(15), math.radians(10))

    # Fill Light from side
    bpy.ops.object.light_add(
        type='SUN',
        location=(0, -10, 10)
    )
    fill = bpy.context.object
    fill.data.energy = 1.0
    fill.rotation_euler = (math.radians(30), math.radians(-30), math.radians(0))

    # Ground Plane
    bpy.ops.mesh.primitive_plane_add(
        size=200,
        location=(center_x, 0, -3.2)
    )

    ground = bpy.context.object

    ground.data.materials.append(
        make_material(
            "Ground",
            (0.025, 0.025, 0.025)
        )
    )

    # Render settings
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE_NEXT' if hasattr(bpy.types, 'RenderSettings') and 'BLENDER_EEVEE_NEXT' in dir(bpy.types) else 'BLENDER_EEVEE'
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.filepath = 'farey_stars_render.png'
    bpy.ops.render.render(write_still=True)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    build_scene()
