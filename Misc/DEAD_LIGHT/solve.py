#!/usr/bin/env python3

import argparse
from pathlib import Path

import cv2
import numpy as np


# Manually confirmed guide-light coordinates in the 2048x360 polar image.
A_GUIDES = np.array(
    [
        [1437.078, 15.595],
        [1316.639, 8.566],
        [1201.391, 15.945],
        [1072.591, 27.870],
        [919.432, 32.442],
        [934.531, 53.771],
        [966.670, 81.714],
        [1015.349, 98.619],
        [1212.500, 74.031],
        [1407.381, 45.898],
        [1582.626, 41.473],
        [1548.295, 30.174],
    ],
    dtype=np.float32,
)

B_GUIDES = np.array(
    [
        [495.782, 198.459],
        [606.333, 172.703],
        [825.862, 189.634],
        [1004.292, 204.396],
        [1157.990, 203.438],
        [1154.832, 223.993],
        [1131.464, 247.446],
        [1092.362, 261.569],
        [905.511, 260.489],
        [683.737, 237.686],
        [417.151, 247.866],
        [417.371, 232.113],
    ],
    dtype=np.float32,
)

# x > 2048 is intentional because ghost C crosses the polar seam.
C_GUIDES = np.array(
    [
        [1634.184, 110.695],
        [1729.495, 95.495],
        [1883.240, 105.058],
        [2040.576, 116.495],
        [2215.670, 109.348],
        [2227.177, 125.496],
        [2195.398, 147.945],
        [2136.575, 168.743],
        [1924.473, 165.847],
        [1710.973, 145.747],
        [1497.349, 149.946],
        [1534.848, 133.964],
    ],
    dtype=np.float32,
)


def make_polar(image_bgr: np.ndarray) -> np.ndarray:
    # These parameters reproduce the working polar image used during analysis.
    polar_width = int(2048)
    polar_height = int(360)

    center_x = float(512.0)
    center_y = float(506.0)

    radius_min = float(220.0)
    radius_max = float(460.0)

    x = np.arange(
        polar_width,
        dtype=np.float32,
    )[None, :]

    y = np.arange(
        polar_height,
        dtype=np.float32,
    )[:, None]

    radius = (
        radius_min
        + (radius_max - radius_min)
        * y
        / float(polar_height)
    )

    theta = (
        -2.0
        * np.pi
        * x
        / float(polar_width)
    )

    map_x = (
        center_x
        + radius * np.cos(theta)
    ).astype(np.float32)

    map_y = (
        center_y
        + radius * np.sin(theta)
    ).astype(np.float32)

    polar_bgr = cv2.remap(
        image_bgr,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )

    return polar_bgr


def ruled_warp(
    polar_bgr: np.ndarray,
    guides: np.ndarray,
    output_width: int = 1500,
    output_height: int = 300,
) -> np.ndarray:
    # The 12 guide lights are treated as two ordered rows of six.
    top_ids = [0, 1, 2, 3, 4, 5]
    bottom_ids = [11, 10, 9, 8, 7, 6]

    columns = np.linspace(
        0.0,
        float(int(output_width) - 1),
        num=6,
        dtype=np.float32,
    )

    map_x = np.zeros(
        (int(output_height), int(output_width)),
        dtype=np.float32,
    )

    map_y = np.zeros(
        (int(output_height), int(output_width)),
        dtype=np.float32,
    )

    vertical_t = np.linspace(
        0.0,
        1.0,
        num=int(output_height),
        dtype=np.float32,
    )[:, None]

    for dst_x in range(int(output_width)):
        strip_index = int(
            np.searchsorted(
                columns,
                float(dst_x),
                side="right",
            )
            - 1
        )

        strip_index = int(
            max(
                0,
                min(
                    4,
                    strip_index,
                ),
            )
        )

        left_x = float(
            columns[strip_index]
        )

        right_x = float(
            columns[strip_index + 1]
        )

        horizontal_t = float(
            (float(dst_x) - left_x)
            / max(
                1.0,
                right_x - left_x,
            )
        )

        top_point = (
            (1.0 - horizontal_t)
            * guides[top_ids[strip_index]]
            + horizontal_t
            * guides[top_ids[strip_index + 1]]
        ).astype(np.float32)

        bottom_point = (
            (1.0 - horizontal_t)
            * guides[bottom_ids[strip_index]]
            + horizontal_t
            * guides[bottom_ids[strip_index + 1]]
        ).astype(np.float32)

        source_xy = (
            (1.0 - vertical_t)
            * top_point[None, :]
            + vertical_t
            * bottom_point[None, :]
        ).astype(np.float32)

        map_x[:, dst_x] = source_xy[:, 0]
        map_y[:, dst_x] = source_xy[:, 1]

    # Duplicate the polar image horizontally so seam-crossing coordinates work.
    polar_double = np.concatenate(
        [
            polar_bgr,
            polar_bgr,
        ],
        axis=1,
    )

    rectified_bgr = cv2.remap(
        polar_double,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )

    return rectified_bgr


