#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mac 微信客户端：视频号转发到朋友圈
原理：pyautogui + OpenCV 模板匹配模拟人工点击

⚠️ 风险提示：
1. 微信严禁自动化操作，可能导致限流、封号。
2. 建议先用小号测试，不要直接上大号。
3. 该脚本仅供技术学习，请自行承担使用风险。

使用步骤：
1. 登录 Mac 微信，窗口保持在最前，不要最小化。
2. 在当前目录创建 templates/ 文件夹，并放入以下截图：
   - profile_avatar.png       （微信左上角自己的头像）
   - channels_entry.png       （个人主页里的“视频号”入口）
   - sph_share_btn1.png            （视频号视频下方的分享/转发按钮）
   - sph_share_btn2.png     （分享菜单中的“分享到朋友圈”选项）
   - text_input_area.png      （发朋友圈时的文字输入区域）
   - publish_btn.png          （“发表”按钮）
3. 修改下方 CONFIG 中的文案列表。
4. 运行：python wechat_channels_share_to_moments.py
"""

import os
import sys
import time
import random
import logging
import subprocess
from pathlib import Path
from datetime import datetime

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
# CONFIG：按你的需求修改
# ============================================================
def _get_base_dir():
    if getattr(sys, 'frozen', False):
        exe_path = Path(sys.executable)
        if ".app" in str(exe_path):
            return exe_path.parent.parent.parent.parent
        return exe_path.parent
    return Path(__file__).parent

TEMPLATES_DIR = _get_base_dir() / "templates"

# 启动时是否自动打开微信
AUTO_OPEN_WECHAT = True

# 从环境变量读取文案（GUI 传入），否则使用默认值
_env_caption = os.environ.get("PYQ_CAPTION", "")
if _env_caption:
    CAPTIONS = [_env_caption]
else:
    CAPTIONS = [
        "这个视频讲得不错，推荐看看~",
        "分享一个有价值的视频。",
        "刚好看到这个，挺有启发。",
    ]

# 操作之间的随机延迟（秒）
MIN_ACTION_DELAY = 0.8
MAX_ACTION_DELAY = 2.5

# 找图置信度阈值
MATCH_THRESHOLD = 0.75

# 是否只运行一次就退出
SINGLE_RUN = True

# 要转发的目标视频封面截图，放在 templates/ 目录下
TARGET_VIDEO_COVER = "target_video_cover.png"

# 在视频号列表中查找目标视频时，最多滚动次数
MAX_SCROLL_ATTEMPTS = 10

# 每次滚动距离（像素）
SCROLL_DISTANCE = 400

# 滚动前用于定位视频号列表的锚点图，可选。
# 建议截取视频号列表里稳定可见的一小块区域，放到 templates/channels_scroll_anchor.png。
# 如果该模板不存在或未识别到，会回退到屏幕中心附近滚动。
SCROLL_ANCHOR_TEMPLATE = "channels_scroll_anchor.png"
SCROLL_ANCHOR_THRESHOLD = 0.65

# 找到 sph_btn 后需要往右偏移的像素数（因为直接点击文字无反应）
SPH_BTN_RIGHT_OFFSET = 60

# 发布前是否设置”不给谁看”权限。
ENABLE_PRIVACY_SETTINGS = os.environ.get("PYQ_ENABLE_PRIVACY", "1") == "1"
PRIVACY_DIR = TEMPLATES_DIR / "privacy"
PRIVACY_TAGS_DIR = PRIVACY_DIR / "tags"
PRIVACY_ENTRY_TEMPLATE = "privacy/privacy_entry.png"
PRIVACY_HIDE_FROM_TEMPLATE = "privacy/hide_from_option.png"
PRIVACY_TAG_DONE_TEMPLATE = "privacy/done_btn.png"
PRIVACY_CONFIRM_TEMPLATE = "privacy/confirm_btn.png"
PRIVACY_MATCH_THRESHOLD = 0.45
PRIVACY_MAX_SCROLL_ATTEMPTS = 12
PRIVACY_SCROLL_DISTANCE = 350

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


def click_template(template_name, retries=3, threshold=MATCH_THRESHOLD, use_edge=False):
    for attempt in range(retries):
        pos = find_template(template_name, threshold=threshold, use_edge=use_edge)
        if pos:
            human_like_click(*pos)
            random_delay()
            return True
        logger.warning(f"{template_name} not found, retry {attempt + 1}/{retries}")
        random_delay(1, 2)
    return False


def click_template_right(template_name, offset_x=SPH_BTN_RIGHT_OFFSET, retries=3, threshold=MATCH_THRESHOLD, use_edge=False):
    """查找模板，然后往右偏移 offset_x 像素后再点击。"""
    for attempt in range(retries):
        pos = find_template(template_name, threshold=threshold, use_edge=use_edge)
        if pos:
            target_x = pos[0] + offset_x
            target_y = pos[1]
            human_like_click(target_x, target_y)
            random_delay()
            return True
        logger.warning(f"{template_name} not found, retry {attempt + 1}/{retries}")
        random_delay(1, 2)
    return False


def paste_text(text):
    """将文本写入剪贴板并粘贴到当前焦点位置。"""
    if not text:
        return False

    try:
        from AppKit import NSPasteboard, NSString
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        paste_text_obj = NSString.stringWithString_(text)
        pb.writeObjects_([paste_text_obj])
    except ImportError:
        logger.error("pyobjc is required for clipboard text paste: pip install pyobjc")
        return False

    pyautogui.keyDown('command')
    pyautogui.keyDown('v')
    pyautogui.keyUp('v')
    pyautogui.keyUp('command')
    random_delay(0.5, 1)
    return True


def wait_for_page_load(extra_wait=2):
    """通用等待函数，等待页面元素加载完成。"""
    logger.info(f"Waiting extra {extra_wait}s for page/network load...")
    time.sleep(extra_wait)


def scroll_channels_list(distance=-SCROLL_DISTANCE):
    """在视频号列表区域向下滚动。"""
    anchor_path = TEMPLATES_DIR / SCROLL_ANCHOR_TEMPLATE
    anchor_pos = None

    if anchor_path.exists():
        anchor_pos = find_template(SCROLL_ANCHOR_TEMPLATE, threshold=SCROLL_ANCHOR_THRESHOLD)

    if anchor_pos:
        center_x, center_y = anchor_pos
        logger.info(f"Scroll anchor found at {anchor_pos}")
    else:
        screen_w, screen_h = pyautogui.size()
        center_x = screen_w // 2
        center_y = screen_h // 2
        logger.info("Scroll anchor not found, fallback to screen center")

    pyautogui.moveTo(center_x + random.randint(-100, 100), center_y + random.randint(-50, 50))
    random_delay(0.3, 0.6)
    pyautogui.scroll(distance)
    logger.info(f"Scrolled channels list by {distance}px")
    # 滚动后等待内容加载
    random_delay(2.5, 4)


def scroll_privacy_list(distance=-PRIVACY_SCROLL_DISTANCE):
    """在权限标签列表区域滚动。"""
    screen_w, screen_h = pyautogui.size()
    center_x = screen_w // 2
    center_y = screen_h // 2
    pyautogui.moveTo(center_x + random.randint(-80, 80), center_y + random.randint(-40, 40))
    random_delay(0.3, 0.6)
    pyautogui.scroll(distance)
    logger.info(f"Scrolled privacy list by {distance}px")
    random_delay(1.2, 2.0)


def get_privacy_tag_templates():
    """返回需要勾选的标签模板，按文件名顺序执行。"""
    if not PRIVACY_TAGS_DIR.exists():
        logger.error(f"Privacy tags dir not found: {PRIVACY_TAGS_DIR}")
        return []

    templates = sorted(PRIVACY_TAGS_DIR.glob("*.png"))
    return [path.relative_to(TEMPLATES_DIR).as_posix() for path in templates]


def find_and_click_privacy_tag(tag_template):
    """查找并勾选一个“不给谁看”标签，找不到则向下滚动继续找。"""
    logger.info(f"Looking for privacy tag: {tag_template}")

    for attempt in range(PRIVACY_MAX_SCROLL_ATTEMPTS + 1):
        pos = find_template(tag_template, threshold=PRIVACY_MATCH_THRESHOLD)
        if pos:
            logger.info(f"Privacy tag found at {pos}, clicking...")
            human_like_click(*pos)
            random_delay(0.8, 1.5)
            return True

        if attempt < PRIVACY_MAX_SCROLL_ATTEMPTS:
            logger.info(f"Privacy tag not found, scrolling... ({attempt + 1}/{PRIVACY_MAX_SCROLL_ATTEMPTS})")
            scroll_privacy_list()

    logger.error(f"Privacy tag not found after scrolling: {tag_template}")
    return False


def select_privacy_tags():
    """逐个勾选 privacy/tags 目录中的标签截图。"""
    tag_templates = get_privacy_tag_templates()
    if not tag_templates:
        logger.error("No privacy tag templates found")
        return False

    for tag_template in tag_templates:
        if not find_and_click_privacy_tag(tag_template):
            return False

    return True


def apply_privacy_settings():
    """设置朋友圈“不给谁看”权限。"""
    if not ENABLE_PRIVACY_SETTINGS:
        logger.info("Privacy settings disabled")
        return True

    logger.info("Opening privacy settings...")
    if not click_template(PRIVACY_ENTRY_TEMPLATE, retries=3, threshold=PRIVACY_MATCH_THRESHOLD):
        logger.error("Failed to open privacy settings")
        return False

    logger.info("Choosing 'hide from' privacy option...")
    if not click_template(PRIVACY_HIDE_FROM_TEMPLATE, retries=3, threshold=PRIVACY_MATCH_THRESHOLD):
        logger.error("Failed to choose hide-from option")
        return False

    if not select_privacy_tags():
        return False

    logger.info("Finishing privacy tag selection...")
    if not click_template(PRIVACY_TAG_DONE_TEMPLATE, retries=3, threshold=PRIVACY_MATCH_THRESHOLD):
        logger.error("Failed to click privacy tag done button")
        return False

    logger.info("Confirming privacy settings...")
    if not click_template(PRIVACY_CONFIRM_TEMPLATE, retries=3, threshold=PRIVACY_MATCH_THRESHOLD):
        logger.error("Failed to confirm privacy settings")
        return False

    logger.info("Privacy settings applied")
    return True


def find_and_click_target_video(cover_template=TARGET_VIDEO_COVER, max_attempts=MAX_SCROLL_ATTEMPTS):
    """
    在视频号列表中滚动查找目标视频封面，找到后点击进入。
    每次查找前都会等待页面加载完成。
    """
    logger.info(f"Looking for target video cover: {cover_template}")

    # 首次进入列表后多等一下，让首屏视频封面加载
    wait_for_page_load(3)

    for attempt in range(max_attempts):
        pos = find_template(cover_template)
        if pos:
            logger.info(f"Target video found at {pos}, clicking...")
            human_like_click(*pos)
            logger.info("Waiting for video detail page to load...")
            random_delay(4, 6)
            return True

        logger.info(f"Target video not found on screen, scrolling... ({attempt + 1}/{max_attempts})")
        scroll_channels_list()

    logger.error(f"Target video cover not found after {max_attempts} scroll attempts")
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
    logger.info("WeChat window should be ready. Make sure you are already logged in.")
    return True


def open_channels():
    """
    打开视频号页面：
    1. 点击左上角头像
    2. 找到 sph_btn 文字，往右偏移后点击（直接点文字无反应）
    3. 等待视频号列表加载完成
    """
    logger.info("Step 1: 点击头像...")
    if not click_template("profile_avatar.png"):
        logger.error("Failed to click profile avatar")
        return False

    logger.info("等待个人主页加载...")
    random_delay(3, 5)

    logger.info(f"Step 2: 找到 sph_btn，往右偏移 {SPH_BTN_RIGHT_OFFSET}px 后点击...")
    if not click_template_right("sph_btn.png", offset_x=SPH_BTN_RIGHT_OFFSET):
        logger.error("Failed to click sph_btn (right offset)")
        return False

    logger.info("等待视频号页面加载...")
    random_delay(5, 8)
    return True


def share_video_to_moments(caption):
    """
    转发当前视频号视频到朋友圈。
    前提：已经进入视频详情页。
    """
    logger.info("Waiting for share button to be ready...")
    random_delay(2, 3)

    logger.info("Clicking share button...")
    if not click_template("sph_share_btn1.png"):
        logger.error("Failed to click share button")
        return False

    logger.info("Waiting for share menu to appear...")
    random_delay(2, 3)

    logger.info("Clicking 'Share to Moments'...")
    if not click_template("sph_share_btn2.png"):
        logger.error("Failed to click share to moments")
        return False

    logger.info("Waiting for Moments editor to load...")
    random_delay(4, 6)

    # 输入文案
    if caption:
        pos = find_template("text_input_area.png")
        if pos:
            human_like_click(*pos)
            random_delay(0.5, 1)
            paste_text(caption)
        else:
            paste_text(caption)

    random_delay(2, 3)

    # 设置隐私：不给谁看
    logger.info(">>> 准备执行隐私设置...")
    if not apply_privacy_settings():
        logger.warning("Privacy settings failed, continuing to publish anyway...")

    random_delay(2, 3)

    logger.info("Clicking publish button...")
    if not click_template("publish_btn.png"):
        logger.error("Failed to click publish button")
        return False

    logger.info("Shared to moments successfully")
    return True


def main():
    logger.info("=" * 50)
    logger.info("WeChat Channels Share to Moments starting...")
    logger.info("⚠️  Remember: high risk of account restriction/ban.")
    logger.info("=" * 50)

    if not TEMPLATES_DIR.exists():
        TEMPLATES_DIR.mkdir(parents=True)
        logger.info(f"Created templates dir: {TEMPLATES_DIR}")
        logger.info("Please put your screenshot templates there and rerun.")
        return

    if not ensure_wechat_ready():
        logger.error("WeChat is not ready, exiting")
        return

    # 打开视频号主页
    if not open_channels():
        logger.error("Failed to open Channels")
        return

    # 在视频号列表中查找并点击目标视频
    if not find_and_click_target_video():
        logger.error("Failed to find target video")
        return

    caption = random.choice(CAPTIONS)
    logger.info(f"Preparing to share with caption: {caption[:20]}...")

    if share_video_to_moments(caption):
        logger.info("Share completed")
    else:
        logger.error("Share failed")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Stopped by user")
