# 模板目录说明

本目录保存自动化识别需要用到的截图模板。程序会通过 OpenCV 在屏幕截图中查找这些模板，然后移动鼠标并点击对应位置。

## 基础模板

| 文件 | 是否必需 | 用途 |
| --- | --- | --- |
| `profile_avatar.png` | 必需 | 点击微信左上角个人头像，进入个人信息入口 |
| `pyq_btn.png` | 必需 | 识别朋友圈入口 |
| `sph_btn.png` | 视频号转发必需 | 识别视频号入口 |
| `camera_icon.png` | 发朋友圈/删除朋友圈必需 | 识别朋友圈页面相机图标或定位朋友圈内容区域 |
| `check_pyq_btn.png` | 发朋友圈必需 | 在微信侧边栏/页面中定位朋友圈入口 |
| `publish_btn.png` | 必需 | 识别并点击发表按钮 |
| `del_icon.png` | 删除朋友圈必需 | 识别删除入口图标 |
| `del_text.png` | 删除朋友圈必需 | 识别确认删除文字 |
| `sph_share_btn1.png` | 视频号转发必需 | 识别视频号视频下方分享按钮 |
| `sph_share_btn2.png` | 视频号转发必需 | 识别分享菜单里的分享到朋友圈 |
| `target_video_cover.png` | 视频号转发必需 | 当前要查找的视频号封面 |
| `text_input_area.png` | 建议提供 | 定位朋友圈文案输入区域；缺失时程序会尝试直接粘贴 |
| `add_photo_btn.png` | 图片发布时需要 | 添加图片/视频入口；不发图片时可不提供 |

## 头像库

```text
头像/
```

用于保存多个可选头像截图。GUI 中选择头像后，会复制为根目录下的：

```text
profile_avatar.png
```

## 视频封面库

```text
视频封面/
```

用于保存多个可选视频封面截图。GUI 中选择封面后，会复制为根目录下的：

```text
target_video_cover.png
```

## 隐私权限模板

隐私模板统一使用英文目录：

```text
privacy/
├── privacy_entry.png
├── hide_from_option.png
├── done_btn.png
├── confirm_btn.png
└── tags/
    ├── 1.png
    └── 2.png
```

| 文件 | 是否必需 | 用途 |
| --- | --- | --- |
| `privacy/privacy_entry.png` | 开启隐私时必需 | 点击“谁可以看/公开”等权限入口 |
| `privacy/hide_from_option.png` | 开启隐私时必需 | 点击“不给谁看”选项 |
| `privacy/done_btn.png` | 开启隐私时必需 | 标签选择完成按钮 |
| `privacy/confirm_btn.png` | 开启隐私时必需 | 权限设置确认按钮 |
| `privacy/tags/*.png` | 开启隐私标签时必需 | 需要勾选的标签截图，按文件名顺序逐个查找 |

`privacy/tags/*.png` 通常包含账号隐私信息，仓库默认忽略这些图片，只保留 `.gitkeep`。

## 截图建议

- 截图范围尽量小，只包含按钮或标签本体。
- 不要截太大的区域，避免窗口尺寸变化后匹配失败。
- 同一台电脑上重新校准模板最稳定。
- 换电脑、换微信版本、换显示器缩放后，如果识别失败，应重新截图。
- 深色模式和浅色模式的模板不能混用。

