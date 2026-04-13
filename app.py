# =====================================================================
# app.py — 상품 이미지 자동 합성 웹 앱 (Streamlit)
# =====================================================================
# 실행 방법: 터미널에서 아래 명령어를 입력하고 엔터를 누르세요.
#   python3 -m streamlit run app.py
#
# 기능:
#   - 배경: 단색(색상 선택) 또는 이미지 업로드
#   - 상품 최대 3개 업로드 → 자동 누끼 제거(rembg)
#   - 상품별 위치(x, y), 크기, 그림자를 슬라이더로 조절
#   - [합성하기] 버튼으로 결과 미리보기
#   - [다운로드] 버튼으로 PNG 저장
# =====================================================================

import io

import streamlit as st
from PIL import Image, ImageFilter
from rembg import remove

# ─────────────────────────────────────────────
# 설정 상수
# ─────────────────────────────────────────────

CANVAS_WIDTH   = 1200   # 완성 이미지 가로 크기 (픽셀)
CANVAS_HEIGHT  = 900    # 완성 이미지 세로 크기 (픽셀)
SHADOW_OFFSET_X = 0     # 그림자 가로 오프셋
SHADOW_OFFSET_Y = 10    # 그림자 세로 오프셋 (살짝 아래)
MAX_PRODUCTS   = 3      # 한 번에 합성할 수 있는 최대 상품 수


# ─────────────────────────────────────────────
# 핵심 처리 함수 (main.py 로직 재사용)
# ─────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _run_rembg(image_bytes: bytes) -> bytes:
    """
    rembg로 배경을 제거하고 결과 바이트를 반환하는 함수.
    같은 이미지를 다시 누끼 제거하지 않도록 Streamlit이 자동 캐싱합니다.
    """
    return remove(image_bytes)


def remove_background(image_bytes: bytes) -> Image.Image:
    """
    업로드된 이미지 바이트를 받아 배경이 제거된 RGBA PIL Image를 반환합니다.
    """
    result_bytes = _run_rembg(image_bytes)
    return Image.open(io.BytesIO(result_bytes)).convert("RGBA")


def create_shadow(product_image: Image.Image, opacity: int, blur_radius: int) -> Image.Image:
    """
    상품 이미지의 실루엣을 따서 그림자를 생성합니다.
    - opacity    : 그림자 진하기 (0~255)
    - blur_radius: 그림자 퍼짐 정도 (픽셀)
    """
    _, _, _, alpha = product_image.split()  # 알파 채널 추출

    shadow_base  = Image.new("L", product_image.size, 0)  # 검은색 실루엣 베이스
    opacity_ratio = opacity / 255.0
    shadow_alpha  = alpha.point(lambda p: int(p * opacity_ratio))  # 농도 조절

    shadow = Image.merge("LA", (shadow_base, shadow_alpha))

    if blur_radius > 0:
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    return shadow.convert("RGBA")


def create_background(bg_type: str, color: str = "#f5e6d3", image_bytes: bytes = None) -> Image.Image:
    """
    배경 캔버스를 생성합니다.
    - bg_type    : "단색" 또는 "이미지 업로드"
    - color      : HEX 색상 코드 (#ffffff)
    - image_bytes: 배경 이미지 바이트
    """
    canvas_size = (CANVAS_WIDTH, CANVAS_HEIGHT)

    if bg_type == "단색":
        hex_code = color.lstrip("#")
        r = int(hex_code[0:2], 16)
        g = int(hex_code[2:4], 16)
        b = int(hex_code[4:6], 16)
        return Image.new("RGBA", canvas_size, (r, g, b, 255))
    else:
        bg_image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        return bg_image.resize(canvas_size, Image.LANCZOS)


def paste_product_with_shadow(
    canvas: Image.Image,
    product: Image.Image,
    x: int, y: int,
    shadow_opacity: int, shadow_blur: int
) -> Image.Image:
    """
    캔버스에 그림자를 먼저 붙이고, 그 위에 상품을 합성합니다.
    """
    shadow = create_shadow(product, shadow_opacity, shadow_blur)

    # 그림자를 오프셋만큼 이동해서 붙임
    canvas.paste(shadow, (x + SHADOW_OFFSET_X, y + SHADOW_OFFSET_Y), shadow.split()[3])
    # 그 위에 상품 이미지 붙임
    canvas.paste(product, (x, y), product.split()[3])

    return canvas


def composite(
    bg_type: str,
    bg_color: str,
    bg_image_bytes: bytes,
    products: list,       # [(image_bytes, x, y, size), ...]
    shadow_opacity: int,
    shadow_blur: int
) -> Image.Image:
    """
    전체 합성 과정을 실행하고 완성된 이미지를 반환합니다.
    products 리스트의 각 항목: (image_bytes, x좌표, y좌표, 너비px)
    """
    canvas = create_background(bg_type, bg_color, bg_image_bytes)

    for image_bytes, x, y, size in products:
        # 누끼 제거
        product_img = remove_background(image_bytes)

        # 크기 조절 (너비 기준, 비율 유지)
        if size > 0:
            orig_w, orig_h = product_img.size
            target_h = int(orig_h * size / orig_w)
            product_img = product_img.resize((size, target_h), Image.LANCZOS)

        canvas = paste_product_with_shadow(canvas, product_img, x, y, shadow_opacity, shadow_blur)

    return canvas


