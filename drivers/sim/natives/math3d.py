# -*- coding: utf-8 -*-
"""NeoX math3d 的纯 Python 替代：vector / vector2 / matrix(4x4，行向量约定 v' = v·M) / rotation(四元数)。
未实现的属性走模块级 __getattr__ 记录（便于补齐）。"""
import math

MISSING = {}


def _miss(cls, name):
    MISSING[(cls, name)] = MISSING.get((cls, name), 0) + 1
    raise AttributeError("%s.%s 未实现" % (cls, name))


class vector(object):
    __slots__ = ("x", "y", "z")

    def __init__(self, x=0.0, y=0.0, z=0.0):
        if isinstance(x, vector):
            x, y, z = x.x, x.y, x.z
        elif isinstance(x, (tuple, list)):
            x, y, z = (list(x) + [0.0, 0.0, 0.0])[:3]
        self.x = float(x); self.y = float(y); self.z = float(z)

    def __getattr__(self, n): _miss("vector", n)
    def __repr__(self): return "vector(%.3f, %.3f, %.3f)" % (self.x, self.y, self.z)
    def __iter__(self): return iter((self.x, self.y, self.z))
    def __getitem__(self, i): return (self.x, self.y, self.z)[i]
    def __setitem__(self, i, v): setattr(self, "xyz"[i], float(v))
    def __eq__(self, o): return isinstance(o, vector) and self.x == o.x and self.y == o.y and self.z == o.z
    def __ne__(self, o): return not self.__eq__(o)
    def __hash__(self): return hash((self.x, self.y, self.z))
    def __add__(self, o): return vector(self.x + o.x, self.y + o.y, self.z + o.z)
    def __sub__(self, o): return vector(self.x - o.x, self.y - o.y, self.z - o.z)
    def __neg__(self): return vector(-self.x, -self.y, -self.z)
    def __iadd__(self, o): self.x += o.x; self.y += o.y; self.z += o.z; return self
    def __isub__(self, o): self.x -= o.x; self.y -= o.y; self.z -= o.z; return self

    def __mul__(self, o):
        if isinstance(o, matrix):
            return o.transform_coord(self)
        if isinstance(o, vector):
            return vector(self.x * o.x, self.y * o.y, self.z * o.z)
        return vector(self.x * o, self.y * o, self.z * o)
    __rmul__ = __mul__

    def __imul__(self, o):
        r = self * o; self.x, self.y, self.z = r.x, r.y, r.z; return self

    def __truediv__(self, o): return vector(self.x / o, self.y / o, self.z / o)
    def __itruediv__(self, o): self.x /= o; self.y /= o; self.z /= o; return self
    __div__ = __truediv__

    @property
    def length(self): return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)
    @property
    def length_sqr(self): return self.x * self.x + self.y * self.y + self.z * self.z
    @property
    def is_zero(self): return self.x == 0 and self.y == 0 and self.z == 0
    def __abs__(self): return self.length          # UtilsMath.get_plane_dis/get_space_dis 用 abs(v) 取长度
    # 推断：DoorUnit.load_ext_model 用 `dis < min_dis`（两个差向量）挑最近的门灯，真机不报错 -> NeoX vector 可比较，按长度最合语义
    def __lt__(self, o): return self.length_sqr < o.length_sqr
    def __le__(self, o): return self.length_sqr <= o.length_sqr
    def __gt__(self, o): return self.length_sqr > o.length_sqr
    def __ge__(self, o): return self.length_sqr >= o.length_sqr

    def normalize(self):
        L = self.length
        if L > 1e-12: self.x /= L; self.y /= L; self.z /= L
        return self
    def normalized(self):
        return vector(self).normalize()
    def dot(self, o): return self.x * o.x + self.y * o.y + self.z * o.z
    def cross(self, o):
        return vector(self.y * o.z - self.z * o.y, self.z * o.x - self.x * o.z, self.x * o.y - self.y * o.x)
    def set(self, x, y=None, z=None):
        if isinstance(x, vector): x, y, z = x.x, x.y, x.z
        self.x, self.y, self.z = float(x), float(y), float(z)
    def assign(self, o): self.set(o)
    def copy(self): return vector(self)
    def distance(self, o): return (self - o).length
    def lerp(self, o, t): return vector(self.x + (o.x - self.x) * t, self.y + (o.y - self.y) * t, self.z + (o.z - self.z) * t)
    def intrp(self, a, b, t):
        r = a.lerp(b, t); self.set(r); return self
    def yaw_to(self): return math.atan2(self.x, self.z)


Vector3 = vector


