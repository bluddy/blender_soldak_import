import sys
import os
import time
import struct
from collections import namedtuple

if __name__ != '__main__':
    import bpy
    import bmesh
    import mathutils

# Format ----

HEADER_FORMAT = '<' + ('i' * 10)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

Header = namedtuple('Header', ['id', 'version', 'numSurfaces',
        'numTris', 'numVerts', 'surfaceOffset', 'trisOffset', 'vertsOffset',
        'weightsOffset', 'collapseMappingsOffset'])

def read_header(file):
    str = file.read(HEADER_SIZE)
    return Header._make(struct.unpack(HEADER_FORMAT, str))

SURFACE_FORMAT = '<' + ('i' * 6)
SURFACE_SIZE = struct.calcsize(SURFACE_FORMAT)
Surface = namedtuple('Surface', ['surfaceNumber', 'numVerts', 'numTris',
        'vertsOffset', 'trisOffset', 'collapseMappingsOffset'])

def read_surface(file):
    str = file.read(SURFACE_SIZE)
    return Surface._make(struct.unpack(SURFACE_FORMAT, str))

TRI_FORMAT = '<' + ('i' * 3)
TRI_SIZE = struct.calcsize(TRI_FORMAT)

def read_tri(file):
    str = file.read(TRI_SIZE)
    return struct.unpack(TRI_FORMAT, str)

VERT_FORMAT = '<' + ('f' * 2) + ('f' * 3) + ('f' * 4) + ('i' * 2)
VERT_SIZE = struct.calcsize(VERT_FORMAT)

Vert = namedtuple('Vert', ['u', 'v', 'normal', 'tangent', 'numBones', 'firstBone'])

def read_vert(file):
    str = file.read(VERT_SIZE)
    data = struct.unpack(VERT_FORMAT, str)
    v = Vert(data[0], data[1], (data[2], data[3], data[4]), (data[5], data[6], data[7], data[8]), data[9], data[10])
    return v

VERTBONE_FORMAT = '<i' + ('f' * 4)
VERTBONE_SIZE = struct.calcsize(VERTBONE_FORMAT)

VertBone = namedtuple('VertBone', ['boneIndex', 'vertOffset', 'boneWeight'])

def read_vertbone(file):
    str = file.read(VERTBONE_SIZE)
    data = struct.unpack(VERTBONE_FORMAT, str)
    vb = VertBone(data[0], (data[1], data[2], data[3]), data[4])
    return vb

# Loader -----

def load(operator,
         context,
         filepath=""
         ):

    print("importing MDM: %r..." % (filepath), end="")

    time1 = time.clock()

    name = os.path.split(os.path.splitext(filepath)[0])[-1]

    with open(filepath, 'rb') as file:

        header = read_header(file)
        if header.id != 0x12121212:
            print('\tFatal Error:  Not a valid mdm file: %r' % filepath)
            file.close()
            return

        scene = context.scene

        # Load all surfaces
        surface_data = []
        file.seek(header.surfaceOffset)
        for s in range(header.numSurfaces):
            surface_data.append(read_surface(file))

        # Create start offset into vertices so we can look up vertBones
        surface_startVerts = []
        total = 0
        for s in surface_data:
            surface_startVerts.append(total)
            total += s.numVerts

        # Read all vertBone data into memory
        file.seek(header.weightsOffset)
        vertbone_data = []
        for _ in range(header.numVerts):
            vertbone_data.append(read_vertbone(file))

        # Loop over all surfaces
        for surf_num, surface in enumerate(surface_data[:1]):

            # Create a new mesh (not editable)
            mesh = bpy.data.meshes.new("mesh" + str(surf_num))
            obj = bpy.data.objects.new("Foo" + str(surf_num), mesh)
            scene.objects.link(obj)

            # Make a bmesh (editable) per surface
            bm = bmesh.new()

            # Add the vertices
            file.seek(surface.vertsOffset)
            vertices = [] # these are blender objects
            st = surface_startVerts[surf_num]
            # Match vertbones to vertices
            for vb_data in vertbone_data[st : st + surface.numVerts]:
                vert_data = read_vert(file)
                v = bm.verts.new(vb_data.vertOffset)
                v.normal = mathutils.Vector(vert_data.normal)
                vertices.append(v)

            # Add the triangles
            file.seek(surface.trisOffset)
            for _ in range(surface.numTris):
                tri = read_tri(file)
                bm.faces.new([vertices[i] for i in tri])
                #bm.faces.new([vertices[tri[0]], vertices[tri[1]], vertices[tri[2]]])

            # Convert back to mesh
            # mesh = context.object.data
            mesh = obj.data
            bm.to_mesh(mesh)
            bm.free()

        scene.objects.active = obj
        obj.select = True

        print(" done in %.4f sec." % (time.clock() - time1))

    return {'FINISHED'}

if __name__ == '__main__':
    filename = sys.argv[1]
    with open(filename, 'rb') as f:
        header = read_header(f)
        print("Header: ", header)
        print("vertsOffset: {:x}".format(header.vertsOffset))

        f.seek(header.surfaceOffset)
        for surf_num in range(header.numSurfaces):
            surface = read_surface(f)
            print("Surface ", surf_num, " :", surface)

        tris = {}

        f.seek(header.trisOffset)
        for i in range(header.numTris):
            tri = read_tri(f)
            if tri in tris:
                print("Tri {} matches tri {}!!!".format(i, tris[tri]))
            tris[tri] = i
            print("Tri ", i, " :", tri)

        # Vertices ---
        f.seek(header.vertsOffset)
        for vert_num in range(header.numVerts):
            vert = read_vert(f)
            print("Vertice ", vert_num, " :", vert)

        f.seek(header.weightsOffset)
        for vb_num in range(header.numVerts):
            vb = read_vertbone(f)
            print("VertBone ", vb_num, " :", vb)