# ─────────────────────────────────────────────
# Streamlit 웹 UI
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="상품 이미지 합성기",
    layout="wide",
)

st.title("상품 이미지 자동 합성기")
st.caption("상품 사진을 업로드하면 배경 제거(누끼) 후 자동으로 합성해 드립니다.")

st.divider()

# 좌우 2단 레이아웃 — 왼쪽: 설정, 오른쪽: 결과
col_left, col_right = st.columns([1, 1.4], gap="large")


# ── 왼쪽: 설정 패널 ──────────────────────────
with col_left:

    # 1. 배경 설정
    st.subheader("1. 배경")
    bg_type = st.radio("배경 유형", ["단색", "이미지 업로드"], horizontal=True, label_visibility="collapsed")

    bg_color      = "#f5e6d3"
    bg_image_bytes = None

    if bg_type == "단색":
        bg_color = st.color_picker("배경 색상", "#f5e6d3")
    else:
        bg_file = st.file_uploader("배경 이미지 (JPG/PNG)", type=["jpg", "jpeg", "png"], key="bg")
        if bg_file:
            bg_image_bytes = bg_file.read()
            st.image(io.BytesIO(bg_image_bytes), caption="배경 미리보기", use_container_width=True)

    st.divider()

    # 2. 상품 이미지 (최대 3개)
    st.subheader("2. 상품 이미지")

    products = []  # [(image_bytes, x, y, size), ...]

    for i in range(1, MAX_PRODUCTS + 1):
        with st.expander(f"상품 {i}", expanded=(i == 1)):
            prod_file = st.file_uploader(
                f"상품 {i} 이미지 (JPG/PNG)",
                type=["jpg", "jpeg", "png"],
                key=f"prod_{i}",
                label_visibility="collapsed",
            )

            if prod_file:
                prod_bytes = prod_file.read()

                # 원본 미리보기 (작게)
                st.image(io.BytesIO(prod_bytes), caption=f"상품 {i} 원본", width=160)

                # 위치 슬라이더
                c1, c2 = st.columns(2)
                with c1:
                    x = st.slider("X 위치", 0, CANVAS_WIDTH - 1,  value=80 + (i - 1) * 400, key=f"x_{i}")
                with c2:
                    y = st.slider("Y 위치", 0, CANVAS_HEIGHT - 1, value=300,                  key=f"y_{i}")

                # 크기 슬라이더
                size = st.slider("크기 (너비 px)", 50, CANVAS_WIDTH, value=500, key=f"size_{i}")

                products.append((prod_bytes, x, y, size))

    st.divider()

    # 3. 그림자 설정
    st.subheader("3. 그림자")
    shadow_opacity = st.slider("그림자 농도 (0=없음 ~ 255=진함)", 0, 255, 180)
    shadow_blur    = st.slider("그림자 흐림 (0=선명 ~ 60=매우 퍼짐)", 0, 60, 20)

    st.divider()

    # 4. 저장 파일명 + 합성 버튼
    output_filename = st.text_input("저장 파일명", "result.png")

    run_btn = st.button("합성하기", type="primary", use_container_width=True)


# ── 오른쪽: 결과 패널 ────────────────────────
with col_right:
    st.subheader("결과 미리보기")

    # [합성하기] 버튼 클릭 시 처리
    if run_btn:
        # 유효성 검사
        if not products:
            st.error("상품 이미지를 최소 하나 업로드해 주세요.")
        elif bg_type == "이미지 업로드" and bg_image_bytes is None:
            st.error("배경 이미지를 업로드해 주세요.")
        else:
            with st.spinner("누끼 제거 및 합성 중입니다... 잠시만 기다려 주세요."):
                result_img = composite(
                    bg_type, bg_color, bg_image_bytes,
                    products,
                    shadow_opacity, shadow_blur,
                )
            # 결과를 세션에 저장 (다운로드 버튼이 사라지지 않도록)
            st.session_state["result_img"]       = result_img
            st.session_state["output_filename"]  = output_filename

    # 결과 이미지 표시
    if "result_img" in st.session_state:
        result_img = st.session_state["result_img"]

        st.image(result_img, caption="합성 완료", use_container_width=True)

        # PNG 바이트로 변환 후 다운로드 버튼 제공
        buf = io.BytesIO()
        result_img.save(buf, format="PNG")

        st.download_button(
            label="다운로드 (PNG)",
            data=buf.getvalue(),
            file_name=st.session_state.get("output_filename", "result.png"),
            mime="image/png",
            use_container_width=True,
        )
    else:
        # 아직 합성 전 안내 문구
        st.info("왼쪽에서 설정을 마친 뒤 [합성하기] 버튼을 눌러 주세요.")
        st.markdown(
            """
            **사용 순서**
            1. 배경 색상 또는 배경 이미지를 선택하세요.
            2. 상품 이미지를 업로드하고 위치·크기를 조절하세요.
            3. 그림자 농도와 흐림 정도를 설정하세요.
            4. [합성하기] 버튼을 누르면 결과물이 여기에 표시됩니다.
            5. [다운로드] 버튼으로 PNG 파일을 저장하세요.
            """
        )
