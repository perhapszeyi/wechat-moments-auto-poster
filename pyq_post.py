#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mac 微信客户端朋友圈自动发布 Demo
原理：pyautogui + OpenCV 模板匹配模拟人工点击

⚠️ 风险提示：
1. 微信严禁自动化操作，可能导致限流、封号。
2. 建议先用小号测试，不要直接上大号。
3. 该脚本仅供技术学习，请自行承担使用风险。

使用步骤：
1. 登录 Mac 微信，窗口保持在最前，不要最小化。
2. 在当前目录创建 templates/ 文件夹，并放入以下截图：
   - pyq_btn.png      （微信左侧“朋友圈”按钮）
   - camera_icon.png      （朋友圈右上角相机图标）
   - text_input_area.png  （朋友圈文字输入区域，用于定位光标）
   - publish_btn.png      （“发表”按钮）
   - add_photo_btn.png    （发朋友圈时底部“添加图片/视频”按钮，可选）
3. 修改下方 CONFIG 中的文案列表和媒体文件路径。
4. 运行：python wechat_moments_poster.py

媒体发送说明：
- 图片：通过剪贴板粘贴到输入框，较稳定。
- 视频：点击“添加图片/视频”按钮后，使用 Command+Shift+G 输入文件路径选择视频。
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

# 安全设置：鼠标移到屏幕左上角会触发异常中断
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
IMAGES_DIR = _get_base_dir() / "images"

# 启动时是否自动打开微信
AUTO_OPEN_WECHAT = True

# 从环境变量读取文案（GUI 传入），否则使用默认值
_env_caption = os.environ.get("PYQ_CAPTION", "")
if _env_caption:
    CAPTIONS = [_env_caption]
else:
    CAPTIONS = [
        "Yes，你好～-！"
    ]

# 从环境变量读取图片路径
_env_image = os.environ.get("PYQ_IMAGE_PATH", "")
IMAGES_POOL = [_env_image] if _env_image else []

# 从环境变量读取视频路径，否则使用默认值
_env_video = os.environ.get("PYQ_VIDEO_PATH", "")
if _env_video:
    VIDEOS_POOL = [_env_video]
else:
    VIDEOS_POOL = [
        "/Users/mac/Desktop/pycode/测试案例/微信朋友圈自动发送/videos/test.MP4"
    ]

# 每次发布使用什么媒体
#   "text"      : 只发文字
#   "image"     : 发文字 + 图片
#   "video"     : 发文字 + 视频
#   "random"    : 从上面三种类型中随机选（需要有对应素材）
# 根据传入的路径自动判断媒体类型
if _env_video:
    MEDIA_TYPE = "video"
elif _env_image:
    MEDIA_TYPE = "image"
else:
    MEDIA_TYPE = "text"

# 是否在发新朋友圈前删除上一条？风险较高，默认关闭
DELETE_PREVIOUS = False

# 操作之间的随机延迟（秒）
MIN_ACTION_DELAY = 0.8
MAX_ACTION_DELAY = 2.5

# 找图置信度阈值（0~1），越高越严格
MATCH_THRESHOLD = 0.6

# 屏幕缩放系数，Retina 屏 Mac 一般设为 2；普通外接屏设为 1
SCREEN_SCALE = 2

# 找到"朋友圈"文字后需要往右偏移的像素数（因为直接点击文字无反应）
MOMENTS_RIGHT_OFFSET = 60

# check_pyq_btn 找到后鼠标往下移的像素数（用于定位滚动区域）
CHECK_BTN_DOWN_OFFSET = 80
# 找不到 camera_icon 时最多滚动几次
CAMERA_MAX_SCROLL_ATTEMPTS = 5

# 隐私设置相关配置
PRIVACY_DIR = TEMPLATES_DIR / "privacy"
PRIVACY_TAGS_DIR = PRIVACY_DIR / "tags"
PRIVACY_MATCH_THRESHOLD = 0.45
PRIVACY_MAX_SCROLL_ATTEMPTS = 12
PRIVACY_SCROLL_DISTANCE = 350

