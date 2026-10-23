[app]

title = Pixel Chess
package.name = pixelchess
package.domain = org.pixelchess
source.dir = .
source.include_exts = py,kv,png,jpg,atlas,txt,wav,ttf
source.exclude_dirs = venv,.git,.buildozer,__pycache__
version = 1.0.0
requirements = python3,kivy==2.3.1,python-chess==1.999
orientation = portrait
fullscreen = 0
android.api = 36
android.minapi = 24
android.ndk = 28c
android.archs = arm64-v8a
android.accept_sdk_license = True
icon.filename = assets/pixelchess-icon.png
presplash.filename = assets/presplash.jpg
android.presplash_color = #141413
p4a.branch = develop
license = GPL-3.0-only

[buildozer]
log_level = 2
warn_on_root = 1