class vector2(object):
    __slots__ = ("x", "y")

    def __init__(self, x=0.0, y=0.0):
        if isinstance(x, vector2): x, y = x.x, x.y
        self.x = float(x); self.y = float(y)
    def __getattr__(self, n): _miss("vector2", n)
    def __repr__(self): return "vector2(%.3f, %.3f)" % (self.x, self.y)
    def __add__(self, o): return vector2(self.x + o.x, self.y + o.y)
    def __sub__(self, o): return vector2(self.x - o.x, self.y - o.y)
    def __mul__(self, k): return vector2(self.x * k, self.y * k) if not isinstance(k, vector2) else vector2(self.x * k.x, self.y * k.y)
    __rmul__ = __mul__
    def __truediv__(self, k): return vector2(self.x / k, self.y / k)
    def __neg__(self): return vector2(-self.x, -self.y)
    def __eq__(self, o): return isinstance(o, vector2) and self.x == o.x and self.y == o.y
    def __hash__(self): return hash((self.x, self.y))
    def __iter__(self): return iter((self.x, self.y))
    @property
    def length(self): return math.hypot(self.x, self.y)
    def __abs__(self): return self.length
    @property
    def length_sqr(self): return self.x * self.x + self.y * self.y
    @property
    def is_zero(self): return self.x == 0 and self.y == 0
    def normalize(self):
        L = self.length
        if L > 1e-12: self.x /= L; self.y /= L
        return self
    def dot(self, o): return self.x * o.x + self.y * o.y
    def cross(self, o): return self.x * o.y - self.y * o.x
    def set(self, x, y=None):
        if isinstance(x, vector2): x, y = x.x, x.y
        self.x, self.y = float(x), float(y)


class rotation(object):
    """四元数 (x,y,z,w)。"""
    __slots__ = ("x", "y", "z", "w")

    def __init__(self, x=0.0, y=0.0, z=0.0, w=1.0):
        if isinstance(x, rotation): x, y, z, w = x.x, x.y, x.z, x.w
        self.x, self.y, self.z, self.w = float(x), float(y), float(z), float(w)
    def __getattr__(self, n): _miss("rotation", n)
    def __repr__(self): return "rotation(%.3f,%.3f,%.3f,%.3f)" % (self.x, self.y, self.z, self.w)

    @staticmethod
    def from_axis_angle(axis, ang):
        a = vector(axis).normalized(); s = math.sin(ang / 2)
        return rotation(a.x * s, a.y * s, a.z * s, math.cos(ang / 2))

    def to_matrix(self):
        x, y, z, w = self.x, self.y, self.z, self.w
        m = matrix()
        m.m = [[1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w), 0],
               [2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w), 0],
               [2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y), 0],
               [0, 0, 0, 1]]
        return m
    def rotate_vector(self, v): return self.to_matrix().transform_normal(v)

    def slerp(self, a, b, t, shortest=True):
        """就地：self = slerp(a, b, t)。用法见 CamModeBase._get_tran_interp: rot1.slerp(rot1, rot2, ratio, True)"""
        ax, ay, az, aw = a.x, a.y, a.z, a.w
        bx, by, bz, bw = b.x, b.y, b.z, b.w
        d = ax * bx + ay * by + az * bz + aw * bw
        if shortest and d < 0:
            bx, by, bz, bw, d = -bx, -by, -bz, -bw, -d
        if d > 0.9995:
            k0, k1 = 1 - t, t
        else:
            th = math.acos(max(-1.0, min(1.0, d))); s = math.sin(th)
            k0, k1 = math.sin((1 - t) * th) / s, math.sin(t * th) / s
        x, y, z, w = ax * k0 + bx * k1, ay * k0 + by * k1, az * k0 + bz * k1, aw * k0 + bw * k1
        n = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
        self.x, self.y, self.z, self.w = x / n, y / n, z / n, w / n
        return self


