"""参数化 3D 小猫。

所有部位都是几何体，靠 Pose 控制姿态和表情——
所以"加一个表情"只是改几个数值，不需要新画任何素材。
这也是这套方案相对序列帧手绘最大的优势：表情数量几乎免费。

单位：身体半径约 0.8，y 轴向上，z 轴朝向镜头。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .mesh import cone, ellipsoid, part_from, transform, transform_normals, tube
from .raster import Part, rotation_xyz

# ---- 调色 ----
FUR = (250, 244, 236)
FUR_BELLY = (255, 253, 249)
FUR_DARK = (232, 222, 214)
EAR_IN = (244, 168, 180)
EYE_WHITE = (252, 252, 255)
IRIS = (84, 62, 112)
PUPIL = (46, 34, 58)
HIGHLIGHT = (255, 255, 255)
NOSE = (224, 132, 146)
MOUTH = (126, 96, 108)
BROW = (112, 92, 112)
BLUSH = (246, 152, 170)
PAW = (255, 250, 244)

HEAD_CENTER = np.array([0.0, 1.60, 0.03], dtype=np.float32)
NECK_PIVOT = np.array([0.0, 1.02, 0.0], dtype=np.float32)
BODY_CENTER = np.array([0.0, 0.60, 0.0], dtype=np.float32)


@dataclass
class Pose:
    """一帧的姿态 + 表情。"""

    # 身体
    breath: float = 0.0        # 呼吸幅度
    squat: float = 0.0         # 下蹲
    hop: float = 0.0           # 跳起
    bob: float = 0.0           # 行走起伏
    lean: float = 0.0          # 身体前倾（弧度）
    body_yaw: float = 0.0
    # 头
    head_yaw: float = 0.0
    head_pitch: float = 0.0
    head_roll: float = 0.0
    # 五官
    ear: tuple[float, float] = (0.0, 0.0)     # 左右耳向外/向后（弧度）
    eye_open: tuple[float, float] = (1.0, 1.0)
    pupil: float = 1.0
    brow: tuple[float, float] = (0.0, 0.0)    # 眉毛角度，正=皱眉
    mouth: str = "omega"
    blush: float = 0.35
    # 四肢 / 尾巴
    paw: tuple[float, float] = (0.0, 0.0)     # 前后爪前后位移
    paw_lift: tuple[float, float] = (0.0, 0.0)
    tail: tuple[float, float, float] = (0.0, 0.0, 0.0)  # 尾巴三段摆动
    # 2D 叠加表情
    extras: tuple[str, ...] = field(default_factory=tuple)
    camera_yaw: float = 0.0


# ---------- 局部零件 ----------
def _mouth_curves(kind: str) -> list[list[tuple[float, float, float]]]:
    """返回若干条 3D 曲线（嘴部局部坐标，稍后会贴到脸前）。"""
    if kind == "smile":
        return [[(-0.16, 0.02, 0.0), (-0.06, -0.05, 0.005), (0.06, -0.05, 0.005), (0.16, 0.02, 0.0)]]
    if kind == "omega":
        return [
            [(-0.24, 0.03, 0.0), (-0.17, -0.04, 0.005), (-0.09, 0.01, 0.006)],
            [(0.09, 0.01, 0.006), (0.17, -0.04, 0.005), (0.24, 0.03, 0.0)],
        ]
    if kind == "flat":
        return [[(-0.12, 0.0, 0.0), (0.0, -0.005, 0.002), (0.12, 0.0, 0.0)]]
    if kind == "sad":
        return [[(-0.14, -0.04, 0.0), (0.0, 0.03, 0.005), (0.14, -0.04, 0.0)]]
    if kind in ("open", "o"):
        r = 0.13 if kind == "open" else 0.08
        angles = np.linspace(0, 2 * np.pi, 18, endpoint=False)
        return [[(np.cos(a) * r, np.sin(a) * r * 0.85, 0.0) for a in angles]]
    if kind == "wave":
        return [[(-0.18, 0.0, 0.0), (-0.06, -0.06, 0.004), (0.06, 0.04, 0.004), (0.18, 0.0, 0.0)]]
    return [[(-0.12, 0.0, 0.0), (0.12, 0.0, 0.0)]]


def _eye_parts(pose: Pose, side: int, group: list) -> None:
    """一只眼睛：眼白 + 虹膜 + 高光；闭眼时整体压扁。"""
    open_k = pose.eye_open[0] if side < 0 else pose.eye_open[1]
    x = 0.30 * side
    y = 1.70
    z = 0.66
    squash = max(0.05, open_k)

    white_v, white_f = ellipsoid((x, y, z), (0.21, 0.23 * squash, 0.17))
    group.append((white_v, white_f, EYE_WHITE, 0.35, True))

    iris_r = 0.175 * pose.pupil / max(0.35, open_k) ** 0.35
    iris_v, iris_f = ellipsoid((x, y, z + 0.13), (iris_r, iris_r * max(0.08, squash), 0.10))
    group.append((iris_v, iris_f, IRIS, 0.55, False))

    pupil_v, pupil_f = ellipsoid((x, y, z + 0.18), (iris_r * 0.42, iris_r * 0.48 * max(0.08, squash), 0.05))
    group.append((pupil_v, pupil_f, PUPIL, 0.0, False))

    hl_v, hl_f = ellipsoid((x + 0.08, y + 0.085, z + 0.22), (0.065, 0.065, 0.03))
    group.append((hl_v, hl_f, HIGHLIGHT, 1.0, False))


def _brow_parts(pose: Pose, side: int, group: list) -> None:
    angle = pose.brow[0] if side < 0 else pose.brow[1]
    if abs(angle) < 1e-4:
        return
    x = 0.34 * side
    y = 1.94
    z = 0.58
    rot = rotation_xyz(0.0, 0.0, angle * side)
    v, f = ellipsoid((x, y, z), (0.17, 0.032, 0.03), rot=rot)
    group.append((v, f, BROW, 0.0, True))


def build_cat(pose: Pose) -> list[Part]:
    """按姿态构造所有部件（世界坐标）。"""
    body_rot = rotation_xyz(pose.lean, pose.body_yaw, 0.0)
    body_trans = np.array([0.0, pose.hop + pose.bob - pose.squat, 0.0], dtype=np.float32)
    breath_scale = (1.0 + pose.breath * 0.012, 1.0 + pose.breath * 0.02, 1.0 + pose.breath * 0.012)

    head_rot = rotation_xyz(pose.head_pitch, pose.head_yaw, pose.head_roll)

    # ---------- 身体组 ----------
    body_group: list = []

    v, f = ellipsoid(BODY_CENTER, (0.78, 0.62, 0.68))
    body_group.append((v, f, FUR, 0.0, True))

    v, f = ellipsoid((0.0, 0.52, 0.34), (0.44, 0.40, 0.36))
    body_group.append((v, f, FUR_BELLY, 0.0, True))

    # 后腿轮廓（让坐姿更像猫而不是海豹）
    for side in (-1, 1):
        v, f = ellipsoid((0.52 * side, 0.30, 0.10), (0.30, 0.36, 0.36))
        body_group.append((v, f, FUR, 0.0, True))

    # 爪子
    paw_specs = ((pose.paw[0], pose.paw_lift[0]), (pose.paw[1], pose.paw_lift[1]))
    for side, (off, lift) in zip((-1, 1), paw_specs):
        v, f = ellipsoid((0.36 * side + off * 0.06, 0.10 + lift, 0.54 + off * 0.5),
                         (0.26, 0.18, 0.32))
        body_group.append((v, f, PAW, 0.0, True))

    # 尾巴
    sway_a, sway_b, sway_c = pose.tail
    base = (0.0, 0.52, -0.52)
    pts = [
        base,
        (0.05 + sway_a * 0.10, 0.72 + sway_a * 0.12, -0.90),
        (0.10 + sway_b * 0.16, 1.04 + sway_b * 0.10, -0.90),
        (0.02 + sway_c * 0.22, 1.36 + sway_c * 0.08, -0.64),
    ]
    v, f = tube(pts, [0.15, 0.12, 0.09, 0.07], segments=12)
    body_group.append((v, f, FUR_DARK, 0.0, True))

    body_parts = []
    for v, f, color, gloss, toon in body_group:
        tv = transform(v, rot=body_rot, trans=body_trans, scale=breath_scale, pivot=BODY_CENTER)
        body_parts.append(part_from(tv, f, color, gloss, toon))

    # ---------- 头部组 ----------
    head_group: list = []

    v, f = ellipsoid(HEAD_CENTER, (0.86, 0.75, 0.80))
    head_group.append((v, f, FUR, 0.0, True))

    # 耳朵：圆锥 + 锥尖小球倒圆角，太尖会像恶魔角
    for side in (-1, 1):
        ear_value = pose.ear[0] if side < 0 else pose.ear[1]
        outward = 0.30 - ear_value * 0.30          # 正值更竖直，负值更趴
        back = -0.10 - min(0.0, ear_value) * 0.55  # 负值往后压
        tilt_z = -side * outward
        rot = rotation_xyz(back, 0.0, tilt_z)
        base = (0.37 * side, 2.04, -0.02)
        height = 0.44
        v, f = cone(base, 0.37, height, rot=rot, flatten=(1.0, 1.0, 0.55), cap=False)
        head_group.append((v, f, FUR, 0.0, True))
        # 锥尖圆角
        tip_local = np.array([0.0, height, 0.0], dtype=np.float32)
        tip = transform(tip_local[None, :], rot=rot, trans=base)[0]
        v, f = ellipsoid(tuple(tip), (0.075, 0.09, 0.055))
        head_group.append((v, f, FUR, 0.0, True))
        inner_rot = rotation_xyz(back, 0.0, tilt_z)
        v, f = cone((0.38 * side, 2.09, 0.06), 0.20, 0.28, rot=inner_rot,
                    flatten=(1.0, 1.0, 0.5), cap=False)
        head_group.append((v, f, EAR_IN, 0.0, True))

    # 口鼻
    v, f = ellipsoid((0.0, 1.40, 0.60), (0.38, 0.27, 0.26))
    head_group.append((v, f, FUR_BELLY, 0.0, True))

    v, f = ellipsoid((0.0, 1.475, 0.86), (0.105, 0.08, 0.08))
    head_group.append((v, f, NOSE, 0.3, False))

    # 嘴（贴在口鼻前端，z 太小会被埋进模型里）
    for curve in _mouth_curves(pose.mouth):
        pts = [(p[0] * 1.2, 1.33 + p[1] * 1.15, 0.87 + p[2]) for p in curve]
        v, f = tube(pts, [0.04] * len(pts), segments=8)
        head_group.append((v, f, MOUTH, 0.0, True))

    # 胡须（细管，猫感全靠它）
    for side in (-1, 1):
        for dy, dz in ((0.03, 0.02), (-0.01, 0.03), (-0.05, 0.01)):
            pts = [
                (0.26 * side, 1.38 + dy * 0.5, 0.70 + dz),
                (0.52 * side, 1.40 + dy, 0.62),
                (0.78 * side, 1.38 + dy * 1.4, 0.42),
            ]
            v, f = tube(pts, [0.012, 0.010, 0.006], segments=5)
            head_group.append((v, f, (150, 130, 140), 0.0, True))

    # 腮红
    if pose.blush > 0.02:
        for side in (-1, 1):
            v, f = ellipsoid((0.60 * side, 1.44, 0.55),
                             (0.20 * pose.blush + 0.06, 0.13 * pose.blush + 0.04, 0.06))
            head_group.append((v, f, BLUSH, 0.0, True))

    # 眼睛 / 眉毛
    for side in (-1, 1):
        _eye_parts(pose, side, head_group)
        _brow_parts(pose, side, head_group)

    head_parts = []
    head_shift = np.array([0.0, pose.hop + pose.bob - pose.squat * 0.4, 0.0], dtype=np.float32)
    for v, f, color, gloss, toon in head_group:
        tv = transform(v, rot=head_rot, trans=head_shift, pivot=NECK_PIVOT)
        head_parts.append(part_from(tv, f, color, gloss, toon))

    return body_parts + head_parts