# ============================================================
# 工具函数
# ============================================================


def random_delay(min_sec=MIN_ACTION_DELAY, max_sec=MAX_ACTION_DELAY):
    """随机等待，模拟真人操作间隔。"""
    sec = random.uniform(min_sec, max_sec)
    time.sleep(sec)


def human_like_click(x, y):
    """在目标附近随机偏移后点击，避免每次都点同一个像素。"""
    offset_x = random.randint(-8, 8)
    offset_y = random.randint(-6, 6)
    target_x = x + offset_x
    target_y = y + offset_y
    duration = random.uniform(0.15, 0.45)
    pyautogui.moveTo(target_x, target_y, duration=duration)
    pyautogui.click()
    logger.info(f"Clicked at ({target_x}, {target_y})")


def grab_screen():
    """截取当前全屏。"""
    screenshot = ImageGrab.grab()
    return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)


def find_template(template_name, threshold=MATCH_THRESHOLD, use_edge=False):
    """
    在屏幕上查找模板图片，返回中心点坐标。
    use_edge=True 时使用边缘检测匹配，对亮度/灰色变化更鲁棒。
    没找到返回 None。
    """
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
    """查找并点击模板，失败重试。"""
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
    """查找模板，然后往右偏移 offset_x 像素后再点击。"""
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


def type_path_in_file_dialog(file_path):
    """
    在 macOS 文件选择对话框中，使用 Command+Shift+G 打开“前往文件夹”，
    然后将完整文件路径通过剪贴板粘贴进去，按两次回车确认。
    """
    if not file_path or not Path(file_path).exists():
        logger.error(f"File not found: {file_path}")
        return False

    abs_path = str(Path(file_path).resolve())

    # 把路径写入剪贴板
    try:
        from AppKit import NSPasteboard, NSString
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        text = NSString.stringWithString_(abs_path)
        pb.writeObjects_([text])
    except ImportError:
        logger.error("pyobjc is required for clipboard paste")
        return False

    # 打开“前往文件夹”对话框
    pyautogui.keyDown('command')
    pyautogui.keyDown('shift')
    pyautogui.keyDown('g')
    pyautogui.keyUp('g')
    pyautogui.keyUp('shift')
    pyautogui.keyUp('command')
    random_delay(1.5, 2)

    # 粘贴路径
    pyautogui.keyDown('command')
    pyautogui.keyDown('v')
    pyautogui.keyUp('v')
    pyautogui.keyUp('command')
    random_delay(0.5, 1)

    # 第一次回车：确认路径
    pyautogui.keyDown('return')
    pyautogui.keyUp('return')
    random_delay(2, 3)

    # 第二次回车：点击“打开”按钮
    pyautogui.keyDown('return')
    pyautogui.keyUp('return')
    random_delay(2, 3)

    return True


def add_image(image_path):
    """
    在朋友圈输入框中粘贴一张图片。
    使用剪贴板文件 URL 方式。
    """
    if not image_path or not Path(image_path).exists():
        logger.warning(f"Image not found, skip: {image_path}")
        return False

    pos = find_template("text_input_area.png")
    if not pos:
        logger.error("Cannot locate text input area for image paste")
        return False

    try:
        from AppKit import NSPasteboard, NSURL

        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        url = NSURL.fileURLWithPath_(str(Path(image_path).resolve()))
        pb.writeObjects_([url])

        human_like_click(*pos)
        random_delay(0.5, 1.0)
        pyautogui.keyDown('command')
        pyautogui.keyDown('v')
        pyautogui.keyUp('v')
        pyautogui.keyUp('command')
        random_delay(2, 3)
        logger.info(f"Image pasted: {image_path}")
        return True
    except ImportError:
        logger.error("pyobjc is required for clipboard image paste: pip install pyobjc")
        return False