class matrix(object):
    """4x4，行向量约定：点 p' = p·M（平移在第 4 行）。"""
    __slots__ = ("m",)

    def __init__(self, *a):
        if len(a) == 1 and isinstance(a[0], matrix):
            self.m = [r[:] for r in a[0].m]
        elif len(a) == 1 and isinstance(a[0], (tuple, list)) and len(a[0]) == 16:
            a = a[0]
            self.m = [list(map(float, a[i * 4:i * 4 + 4])) for i in range(4)]
        elif len(a) == 16:
            self.m = [list(map(float, a[i * 4:i * 4 + 4])) for i in range(4)]
        else:
            self.m = [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]
    def __getattr__(self, n): _miss("matrix", n)
    def __repr__(self): return "matrix(%s)" % self.m

    def __mul__(self, o):
        if isinstance(o, matrix):
            r = matrix()
            r.m = [[sum(self.m[i][k] * o.m[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
            return r
        return NotImplemented

    def transform_coord(self, v):
        m = self.m
        return vector(v.x * m[0][0] + v.y * m[1][0] + v.z * m[2][0] + m[3][0],
                      v.x * m[0][1] + v.y * m[1][1] + v.z * m[2][1] + m[3][1],
                      v.x * m[0][2] + v.y * m[1][2] + v.z * m[2][2] + m[3][2])
    def transform_normal(self, v):
        m = self.m
        return vector(v.x * m[0][0] + v.y * m[1][0] + v.z * m[2][0],
                      v.x * m[0][1] + v.y * m[1][1] + v.z * m[2][1],
                      v.x * m[0][2] + v.y * m[1][2] + v.z * m[2][2])
    mulvec3x4 = transform_coord

    @property
    def translation(self): return vector(self.m[3][0], self.m[3][1], self.m[3][2])
    @translation.setter
    def translation(self, v): self.m[3][0], self.m[3][1], self.m[3][2] = v.x, v.y, v.z
    @property
    def right(self): return vector(*self.m[0][:3])
    @property
    def up(self): return vector(*self.m[1][:3])
    @property
    def forward(self): return vector(*self.m[2][:3])

    def set_all(self, *a):
        if len(a) == 16: self.m = [list(map(float, a[i * 4:i * 4 + 4])) for i in range(4)]
    @staticmethod
    def make_rotation_y(ang):
        c, s = math.cos(ang), math.sin(ang)
        r = matrix()
        r.m = [[c, 0, -s, 0], [0, 1, 0, 0], [s, 0, c, 0], [0, 0, 0, 1]]
        return r

    @staticmethod
    def make_orient(forward, up=None):
        f = vector(forward).normalized(); u = vector(up) if up is not None else vector(0, 1, 0)
        rt = u.cross(f).normalized(); u = f.cross(rt)
        r = matrix()
        r.m = [[rt.x, rt.y, rt.z, 0], [u.x, u.y, u.z, 0], [f.x, f.y, f.z, 0], [0, 0, 0, 1]]
        return r
    @staticmethod
    def make_rotation(axis, ang): return rotation.from_axis_angle(axis, ang).to_matrix()
    @property
    def rotation(self):
        # NeoX：matrix.rotation 是去掉平移的旋转部分（仍是矩阵），四元数要再过 math3d.matrix_to_rotation
        r = matrix(self); r.m[3][0] = r.m[3][1] = r.m[3][2] = 0.0
        return r
    @property
    def yaw(self): return math.atan2(self.m[2][0], self.m[2][2])
    def inverse(self):
        # 只支持刚体变换
        r = matrix()
        for i in range(3):
            for j in range(3): r.m[i][j] = self.m[j][i]
        t = self.translation
        it = r.transform_normal(t)
        r.m[3][0], r.m[3][1], r.m[3][2] = -it.x, -it.y, -it.z
        return r


Matrix = matrix


def matrix_to_rotation(m):
    """与 rotation.to_matrix 互逆（行向量约定）。"""
    if isinstance(m, rotation):
        return rotation(m)
    a = m.m
    tr = a[0][0] + a[1][1] + a[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        return rotation((a[1][2] - a[2][1]) / s, (a[2][0] - a[0][2]) / s, (a[0][1] - a[1][0]) / s, 0.25 * s)
    if a[0][0] > a[1][1] and a[0][0] > a[2][2]:
        s = math.sqrt(1.0 + a[0][0] - a[1][1] - a[2][2]) * 2
        return rotation(0.25 * s, (a[0][1] + a[1][0]) / s, (a[0][2] + a[2][0]) / s, (a[1][2] - a[2][1]) / s)
    if a[1][1] > a[2][2]:
        s = math.sqrt(1.0 + a[1][1] - a[0][0] - a[2][2]) * 2
        return rotation((a[0][1] + a[1][0]) / s, 0.25 * s, (a[1][2] + a[2][1]) / s, (a[2][0] - a[0][2]) / s)
    s = math.sqrt(1.0 + a[2][2] - a[0][0] - a[1][1]) * 2
    return rotation((a[0][2] + a[2][0]) / s, (a[1][2] + a[2][1]) / s, 0.25 * s, (a[0][1] - a[1][0]) / s)


def rotation_to_matrix(q):
    return q.to_matrix()


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    MISSING[("math3d", name)] = MISSING.get(("math3d", name), 0) + 1
    import simenv
    return simenv.Stub("math3d." + name)
