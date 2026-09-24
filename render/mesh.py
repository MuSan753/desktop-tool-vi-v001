"""程序化几何图元 + 顶点法线计算。

全部人来 basically 三种：
1. 椭球（身体、头、爪子、腮红——任何圆润的东西）
2. 圆锥（耳朵、眉毛）
3. 扫掠管（尾巴、嘴——沿一条空间曲线扫圆形截面）
"""
from __future__ import annotations

import numpy as np

from .raster import Part


def compute_normals(verts: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """按相邻面法线求平均得到平滑法线（圆润感靠它）。"""
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    face_n = np.cross(v1 - v0, v2 - v0)
    normals = np.zeros_like(verts, dtype=np.float32)
    np.add.at(normals, faces[:, 0], face_n)
    np.add.at(normals, faces[:, 1], face_n)
    np.add.at(normals, faces[:, 2], face_n)
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    return normals / np.where(lengths > 1e-8, lengths, 1.0)


def transform(
    verts: np.ndarray,
    rot=None,
    trans=(0.0, 0.0, 0.0),
    scale=(1.0, 1.0, 1.0),
    pivot=(0.0, 0.0, 0.0),
) -> np.ndarray:
    """绕 pivot 旋转缩放，再平移。"""
    out = np.asarray(verts, dtype=np.float32).copy()
    pivot = np.asarray(pivot, dtype=np.float32)
    if np.any(pivot):
        out = out - pivot
    if scale is not None and not np.allclose(scale, 1.0):
        out = out * np.asarray(scale, dtype=np.float32)
    if rot is not None:
        out = out @ np.asarray(rot, dtype=np.float32).T
    if np.any(pivot):
        out = out + pivot
    return out + np.asarray(trans, dtype=np.float32)


def transform_normals(normals: np.ndarray, rot=None, scale=(1.0, 1.0, 1.0)) -> np.ndarray:
    out = np.asarray(normals, dtype=np.float32).copy()
    if scale is not None and not np.allclose(scale, 1.0):
        s = np.asarray(scale, dtype=np.float32)
        out = out / np.where(np.abs(s) > 1e-6, s, 1.0)
    if rot is not None:
        out = out @ np.asarray(rot, dtype=np.float32).T
    lengths = np.linalg.norm(out, axis=1, keepdims=True)
    return out / np.where(lengths > 1e-8, lengths, 1.0)


# ---------- 图元 ----------
def ellipsoid(
    center=(0.0, 0.0, 0.0),
    radii=(1.0, 1.0, 1.0),
    rings: int = 18,
    slices: int = 26,
    rot=None,
    squash=(1.0, 1.0, 1.0),
) -> tuple[np.ndarray, np.ndarray]:
    v_theta = np.linspace(0, np.pi, rings + 1)
    v_phi = np.linspace(0, 2 * np.pi, slices, endpoint=False)
    theta, phi = np.meshgrid(v_theta, v_phi, indexing="ij")

    x = np.sin(theta) * np.cos(phi)
    y = np.cos(theta)
    z = np.sin(theta) * np.sin(phi)
    base = np.stack([x, y, z], axis=-1).reshape(-1, 3).astype(np.float32)

    faces = []
    for i in range(rings):
        for j in range(slices):
            a = i * slices + j
            b = i * slices + (j + 1) % slices
            c = (i + 1) * slices + j
            d = (i + 1) * slices + (j + 1) % slices
            if i != 0:
                faces.append([a, c, d])
            if i != rings - 1:
                faces.append([a, d, b])
    faces = np.array(faces, dtype=np.int32)

    verts = transform(base, rot=rot, trans=center, scale=(
        radii[0] * squash[0], radii[1] * squash[1], radii[2] * squash[2]))
    return verts, faces


def cone(
    base_center=(0.0, 0.0, 0.0),
    radius: float = 1.0,
    height: float = 1.0,
    slices: int = 18,
    rot=None,
    flatten=(1.0, 1.0, 1.0),
    cap: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """底面在局部 XZ 平面、锥尖朝 +Y 的圆锥。cap=False 时不封底（嵌进别的几何体时避免穿模）。"""
    angles = np.linspace(0, 2 * np.pi, slices, endpoint=False)
    ring = np.stack([np.cos(angles), np.zeros_like(angles), np.sin(angles)], axis=-1)
    ring[:, 0] *= flatten[0]
    ring[:, 2] *= flatten[2]
    ring = ring * radius

    apex = np.array([[0.0, height * flatten[1], 0.0]], dtype=np.float32)
    verts = np.concatenate([ring, apex], axis=0).astype(np.float32)
    apex_i = slices

    faces = []
    for j in range(slices):
        a = j
        b = (j + 1) % slices
        faces.append([a, apex_i, b])
    if cap:
        center = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
        verts = np.concatenate([verts, center], axis=0)
        center_i = slices + 1
        for j in range(slices):
            faces.append([center_i, (j + 1) % slices, j])
    verts = transform(verts, rot=rot, trans=base_center)
    return verts, np.array(faces, dtype=np.int32)


def tube(
    points: list[tuple[float, float, float]],
    radii: list[float],
    segments: int = 14,
    closed: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """沿折线扫掠圆截面；用固定上向量推算截面姿态，够用了。"""
    P = np.asarray(points, dtype=np.float32)
    n = len(P)
    angles = np.linspace(0, 2 * np.pi, segments, endpoint=False)

    frames = []
    for i in range(n):
        if i == 0:
            tangent = P[1] - P[0]
        elif i == n - 1:
            tangent = P[-1] - P[-2]
        else:
            tangent = P[i + 1] - P[i - 1]
        t = tangent / (np.linalg.norm(tangent) + 1e-8)
        up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        side = np.cross(t, up)
        if np.linalg.norm(side) < 1e-5:
            side = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        side = side / np.linalg.norm(side)
        up2 = np.cross(side, t)
        frames.append((side, up2))

    verts = []
    for i in range(n):
        side, up2 = frames[i]
        for a in angles:
            verts.append(P[i] + radii[i] * (np.cos(a) * side + np.sin(a) * up2))
    verts = np.asarray(verts, dtype=np.float32)

    faces = []
    for i in range(n - 1):
        for j in range(segments):
            a = i * segments + j
            b = i * segments + (j + 1) % segments
            c = (i + 1) * segments + j
            d = (i + 1) * segments + (j + 1) % segments
            faces.append([a, c, d])
            faces.append([a, d, b])
    return verts, np.array(faces, dtype=np.int32)


def part_from(verts, faces, color, gloss: float = 0.0, toon: bool = True) -> Part:
    color = np.asarray(color, dtype=np.float32)
    if color.max() > 1.0:
        color = color / 255.0
    return Part(
        verts=np.asarray(verts, dtype=np.float32),
        faces=np.asarray(faces, dtype=np.int32),
        normals=compute_normals(np.asarray(verts, dtype=np.float32), faces),
        color=color.astype(np.float32),
        gloss=gloss,
        toon=toon,
    )


def merge(parts: list[Part]) -> Part:
    verts_list, faces_list, offset = [], [], 0
    colors = []
    for p in parts:
        verts_list.append(p.verts)
        faces_list.append(p.faces + offset)
        offset += len(p.verts)
        colors.append(p.color)
    verts = np.concatenate(verts_list, axis=0)
    faces = np.concatenate(faces_list, axis=0)
    return part_from(verts, faces, colors[0], gloss=parts[0].gloss)