def add_video(video_path):
    """
    在朋友圈中添加一个视频。
    流程：点击“添加图片/视频”按钮 -> 文件选择器 -> Command+Shift+G 输入路径 -> 打开。
    """
    if not video_path or not Path(video_path).exists():
        logger.warning(f"Video not found, skip: {video_path}")
        return False

    # 点击添加图片/视频按钮
    if not click_template("add_photo_btn.png"):
        logger.warning("add_photo_btn.png not found, trying to click text input area and use shortcut...")
        # 兜底：点一下输入框，再尝试 Command+V 粘贴视频（不稳定）
        return add_image(video_path)

    random_delay(1.5, 2.5)

    # 文件选择器出现后输入路径
    if type_path_in_file_dialog(video_path):
        logger.info(f"Video added: {video_path}")
        return True

    return False


# ============================================================
# 核心流程
# ============================================================


def open_wechat():
    """
    使用 open -a WeChat 启动微信。
    如果微信已经在运行，会把窗口带到前台。
    登录需要提前完成，脚本不再等待扫码。
    """
    logger.info("Opening WeChat via 'open -a WeChat'...")
    try:
        subprocess.run(["open", "-a", "WeChat"], check=True)
        logger.info("WeChat launched/activated")
        return True
    except Exception as e:
        logger.error(f"Failed to open WeChat: {e}")
        return False


def ensure_wechat_ready():
    """确保微信已打开（不等待登录）。"""
    if not AUTO_OPEN_WECHAT:
        logger.info("AUTO_OPEN_WECHAT is disabled, assuming WeChat is already open")
        return True

    if not open_wechat():
        return False

    # 等待微信窗口加载
    time.sleep(3)
    logger.info("WeChat window should be ready. Make sure you are already logged in.")
    return True


def open_moments():
    """
    打开朋友圈页面：
    1. 点击左上角头像
    2. 找到"朋友圈"文字，往右偏移后点击（直接点文字无反应）
    """
    logger.info("Step 1: 点击头像...")
    if not click_template("profile_avatar.png"):
        logger.error("Failed to click profile avatar")
        return False

    logger.info("等待个人主页加载...")
    random_delay(2, 3)

    logger.info(f"Step 2: 找到'朋友圈'文字，往右偏移 {MOMENTS_RIGHT_OFFSET}px 后点击...")
    if not click_template_right("pyq_btn.png", offset_x=MOMENTS_RIGHT_OFFSET):
        logger.error("Failed to click Moments entry (right offset)")
        return False

    logger.info("等待朋友圈页面加载...")
    random_delay(2, 4)
    return True


def delete_previous_post():
    """
    删除上一条朋友圈。
    ⚠️ 该功能风险较高，默认关闭。
    实现依赖你自己的截图模板：post_menu.png、delete_btn.png。
    """
    if not DELETE_PREVIOUS:
        return True

    logger.info("Trying to delete previous post...")
    logger.warning("DELETE_PREVIOUS is enabled but templates are not implemented")
    return True


def choose_media():
    """
    根据 MEDIA_TYPE 配置，选择本次要发送的媒体。
    返回 (media_type, file_path)。
    media_type: "text" | "image" | "video"
    """
    if MEDIA_TYPE == "text":
        return "text", None
    elif MEDIA_TYPE == "image":
        if IMAGES_POOL:
            return "image", random.choice(IMAGES_POOL)
        logger.warning("MEDIA_TYPE=image but IMAGES_POOL is empty, fallback to text")
        return "text", None
    elif MEDIA_TYPE == "video":
        if VIDEOS_POOL:
            return "video", random.choice(VIDEOS_POOL)
        logger.warning("MEDIA_TYPE=video but VIDEOS_POOL is empty, fallback to text")
        return "text", None
    elif MEDIA_TYPE == "random":
        candidates = ["text"]
        if IMAGES_POOL:
            candidates.append("image")
        if VIDEOS_POOL:
            candidates.append("video")
        choice = random.choice(candidates)
        if choice == "image":
            return "image", random.choice(IMAGES_POOL)
        elif choice == "video":
            return "video", random.choice(VIDEOS_POOL)
        return "text", None
    else:
        logger.warning(f"Unknown MEDIA_TYPE: {MEDIA_TYPE}, fallback to text")
        return "text", None


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
    """查找并勾选一个"不给谁看"标签，找不到则向下滚动继续找。"""
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
        logger.error("No privacy tag templates found in tags/")
        return False

    logger.info(f"Found {len(tag_templates)} tag templates: {tag_templates}")
    for tag_template in tag_templates:
        if not find_and_click_privacy_tag(tag_template):
            return False

    return True


