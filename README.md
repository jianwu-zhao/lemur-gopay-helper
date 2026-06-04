# Lemur GoPay LongLink Helper

一个适配 **Lemur 手机浏览器** 的 GoPay/支付长链解析插件。

## 功能
- 自动识别当前页面 URL 中的长链
- 识别页面正文里的嵌套链接
- 多层 `decodeURIComponent` 解码
- 提取 `url / redirect / target / deeplink / open_url` 等常见参数
- 一键复制真实链接
- 一键在新标签页打开
- 可开关自动复制
- 可开关自动打开
- 可优先选择 `gopay://`、`gojek://`、`intent://` 深链

## 安装到 Lemur
1. 下载 `lemur-gopay-helper.zip`
2. 打开 Lemur
3. 进入扩展管理
4. 导入 zip 或解压目录

## 使用
1. 在 Lemur 打开 GoPay 长链页面
2. 点浏览器扩展按钮
3. 查看解析到的真实链接
4. 点“复制”或“打开”

## 自动模式
插件默认不会自动打开链接。你可以在弹窗里开启：
- 发现链接后自动复制
- 发现链接后自动打开
- 优先 GoPay/Gojek/Intent 深链

建议只在可信页面开启自动打开。

## 文件
- `manifest.json`
- `popup.html`
- `popup.js`
- `content.js`
- `background.js`
- `shared.js`
