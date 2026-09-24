"""软件 3D 渲染器：三角面光栅化 + z-buffer + 卡通着色 + 描边。

为什么不用 Qt 现成的 3D：
- QtQuick3D 的 QML 插件没打进 PySide6 wheel（实测 qquick3dplugin not found）
- Qt3D 虽有 .pyd，但 Python 侧几乎没导出类（Qt3DExtras 里只有 QIntList）
- QtWebEngine 没装，走不了网页渲染 Live2D

所以这里的做法是：离线把参数化模型渲染成 PNG 序列帧，
运行时照旧播序列帧——既拿到了真正的三维光照和转视角，
又不依赖 GPU、不引入任何外部依赖。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n else v


def rotation_xyz(rx: float, ry: float, rz: float) -> np.ndarray:
    """XYZ 顺序的旋转矩阵（弧度）。"""
    cx, sx = np.cos(rx), np.sin(rx)
    cy, sy = np.cos(ry), np.sin(ry)
    cz, sz = np.cos(rz), np.sin(rz)
    rxm = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    rym = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rzm = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return rzm @ rym @ rxm


@dataclass
class Part:
    """一块几何体，顶点已经在世界坐标里。"""

    verts: np.ndarray      # (N, 3)
    faces: np.ndarray      # (M, 3)
    normals: np.ndarray    # (N, 3) 平滑法线
    color: np.ndarray      # (3,) 0~1 的基础色
    gloss: float = 0.0     # 高光强度
    toon: bool = True      # False 则走连续光照（用于金属感/暗部）
    vcolors: np.ndarray | None = None  # (N, 3) 逐顶点色，有则优先（渐变用）


class Renderer:
    def __init__(
        self,
        width: int,
        height: int,
        supersample: int = 3,
        fov: float = 26.0,
        camera_yaw: float = 0.0,
        camera_pitch: float = 0.08,
        distance: float = 8.0,
        target=(0.0, 0.9, 0.0),
    ) -> None:
        self.ss = supersample
        self.out_w, self.out_h = width, height
        self.W, self.H = width * supersample, height * supersample
        self.fov = np.deg2rad(fov)
        self.camera_yaw = camera_yaw
        self.camera_pitch = camera_pitch
        self.distance = distance
        self.target = np.array(target, dtype=np.float32)

        self.key_dir = normalize(np.array([-0.55, 0.72, 0.62], dtype=np.float32))
        self.fill_dir = normalize(np.array([0.75, 0.15, 0.45], dtype=np.float32))
        self.key_color = np.array([1.0, 0.975, 0.94], dtype=np.float32)
        self.key_intensity = 0.5
        self.fill_intensity = 0.14
        self.ambient = 0.34
        self.rim_color = np.array([1.0, 0.94, 0.96], dtype=np.float32)
        self.rim_strength = 0.4
        self.outline_px = 2  # 超采样坐标下的描边宽度

        self.color = np.zeros((self.H, self.W, 3), dtype=np.float32)
        self.depth = np.full((self.H, self.W), np.inf, dtype=np.float32)
        self.alpha = np.zeros((self.H, self.W), dtype=np.uint8)

    # ---------- 相机 ----------
    def _camera(self):
        eye = self.target + np.array(
            [
                self.distance * np.cos(self.camera_pitch) * np.sin(self.camera_yaw),
                self.distance * np.sin(self.camera_pitch),
                self.distance * np.cos(self.camera_pitch) * np.cos(self.camera_yaw),
            ],
            dtype=np.float32,
        )
        return eye

    def _basis(self):
        """相机的 (right, up, forward) 正交基。"""
        eye = self._camera()
        forward = normalize(self.target - eye)
        up_world = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        right = normalize(np.cross(forward, up_world))
        up = np.cross(right, forward)
        return eye, right, up, forward

    # ---------- 主入口 ----------
    def render(self, parts: list[Part]) -> np.ndarray:
        """返回 RGBA uint8 数组（已经是超采样尺寸）。"""
        self.color[:] = 0
        self.depth[:] = np.inf
        self.alpha[:] = 0

        eye, right, up, forward = self._basis()
        focal = (self.H / 2.0) / np.tan(self.fov / 2.0)
        cx, cy = self.W / 2.0, self.H / 2.0

        for part in parts:
            rel = part.verts - eye
            vx = rel @ right
            vy = rel @ up
            depth = rel @ forward          # 越大越远
            ok = depth > 0.05
            denom = np.where(ok, depth, 1e-3)
            sx = cx + focal * vx / denom
            sy = cy - focal * vy / denom
            screen = np.stack([sx, sy], axis=1)

            faces = part.faces
            vcolors = part.vcolors
            for idx in range(faces.shape[0]):
                a, b, c = faces[idx]
                if not (ok[a] and ok[b] and ok[c]):
                    continue
                ca = vcolors[a] if vcolors is not None else None
                cb = vcolors[b] if vcolors is not None else None
                cc = vcolors[c] if vcolors is not None else None
                self._triangle(
                    screen[a], screen[b], screen[c],
                    part.verts[a], part.verts[b], part.verts[c],
                    part.normals[a], part.normals[b], part.normals[c],
                    depth[a], depth[b], depth[c],
                    part, eye, ca, cb, cc,
                )
        return self._compose()

    # ---------- 单个三角面 ----------
    def _triangle(self, p0, p1, p2, w0, w1, w2, n0, n1, n2, d0, d1, d2, part, eye,
                  ca=None, cb=None, cc=None) -> None:
        xmin = int(np.floor(min(p0[0], p1[0], p2[0])))
        xmax = int(np.ceil(max(p0[0], p1[0], p2[0])))
        ymin = int(np.floor(min(p0[1], p1[1], p2[1])))
        ymax = int(np.ceil(max(p0[1], p1[1], p2[1])))
        if xmax < 0 or ymax < 0 or xmin >= self.W or ymin >= self.H:
            return
        xmin, ymin = max(0, xmin), max(0, ymin)
        xmax, ymax = min(self.W - 1, xmax), min(self.H - 1, ymax)
        if xmin > xmax or ymin > ymax:
            return

        xs = np.arange(xmin, xmax + 1, dtype=np.float32) + 0.5
        ys = np.arange(ymin, ymax + 1, dtype=np.float32) + 0.5
        PX, PY = np.meshgrid(xs, ys)

        def edge(ax, ay, bx, by):
            return (bx - ax) * (PY - ay) - (by - ay) * (PX - ax)

        e0 = edge(p1[0], p1[1], p2[0], p2[1])
        e1 = edge(p2[0], p2[1], p0[0], p0[1])
        e2 = edge(p0[0], p0[1], p1[0], p1[1])
        denom = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0])
        if abs(denom) < 1e-9:
            return

        l0, l1, l2 = e0 / denom, e1 / denom, e2 / denom
        inside = (l0 >= -1e-4) & (l1 >= -1e-4) & (l2 >= -1e-4)
        if not inside.any():
            return

        # 透视校正插值
        iw = l0 / d0 + l1 / d1 + l2 / d2
        iw_safe = np.where(np.abs(iw) > 1e-9, iw, 1e-9)
        inv_iw = 1.0 / iw_safe

        P = (
            np.expand_dims(l0 / d0, -1) * w0
            + np.expand_dims(l1 / d1, -1) * w1
            + np.expand_dims(l2 / d2, -1) * w2
        ) * inv_iw[..., None]
        N = (
            np.expand_dims(l0 / d0, -1) * n0
            + np.expand_dims(l1 / d1, -1) * n1
            + np.expand_dims(l2 / d2, -1) * n2
        ) * inv_iw[..., None]

        z = inv_iw  # 距离越远值越大

        sub_depth = self.depth[ymin:ymax + 1, xmin:xmax + 1]
        mask = inside & (z < sub_depth)
        if not mask.any():
            return

        n_len = np.linalg.norm(N, axis=-1, keepdims=True)
        N = N / np.where(n_len > 1e-6, n_len, 1.0)

        if ca is not None and cb is not None and cc is not None:
            C = (
                np.expand_dims(l0 / d0, -1) * ca
                + np.expand_dims(l1 / d1, -1) * cb
                + np.expand_dims(l2 / d2, -1) * cc
            ) * inv_iw[..., None]
        else:
            C = None

        rgb = self._shade(P, N, part, eye, C)

        target_color = self.color[ymin:ymax + 1, xmin:xmax + 1]
        np.copyto(target_color, rgb, where=mask[..., None])
        np.copyto(sub_depth, np.where(mask, z, sub_depth))
        target_alpha = self.alpha[ymin:ymax + 1, xmin:xmax + 1]
        np.copyto(target_alpha, np.where(mask, np.uint8(255), target_alpha))

    # ---------- 着色 ----------
    def _shade(self, P, N, part, eye, C=None) -> np.ndarray:
        V = eye - P
        v_len = np.linalg.norm(V, axis=-1, keepdims=True)
        V = V / np.where(v_len > 1e-6, v_len, 1.0)

        key = np.clip(N @ self.key_dir, 0.0, None)          # (h, w)
        fill = np.clip(N @ self.fill_dir, 0.0, None)        # (h, w)

        if part.toon:
            bands = np.select(
                [key > 0.62, key > 0.36, key > 0.16],
                [1.0, 0.82, 0.68],
                default=0.58,
            )
        else:
            bands = 0.45 + 0.55 * key

        light = (
            self.ambient
            + bands[..., None] * self.key_intensity * self.key_color
            + (0.35 + 0.65 * fill)[..., None] * self.fill_intensity
        )

        facing = np.clip(np.sum(N * V, axis=-1), 0.0, 1.0)  # (h, w)
        rim = (np.power(1.0 - facing, 2.6)[..., None]) * self.rim_strength * self.rim_color

        base = part.color if C is None else np.clip(C, 0.0, 1.0)
        out = base * light + rim

        if part.gloss > 0:
            L = self.key_dir
            Hv = L + V
            h_len = np.linalg.norm(Hv, axis=-1, keepdims=True)
            Hv = Hv / np.where(h_len > 1e-6, h_len, 1.0)
            spec = np.clip(np.sum(N * Hv, axis=-1), 0.0, None)[..., None]
            spec = np.where(spec > 0.955, 1.0, 0.0) * part.gloss
            out = out + spec

        # 轻微 Gamma，让暗部不至于发死
        out = np.clip(out, 0.0, 1.0) ** (1 / 1.08)
        return out.astype(np.float32)

    # ---------- 合成：描边 + 降采样 ----------
    def _compose(self) -> np.ndarray:
        mask = self.alpha > 0
        if not mask.any():
            return np.zeros((self.out_h, self.out_w, 4), dtype=np.uint8)

        # 外轮廓：把实体往外扩一圈，落在透明区的位置描边
        outline_color = np.array([74, 58, 66], dtype=np.float32) / 255.0
        rgb = self.color.copy()
        alpha = self.alpha.astype(np.float32) / 255.0

        dilated = mask.copy()
        for _ in range(max(1, self.outline_px)):
            grown = dilated.copy()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                grown |= np.roll(dilated, (dy, dx), axis=(0, 1))
            dilated = grown
        ring = dilated & ~mask
        if ring.any():
            # 轮廓像素取邻近实体颜色的暗化版本，避免纯黑描边太硬
            rgb[ring] = rgb[ring] * 0.0 + outline_color
            alpha[ring] = 1.0

        img = np.concatenate([rgb, alpha[..., None]], axis=-1)
        img = np.clip(img, 0.0, 1.0)

        # 降采样到目标尺寸
        from PIL import Image

        pil = Image.fromarray((img * 255).astype(np.uint8), mode="RGBA")
        pil = pil.resize((self.out_w, self.out_h), Image.LANCZOS)
        return np.array(pil)