def enhance_for_reading(
    image_bgr: np.ndarray,
) -> np.ndarray:
    gray = cv2.cvtColor(
        image_bgr,
        cv2.COLOR_BGR2GRAY,
    )

    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8),
    )

    contrast = clahe.apply(
        gray,
    )

    blur = cv2.GaussianBlur(
        contrast,
        (0, 0),
        sigmaX=1.0,
    )

    sharpened = cv2.addWeighted(
        contrast,
        1.6,
        blur,
        -0.6,
        0.0,
    )

    return sharpened


def make_contact_sheet(
    raw_a: np.ndarray,
    raw_b_flipx: np.ndarray,
    raw_c: np.ndarray,
) -> np.ndarray:
    labels = [
        ("A", raw_a),
        ("B flip-x", raw_b_flipx),
        ("C", raw_c),
    ]

    rows: list[np.ndarray] = []

    for label, image in labels:
        canvas = np.zeros(
            (
                int(image.shape[0]) + 36,
                int(image.shape[1]),
                3,
            ),
            dtype=np.uint8,
        )

        canvas[
            36:,
            :,
        ] = image

        cv2.putText(
            canvas,
            str(label),
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        rows.append(
            canvas,
        )

    return np.vstack(
        rows,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Extract the three Khepri ghost images from the original PNG "
            "using the confirmed guide-light coordinates."
        )
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Path to deadlight-preview(3).png",
    )

    parser.add_argument(
        "-o",
        "--outdir",
        type=Path,
        default=Path("khepri_out"),
        help="Output directory",
    )

    args = parser.parse_args()

    input_path = Path(
        args.input
    )

    output_dir = Path(
        args.outdir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    image_bgr = cv2.imread(
        str(input_path),
        cv2.IMREAD_COLOR,
    )

    if image_bgr is None:
        raise SystemExit(
            f"Failed to read image: {input_path}"
        )

    polar_bgr = make_polar(
        image_bgr,
    )

    raw_a = ruled_warp(
        polar_bgr,
        A_GUIDES,
    )

    raw_b = ruled_warp(
        polar_bgr,
        B_GUIDES,
    )

    raw_c = ruled_warp(
        polar_bgr,
        C_GUIDES,
    )

    # B is mirrored relative to the reading order of A and C.
    raw_b_flipx = cv2.flip(
        raw_b,
        1,
    )

    enhanced_a = enhance_for_reading(
        raw_a,
    )

    enhanced_b = enhance_for_reading(
        raw_b_flipx,
    )

    enhanced_c = enhance_for_reading(
        raw_c,
    )

    contact = make_contact_sheet(
        raw_a,
        raw_b_flipx,
        raw_c,
    )

    cv2.imwrite(
        str(output_dir / "01_polar.png"),
        polar_bgr,
    )

    cv2.imwrite(
        str(output_dir / "02_raw_A.png"),
        raw_a,
    )

    cv2.imwrite(
        str(output_dir / "03_raw_B_flipx.png"),
        raw_b_flipx,
    )

    cv2.imwrite(
        str(output_dir / "04_raw_C.png"),
        raw_c,
    )

    cv2.imwrite(
        str(output_dir / "05_A_enhanced.png"),
        enhanced_a,
    )

    cv2.imwrite(
        str(output_dir / "06_B_flipx_enhanced.png"),
        enhanced_b,
    )

    cv2.imwrite(
        str(output_dir / "07_C_enhanced.png"),
        enhanced_c,
    )

    cv2.imwrite(
        str(output_dir / "08_compare_ABC.png"),
        contact,
    )

    print(f"[+] Input      : {input_path}")
    print(f"[+] Output dir : {output_dir}")
    print()
    print("[+] Main outputs:")
    print("    02_raw_A.png")
    print("    03_raw_B_flipx.png")
    print("    04_raw_C.png")
    print("    08_compare_ABC.png")
    print()
    print("[+] Read the three rectified ghosts together.")
    print("[+] Recovered flag:")
    print("    STARPWN{DEAD_SIGN_RETURNS}")


if __name__ == "__main__":
    main()