def set_privacy():
    """
    设置朋友圈隐私：点击"谁可以看" → 选"不给谁看" → 勾选标签 → 保存 → 确认。
    使用 templates/privacy/ 目录下的模板。
    """
    logger.info("=" * 40)
    logger.info(">>> set_privacy() 开始执行")

    privacy_dir = "privacy"
    privacy_threshold = PRIVACY_MATCH_THRESHOLD

    # 步骤1: 点击隐私入口（谁可以看）
    logger.info("步骤1: 查找 privacy_entry.png ...")
    pos = find_template(f"{privacy_dir}/privacy_entry.png", threshold=privacy_threshold)
    if not pos:
        logger.error("privacy_entry.png 匹配失败！请检查模板图片是否与当前界面一致")
        return False
    logger.info(f"找到 privacy_entry.png 位置: {pos}，点击中...")
    human_like_click(*pos)
    random_delay(1.5, 2.5)

    # 步骤2: 选择"不给谁看"
    logger.info("步骤2: 查找 hide_from_option.png ...")
    pos = find_template(f"{privacy_dir}/hide_from_option.png", threshold=privacy_threshold)
    if not pos:
        logger.error("hide_from_option.png 匹配失败！")
        return False
    logger.info(f"找到 hide_from_option.png 位置: {pos}，点击中...")
    human_like_click(*pos)
    random_delay(1.5, 2.5)

    # 步骤3: 勾选 tags（privacy/tags/ 目录下的标签）
    logger.info("步骤3: 勾选隐私标签 tags ...")
    if not select_privacy_tags():
        logger.warning("标签勾选失败，继续后续步骤...")

    # 步骤4: 点击"完成"按钮（标签选择页面的完成）
    logger.info("步骤4: 查找完成按钮 done_btn.png ...")
    pos = find_template(f"{privacy_dir}/done_btn.png", threshold=privacy_threshold)
    if not pos:
        logger.info("done_btn.png 未找到，尝试 confirm_btn.png ...")
        pos = find_template(f"{privacy_dir}/confirm_btn.png", threshold=privacy_threshold)
    if not pos:
        logger.error("完成按钮匹配失败！")
        return False
    logger.info(f"找到完成按钮位置: {pos}，点击中...")
    human_like_click(*pos)
    random_delay(1, 2)

    # 步骤5: 点击"保存"或"确认"按钮（最终确认）
    logger.info("步骤5: 查找最终确认按钮 ...")
    pos = find_template(f"{privacy_dir}/confirm_btn.png", threshold=privacy_threshold)
    if not pos:
        pos = find_template(f"{privacy_dir}/done_btn.png", threshold=privacy_threshold)
    if pos:
        logger.info(f"找到最终确认按钮位置: {pos}，点击中...")
        human_like_click(*pos)
        random_delay(1, 2)
    else:
        logger.info("未找到额外确认按钮，可能已在步骤4完成确认")

    logger.info("<<< set_privacy() 完成")
    logger.info("=" * 40)
    return True


