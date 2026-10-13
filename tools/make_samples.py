"""生成 OCR 测试图（Pillow 合成，无需游戏截图即可在 Mac 上跑通全链路）。

产物（samples/）：
- test_korean.png        纯韩语聊天
- test_english.png       纯英语聊天
- test_mixed.png         韩英混合
- test_slang.png         游戏黑话（궁/힐 等）
- test_low_contrast.png  低对比度（深灰底深灰字，考察 CLAHE）
- test_seq_0.png ...     连续帧序列（阶段 2 去重回放用）

字体自动探测：韩文用 AppleSDGothicNeo / AppleGothic，英文用 Arial；
找不到时给出明确报错（Windows 上可放 malgun.ttf 到 samples/fonts/）。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "samples"
FONT_CANDIDATES = {
    "ko": [  # 韩文字体候选，按顺序探测
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/AppleGothic.ttf",
        "C:/Windows/Fonts/malgun.ttf",       # Windows 部署时生效
        "samples/fonts/malgun.ttf",          # 手动放置
    ],
    "en": [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "samples/fonts/arial.ttf",
    ],
}

# 聊天样式：深色半透明底 + 浅色文字（近似守望先锋聊天框）
BG = (18, 22, 30, 230)
FG = (235, 235, 235)

KOREAN_LINES = [
    "라인호버: 아군 궁극기 준비됨",
    "정크랫: 힐 좀 해줘",
    "라인호버: 서두르자 점령까지 30초",
    "D.Va: 기계 폭발 조심",
]
ENGLISH_LINES = [
    "Genji: I need healing",
    "Mercy: ult is ready, group up",
    "Zenyatta: watch the flank",
    "Tank: push the point now",
]
MIXED_LINES = [
    "라인호버: 궁 ready? 같이 갑시다",
    "Genji: 힐해줘 please",
    "정크랫: trap set near point B",
    "Ana: 궁 쓸게, 고개 숙여",
]
SLANG_LINES = [
    "돌격: 궁 게이지 다참",
    "힐러: 힐 없음 물어봐",
    "탱커: 라인 몰아줘 궁턴 준비",
    "서포터: 복구 이륙",
]
SEQ_LINES = [
    "라인호버: 포인트 점령 시작",
    "정크랫: 지뢰 설치 완료",
]


def find_font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES[kind]:
        p = Path(path)
        if p.is_file():
            try:
                return ImageFont.truetype(str(p), size)
            except OSError:
                continue
    raise SystemExit(
        f"未找到 {kind} 字体；Windows 用户请把 malgun.ttf 放到 samples/fonts/ 下再运行"
    )


def render_chat(lines: list[str], out_name: str, *, contrast: int = 1.0,
                bg_alpha: int = 230) -> Path:
    """渲染一张聊天框样式的图。contrast<1 时降低文字/背景对比度。"""
    font = find_font("ko", 20)
    pad, line_h = 14, 30
    width = max(font.getlength(t) for t in lines) + pad * 2
    height = line_h * len(lines) + pad * 2

    img = Image.new("RGBA", (int(width), height))
    overlay = Image.new("RGBA", img.size, (18, 22, 30, bg_alpha))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # contrast: 1.0 为正常；低对比度时把前景色向背景色靠拢
    fg = tuple(int(BG[i] + (FG[i] - BG[i]) * contrast) for i in range(3)) + (255,)
    y = pad
    for t in lines:
        draw.text((pad, y), t, font=font, fill=fg)
        y += line_h

    out = OUT / out_name
    img.convert("RGB").save(out)
    print(f"生成 {out.relative_to(ROOT)} ({out.stat().st_size} bytes)")
    return out


def render_sequence() -> list[Path]:
    """连续帧：帧 0 无消息；帧 1 出现前 1 条；帧 2 滚动（旧行上移，首行消失）+ 新消息。

    用于阶段 2 验证：同一消息在多帧出现也只翻译一次。
    """
    paths: list[Path] = []
    frames = [
        [],                       # 空帧
        SEQ_LINES[:1],            # 新消息出现
        SEQ_LINES,                # 滚动 + 新消息
        SEQ_LINES[1:] + ["D.Va: 폭발 조심"],  # 继续滚动
    ]
    for i, lines in enumerate(frames):
        name = f"test_seq_{i}.png" if lines else "test_seq_empty.png"
        # 用固定底图 + 不同行数，行位置随帧变化（模拟聊天滚动）
        paths.append(render_chat(lines or [" "], name))
    return paths


def main() -> None:
    OUT.mkdir(exist_ok=True)
    render_chat(KOREAN_LINES, "test_korean.png")
    render_chat(ENGLISH_LINES, "test_english.png")
    render_chat(MIXED_LINES, "test_mixed.png")
    render_chat(SLANG_LINES, "test_slang.png")
    render_chat(KOREAN_LINES, "test_low_contrast.png", contrast=0.28)
    render_sequence()
    print("完成。真实截图请放入 samples/real/（已 gitignore）")


if __name__ == "__main__":
    sys.exit(main())
