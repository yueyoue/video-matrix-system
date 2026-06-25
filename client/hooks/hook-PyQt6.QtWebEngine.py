"""PyInstaller hook for PyQt6-WebEngine - ensures Qt binaries are bundled."""
from PyInstaller.utils.hooks import collect_all, collect_submodules

# Collect all PyQt6-WebEngine data files, binaries and submodules
datas_binaries, binaries, hiddenimports = collect_all('PyQt6.QtWebEngine')

# Also collect WebEngineCore and WebEngineWidgets
for mod in ['PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebEngineQuick']:
    d, b, h = collect_all(mod)
    datas_binaries.extend(d)
    binaries.extend(b)
    hiddenimports.extend(h)

# Deduplicate
hiddenimports = list(set(hiddenimports))
