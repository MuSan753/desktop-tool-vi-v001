"""参数化 3D 桌宠：小星芽。

参考形象：白色治愈系小团子，蓝色渐变垂耳，头顶星芽触角（会随心情变），
星形尾巴，大大的星空眼。整体是一个软软的团子，脸直接长在身体上。

Pose 驱动一切：表情、耳朵、眼睛、触角、星星尾巴都是参数——
所以加表情只是改数值，不用画任何新素材。

坐标系：y 向上，z 朝镜头。身体中心大约在 (0, 0.8, 0)。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .mesh import ellipsoid, part_from, transform, tube
from .raster import Part, rotation_xyz

# ---- 调色：白团子 + 长春花蓝 ----
BODY = (252, 250, 248)
BELLY = (255, 254, 252)
PERI = (152, 178, 238)        # 长春花蓝（耳朵/斑纹）
PERI_LIGHT = (190, 210, 246)
IRIS_TOP = (74, 108, 226)     # 眼睛渐变：上蓝
IRIS_BOTTOM = (156, 104, 210)  # 下紫
EYE_WHITE = (250, 252, 255)
PUPIL = (46, 42, 74)
HIGHLIGHT = (255, 255, 255)
NOSE = (232, 170, 184)
MOUTH = (152, 138, 168)
BLUSH = (248, 178, 192)
STEM = (146, 198, 158)        # 触角茎叶
STAR = (250, 230, 176)        # 奶油星星
PAW = (253, 251, 249)

BODY_CENTER = np.array([0.0, 0.80, 0.0], dtype=np.float32)
FACE_PIVOT = np.array([0.0, 0.85, 0.15], dtype=np.float32)

_DROOP = np.array([0.57, -0.82])   # 耳朵自然下垂方向（右耳）
_PERK = np.array([0.45, 0.89])     # 竖起方向


@dataclass
class Pose:
    """一帧的姿态 + 表情。字段与旧版兼容（brow 在这版不使用）。"""

    # 身体
    breath: float = 0.0
    squat: float = 0.0
    hop: float = 0.0
    bob: float = 0.0
    lean: float = 0.0
    body_yaw: float = 0.0
    # 脸部组（脸长在团子上，没有独立头）
    head_yaw: float = 0.0
    head_pitch: float = 0.0
    head_roll: float = 0.0
    # 五官
    ear: tuple[float, float] = (0.0, 0.0)     # 正=竖起，负=耷拉
    eye_open: tuple[float, float] = (1.0, 1.0)
    pupil: float = 1.0
    brow: tuple[float, float] = (0.0, 0.0)    # 保留兼容，小星芽没有眉毛
    mouth: str = "omega"
    blush: float = 0.4
    # 四肢 / 尾巴 / 触角
    paw: tuple[float, float] = (0.0, 0.0)
    paw_lift: tuple[float, float] = (0.0, 0.0)
    tail: tuple[float, float, float] = (0.0, 0.0, 0.0)
    extras: tuple[str, ...] = field(default_factory=tuple)
    camera_yaw: float = 0.0


# ---------- 嘴型 ----------
def _mouth_curves(kind: str) -> list[list[tuple[float, float, float]]]:
    if kind == "smile":
        return [[(-0.10, 0.015, 0.0), (0.0, -0.035, 0.004), (0.10, 0.015, 0.0)]]
    if kind == "omega":
        return [
            [(-0.13, 0.02, 0.0), (-0.085, -0.025, 0.004), (-0.04, 0.005, 0.005)],
            [(0.04, 0.005, 0.005), (0.085, -0.025, 0.004), (0.13, 0.02, 0.0)],
        ]
    if kind == "flat":
        return [[(-0.07, 0.0, 0.0), (0.0, -0.004, 0.002), (0.07, 0.0, 0.0)]]
    if kind == "sad":
        return [[(-0.09, -0.025, 0.0), (0.0, 0.02, 0.004), (0.09, -0.025, 0.0)]]
    if kind in ("open", "o"):
        r = 0.09 if kind == "open" else 0.055
        angles = np.linspace(0, 2 * np.pi, 16, endpoint=False)
        return [[(np.cos(a) * r, np.sin(a) * r * 0.8, 0.0) for a in angles]]
    if kind == "wave":
        return [[(-0.11, 0.0, 0.0), (-0.04, -0.035, 0.003), (0.04, 0.025, 0.003), (0.11, 0.0, 0.0)]]
    return [[(-0.07, 0.0, 0.0), (0.07, 0.0, 0.0)]]


# ---------- 渐变工具 ----------
def _gradient_vcolors(verts: np.ndarray, axis: int, top, bottom, power: float = 1.0) -> np.ndarray:
    """沿某一轴做逐顶点颜色渐变（模型局部坐标，变换前调用）。"""
    lo, hi = verts[:, axis].min(), verts[:, axis].max()
    t = (verts[:, axis] - lo) / max(1e-5, hi - lo)
    t = np.clip(t, 0.0, 1.0) ** power
    top = np.asarray(top, dtype=np.float32) / 255.0
    bottom = np.asarray(bottom, dtype=np.float32) / 255.0
    return (t[..., None] * top + (1 - t)[..., None] * bottom).astype(np.float32)


def _puff_star(center, r_core: float, r_pet: float, color, in_plane="xy") -> list:
    """毛茸茸的星星：中心球 + 5 颗花瓣球。尾巴和头顶的星都用它。"""
    parts = []
    cx, cy, cz = center
    core_v, core_f = ellipsoid(center, (r_core, r_core, r_core * 0.7))
    parts.append((core_v, core_f, color, 0.4, False, None))
    for i in range(5):
        a = np.pi / 2 + i * 2 * np.pi / 5
        dx, dy = np.cos(a), np.sin(a)
        if in_plane == "xy":
            pos = (cx + dx * r_core * 1.5, cy + dy * r_core * 1.5, cz)
            radii = (r_pet, r_pet, r_pet * 0.6)
        else:  # yz 平面（朝后的尾巴从侧面看）
            pos = (cx, cy + dy * r_core * 1.5, cz + dx * r_core * 1.5)
            radii = (r_pet * 0.6, r_pet, r_pet)
        v, f = ellipsoid(pos, radii)
        parts.append((v, f, color, 0.4, False, None))
    return parts


def _ear_parts(pose: Pose, side: int, group: list) -> None:
    """长垂耳：白色根部渐变到蓝色尖端，情绪驱动耷拉/竖起。"""
    value = pose.ear[0] if side < 0 else pose.ear[1]
    if value >= 0:
        t = value * 0.6
        dir2 = _DROOP * (1 - t) + _PERK * t
    else:
        droop = _DROOP + np.array([0.0, -0.25 * (-value)])
        dir2 = droop / np.linalg.norm(droop)
    dir2 = dir2 / np.linalg.norm(dir2)
    dir_x = side * dir2[0]

    base = np.array([0.50 * side, 1.28, -0.02], dtype=np.float32)
    length = 0.50
    center = base + np.array([dir_x * length * 0.78, dir2[1] * length * 0.78, 0.0], dtype=np.float32)

    theta = np.arctan2(-dir_x, dir2[1])  # 把 +Y 转到 dir 方向
    rot = rotation_xyz(0.0, 0.0, theta)

    v, f = ellipsoid((0, 0, 0), (0.17, 0.62, 0.15), rot=rot)
    vc = _gradient_vcolors(v, 1, BODY, PERI, power=1.8)
    v = transform(v, trans=center)
    group.append((v, f, BODY, 0.0, True, vc))

    # 耳尖小亮点
    tip = center + np.array([dir_x * length * 0.42, dir2[1] * length * 0.42, 0.0], dtype=np.float32)
    v, f = ellipsoid(tuple(tip), (0.09, 0.09, 0.07))
    group.append((v, f, PERI_LIGHT, 0.2, True, None))


def _eye_parts(pose: Pose, side: int, group: list) -> None:
    """星空大眼：白眼球 + 蓝紫渐变虹膜 + 深瞳 + 双高光。"""
    open_k = pose.eye_open[0] if side < 0 else pose.eye_open[1]
    x = 0.42 * side
    y = 0.98
    z = 0.70
    squash = max(0.05, open_k)

    v, f = ellipsoid((x, y, z), (0.30, 0.345 * squash, 0.15))
    group.append((v, f, EYE_WHITE, 0.3, True, None))

    iris_scale = pose.pupil / max(0.35, open_k) ** 0.3
    v, f = ellipsoid((x, y, z + 0.09), (0.265 * iris_scale, 0.30 * squash, 0.10))
    vc = _gradient_vcolors(v, 1, IRIS_TOP, IRIS_BOTTOM, power=1.1)
    group.append((v, f, IRIS_TOP, 0.55, False, vc))

    v, f = ellipsoid((x, y, z + 0.16), (0.13 * iris_scale, 0.17 * squash, 0.055))
    group.append((v, f, PUPIL, 0.0, False, None))

    # 主高光（左上）+ 次高光（右下），星空感
    v, f = ellipsoid((x - 0.09, y + 0.115, z + 0.175), (0.085, 0.085, 0.04))
    group.append((v, f, HIGHLIGHT, 1.0, False, None))
    v, f = ellipsoid((x + 0.10, y - 0.10, z + 0.175), (0.04, 0.04, 0.025))
    group.append((v, f, HIGHLIGHT, 1.0, False, None))


def build_cat(pose: Pose) -> list[Part]:
    """按姿态构造所有部件。"""
    body_rot = rotation_xyz(pose.lean, pose.body_yaw, 0.0)
    body_trans = np.array([0.0, pose.hop + pose.bob - pose.squat, 0.0], dtype=np.float32)
    breath_scale = (1.0 + pose.breath * 0.012, 1.0 + pose.breath * 0.02, 1.0 + pose.breath * 0.012)

    face_rot = rotation_xyz(pose.head_pitch, pose.head_yaw, pose.head_roll)

    # ---------- 身体组 ----------
    body_group: list = []

    v, f = ellipsoid(BODY_CENTER, (1.00, 0.80, 0.84))
    body_group.append((v, f, BODY, 0.0, True, None))

    v, f = ellipsoid((0.0, 0.60, 0.36), (0.52, 0.44, 0.42))
    body_group.append((v, f, BELLY, 0.0, True, None))

    # 前爪（团子底下露出的小爪爪）
    paw_specs = ((pose.paw[0], pose.paw_lift[0]), (pose.paw[1], pose.paw_lift[1]))
    for side, (off, lift) in zip((-1, 1), paw_specs):
        v, f = ellipsoid((0.30 * side + off * 0.05, 0.16 + lift, 0.60 + off * 0.4),
                         (0.17, 0.11, 0.15))
        body_group.append((v, f, PAW, 0.0, True, None))

    # 背部星形斑纹（转身/侧视可见）
    tail_yaw = pose.tail[0] + pose.tail[1] * 0.5
    star_center = (tail_yaw * 0.05, 0.86, -0.74)
    for item in _puff_star(star_center, 0.19, 0.13, STAR, in_plane="yz"):
        body_group.append(item)

    body_parts = []
    for item in body_group:
        v, f, color, gloss, toon, vc = item
        tv = transform(v, rot=body_rot, trans=body_trans, scale=breath_scale, pivot=BODY_CENTER)
        body_parts.append(part_from(tv, f, color, gloss, toon, vcolors=vc))

    # ---------- 脸部组（随"头"转动） ----------
    face_group: list = []

    # 耳朵
    for side in (-1, 1):
        _ear_parts(pose, side, face_group)

    # 额头小蓝钻
    v, f = ellipsoid((0.0, 1.14, 0.64), (0.18, 0.18, 0.06), rot=rotation_xyz(0, 0, np.pi / 4))
    face_group.append((v, f, PERI, 0.3, True, None))

    # 触角：茎 + 两片叶 + 星星花
    stem_top = (0.03 + pose.tail[2] * 0.02, 1.88, -0.05)
    v, f = tube([(0.0, 1.54, -0.03), (0.02, 1.72, -0.04), stem_top], [0.045, 0.035, 0.028], segments=8)
    face_group.append((v, f, STEM, 0.0, True, None))
    for side in (-1, 1):
        v, f = ellipsoid((stem_top[0] + 0.09 * side, stem_top[1] - 0.04, stem_top[2]),
                         (0.15, 0.06, 0.035), rot=rotation_xyz(0, 0, side * 0.6))
        face_group.append((v, f, STEM, 0.0, True, None))
    for item in _puff_star((stem_top[0], stem_top[1] + 0.13, stem_top[2]), 0.075, 0.055, STAR):
        face_group.append(item)

    # 眼睛
    for side in (-1, 1):
        _eye_parts(pose, side, face_group)

    # 鼻子 / 嘴
    v, f = ellipsoid((0.0, 0.70, 0.79), (0.065, 0.048, 0.05))
    face_group.append((v, f, NOSE, 0.2, False, None))

    for curve in _mouth_curves(pose.mouth):
        pts = [(p[0] * 1.1, 0.545 + p[1] * 1.1, 0.785 + p[2]) for p in curve]
        v, f = tube(pts, [0.028] * len(pts), segments=8)
        face_group.append((v, f, MOUTH, 0.0, True, None))

    # 腮红
    if pose.blush > 0.02:
        for side in (-1, 1):
            v, f = ellipsoid((0.72 * side, 0.64, 0.52),
                             (0.20 * pose.blush + 0.05, 0.12 * pose.blush + 0.035, 0.05))
            face_group.append((v, f, BLUSH, 0.0, True, None))

    face_parts = []
    face_shift = np.array([0.0, pose.hop + pose.bob - pose.squat * 0.5, 0.0], dtype=np.float32)
    for item in face_group:
        v, f, color, gloss, toon, vc = item
        tv = transform(v, rot=face_rot, trans=face_shift, pivot=FACE_PIVOT)
        face_parts.append(part_from(tv, f, color, gloss, toon, vcolors=vc))

    return body_parts + face_parts
