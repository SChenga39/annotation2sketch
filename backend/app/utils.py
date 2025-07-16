import base64

import cv2
import numpy as np


def bytes_to_base64(image_bytes):
    """将图像字节编码为 base64 字符串"""
    return base64.b64encode(image_bytes).decode("utf-8")


def np_to_base64(image_np, file_extension=".png"):
    """将 numpy 数组（图像）编码为 base64 字符串"""
    _, buffer = cv2.imencode(file_extension, image_np)
    return bytes_to_base64(buffer.tobytes())


def base64_to_np(base64_str):
    """将 base64 字符串解码为 numpy 数组（图像）"""
    image_bytes = base64.b64decode(base64_str)
    nparr = np.frombuffer(image_bytes, np.uint8)
    # 解码为灰度图，因为mask是单通道的
    return cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