def post_moment(caption, media_type="text", media_path=None):
    """发布一条朋友圈（适配点击相机图标直接弹出文件选择器的微信版本）。"""
    if not open_moments():
        logger.error("Failed to open Moments")
        return False

    random_delay(1, 2)

    # 先直接找 camera_icon（边缘检测，适应不同灰色度），找不到则通过 check_pyq_btn 滚动后再找
    if not click_template("camera_icon.png", use_edge=True):
        logger.info("camera_icon 未找到，尝试通过 check_pyq_btn 定位滚动区域...")

        # 找到 check_pyq_btn，鼠标移过去
        btn_pos = find_template("check_pyq_btn.png")
        if not btn_pos:
            logger.error("check_pyq_btn 也未找到")
            return False

        logger.info(f"找到 check_pyq_btn 位置: {btn_pos}，鼠标移过去...")
        pyautogui.moveTo(btn_pos[0], btn_pos[1], duration=random.uniform(0.2, 0.4))
        random_delay(0.3, 0.5)

        # 鼠标再往下移一段距离
        pyautogui.moveRel(0, CHECK_BTN_DOWN_OFFSET, duration=random.uniform(0.15, 0.3))
        logger.info(f"鼠标下移 {CHECK_BTN_DOWN_OFFSET}px，准备滚动...")
        random_delay(0.3, 0.5)

        # 向下滚动找 camera_icon
        for scroll_attempt in range(CAMERA_MAX_SCROLL_ATTEMPTS):
            pyautogui.scroll(-300)
            random_delay(1, 1.5)
            logger.info(f"滚动 {scroll_attempt + 1}/{CAMERA_MAX_SCROLL_ATTEMPTS}，查找 camera_icon ...")

            pos = find_template("camera_icon.png", use_edge=True)
            if pos:
                logger.info(f"找到 camera_icon 位置: {pos}，点击中...")
                human_like_click(*pos)
                break
        else:
            logger.error("滚动后仍未找到 camera_icon")
            return False

    # 某些 Mac 微信版本点击相机后直接进入文件选择器
    # 这里优先处理视频：等待文件选择器弹出后输入路径
    if media_type == "video" and media_path:
        logger.info("Video mode: waiting for file dialog...")
        random_delay(2, 3)
        if type_path_in_file_dialog(media_path):
            logger.info("Video selected, waiting for editor...")
            random_delay(3, 5)
        else:
            logger.error("Failed to select video")
            return False

    # 输入文案（通过剪贴板粘贴）
    if caption:
        pos = find_template("text_input_area.png")
        if pos:
            human_like_click(*pos)
            random_delay(0.5, 1)
            paste_text(caption)
        else:
            paste_text(caption)

    # 如果是图片，再尝试通过剪贴板或 add_photo_btn 添加
    if media_type == "image" and media_path:
        add_image(media_path)

    random_delay(1, 2)

    # 设置隐私：不给谁看（从环境变量判断是否启用）
    enable_privacy = os.environ.get("PYQ_ENABLE_PRIVACY", "1") == "1"
    if enable_privacy:
        logger.info(">>> 准备执行隐私设置...")
        if not set_privacy():
            logger.warning("Privacy setting failed or skipped, continuing to publish...")
    else:
        logger.info(">>> 隐私设置已禁用，跳过")

    random_delay(1, 2)

    # 点击发表
    if not click_template("publish_btn.png"):
        logger.error("Failed to click publish button")
        return False

    logger.info("Moment posted successfully")
    return True


def main():
    logger.info("=" * 50)
    logger.info("WeChat Moments Auto Poster starting...")
    logger.info("⚠️  Remember: high risk of account restriction/ban.")
    logger.info("=" * 50)

    if not TEMPLATES_DIR.exists():
        TEMPLATES_DIR.mkdir(parents=True)
        logger.info(f"Created templates dir: {TEMPLATES_DIR}")
        logger.info("Please put your screenshot templates there and rerun.")
        return False

    # 确保微信已打开并登录
    if not ensure_wechat_ready():
        logger.error("WeChat is not ready, exiting")
        return False

    caption = random.choice(CAPTIONS)
    media_type, media_path = choose_media()

    logger.info(
        f"Preparing single post: "
        f"type={media_type}, caption={caption[:20]}..."
    )

    if post_moment(caption, media_type, media_path):
        logger.info("Single post completed, exiting")
        return True
    else:
        logger.error("Post failed")
        return False


if __name__ == "__main__":
    try:
        sys.exit(0 if main() else 1)
    except KeyboardInterrupt:
        logger.info("Stopped by user")
        sys.exit(130)
