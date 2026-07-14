#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mac 微信客户端：删除朋友圈
原理：pyautogui + OpenCV 模板匹配模拟人工点击

流程：
1. 打开微信 → 点击头像 → 进入朋友圈
2. 找到 camera_icon 但不点击，鼠标往下移一点
3. 点击进入朋友圈内容
4. 找到 del_icon 点击 → 找到 del_text 点击 → 完成删除

⚠️ 风险提示：
1. 微信严禁自动化操作，可能导致限流、封号。
2. 建议先用小号测试，不要直接上大号。
3. 该脚本仅供技术学习，请自行承担使用风险。
"""

import os
import sys
import time
import random
import logging
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

pyautogui.FAILSAFE = True

# ============================================================
# CONFIG
# ============================================================
def _get_base_dir():
    if getattr(sys, 'frozen', False):
        exe_path = Path(sys.executable)
        if ".app" in str(exe_path):
            return exe_path.parent.parent.parent.parent
        return exe_path.parent
    return Path(__file__).parent

TEMPLATES_DIR = _get_base_dir() / "templates"

AUTO_OPEN_WECHAT = True

MIN_ACTION_DELAY = 0.8
MAX_ACTION_DELAY = 2.5

MATCH_THRESHOLD = 0.6

# 找到"朋友圈"文字后往右偏移像素数
MOMENTS_RIGHT_OFFSET = 60

# 找到 camera_icon 后鼠标往下移的像素数
CAMERA_DOWN_OFFSET = 90

# ============================================================
# 工具函数
# ============================================================


def random_delay(min_sec=MIN_ACTION_DELAY, max_sec=MAX_ACTION_DELAY):
    sec = random.uniform(min_sec, max_sec)
    time.sleep(sec)


def human_like_click(x, y):
    offset_x = random.randint(-8, 8)
    offset_y = random.randint(-6, 6)
    target_x = x + offset_x
    target_y = y + offset_y
    duration = random.uniform(0.15, 0.45)
    pyautogui.moveTo(target_x, target_y, duration=duration)
    pyautogui.click()
    logger.info(f"Clicked at ({target_x}, {target_y})")


def grab_screen():
    screenshot = ImageGrab.grab()
    return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)


def find_template(template_name, threshold=MATCH_THRESHOLD, use_edge=False):
    template_path = TEMPLATES_DIR / template_name
    if not template_path.exists():
        logger.error(f"Template not found: {template_path}")
        return None

    screen_bgr = grab_screen()
    template_bgr = cv2.imread(str(template_path))
    if template_bgr is None:
        logger.error(f"Failed to load template: {template_path}")
        return None

    screen_gray = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
    template_gray = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2GRAY)

    if template_gray.shape[0] > screen_gray.shape[0] or template_gray.shape[1] > screen_gray.shape[1]:
        logger.warning(f"Template {template_name} is larger than screen")
        return None

    if use_edge:
        screen_match = cv2.Canny(screen_gray, 50, 150)
        template_match = cv2.Canny(template_gray, 50, 150)
    else:
        screen_match = screen_gray
        template_match = template_gray

    result = cv2.matchTemplate(screen_match, template_match, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    logger.info(f"Matching {template_name}: confidence={max_val:.3f} (edge={use_edge})")

    if max_val < threshold:
        return None

    h, w = template_gray.shape[:2]
    center_x = max_loc[0] + w // 2
    center_y = max_loc[1] + h // 2
    return center_x, center_y


def click_template(template_name, retries=3, use_edge=False):
    for attempt in range(retries):
        pos = find_template(template_name, use_edge=use_edge)
        if pos:
            human_like_click(*pos)
            random_delay()
            return True
        logger.warning(f"{template_name} not found, retry {attempt + 1}/{retries}")
        random_delay(1, 2)
    return False


def click_template_right(template_name, offset_x=MOMENTS_RIGHT_OFFSET, retries=3, use_edge=False):
    for attempt in range(retries):
        pos = find_template(template_name, use_edge=use_edge)
        if pos:
            target_x = pos[0] + offset_x
            target_y = pos[1]
            human_like_click(target_x, target_y)
            random_delay()
            return True
        logger.warning(f"{template_name} not found, retry {attempt + 1}/{retries}")
        random_delay(1, 2)
    return False


# ============================================================
# 核心流程
# ============================================================


def open_wechat():
    logger.info("Opening WeChat via 'open -a WeChat'...")
    try:
        subprocess.run(["open", "-a", "WeChat"], check=True)
        logger.info("WeChat launched/activated")
        return True
    except Exception as e:
        logger.error(f"Failed to open WeChat: {e}")
        return False


def ensure_wechat_ready():
    if not AUTO_OPEN_WECHAT:
        logger.info("AUTO_OPEN_WECHAT is disabled, assuming WeChat is already open")
        return True

    if not open_wechat():
        return False

    time.sleep(3)
    logger.info("WeChat window should be ready.")
    return True


def open_moments():
    """打开朋友圈页面：点头像 → 找'朋友圈'文字往右点击"""
    logger.info("Step 1: 点击头像...")
    if not click_template("profile_avatar.png"):
        logger.error("Failed to click profile avatar")
        return False

    logger.info("等待个人主页加载...")
    random_delay(2, 3)

    logger.info(f"Step 2: 找到'朋友圈'文字，往右偏移 {MOMENTS_RIGHT_OFFSET}px 后点击...")
    if not click_template_right("pyq_btn.png", offset_x=MOMENTS_RIGHT_OFFSET):
        logger.error("Failed to click Moments entry")
        return False

    logger.info("等待朋友圈页面加载...")
    random_delay(2, 4)
    return True


def delete_moment():
    """
    删除一条朋友圈：
    1. 找到 camera_icon，鼠标移到上面再往下移一点
    2. 点击进入朋友圈内容
    3. 找到 del_icon 点击
    4. 找到 del_text 点击确认删除
    """
    # 找到 camera_icon（边缘检测，适应不同灰色度）
    logger.info("查找 camera_icon ...")
    pos = find_template("camera_icon.png", use_edge=True)
    if not pos:
        logger.error("camera_icon 未找到")
        return False

    logger.info(f"找到 camera_icon 位置: {pos}，鼠标移过去...")
    pyautogui.moveTo(pos[0], pos[1], duration=random.uniform(0.2, 0.4))
    random_delay(0.3, 0.5)

    # 鼠标往下移一点
    pyautogui.moveRel(0, CAMERA_DOWN_OFFSET, duration=random.uniform(0.15, 0.3))
    logger.info(f"鼠标下移 {CAMERA_DOWN_OFFSET}px")
    random_delay(0.3, 0.5)

    # 点击进入朋友圈内容
    pyautogui.click()
    logger.info("点击进入朋友圈内容")
    random_delay(2, 3)

    # 找到 del_icon 点击
    logger.info("查找 del_icon ...")
    if not click_template("del_icon.png"):
        logger.error("del_icon 未找到")
        return False

    random_delay(1, 2)

    # 找到 del_text 点击确认删除
    logger.info("查找 del_text ...")
    if not click_template("del_text.png"):
        logger.error("del_text 未找到")
        return False

    logger.info("朋友圈删除成功")
    random_delay(1, 2)
    return True


def main():
    logger.info("=" * 50)
    logger.info("WeChat Moments Delete starting...")
    logger.info("=" * 50)

    if not TEMPLATES_DIR.exists():
        logger.error(f"Templates dir not found: {TEMPLATES_DIR}")
        return

    if not ensure_wechat_ready():
        logger.error("WeChat is not ready, exiting")
        return

    if not open_moments():
        logger.error("Failed to open Moments")
        return

    if delete_moment():
        logger.info("Delete completed")
    else:
        logger.error("Delete failed")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Stopped by user")
