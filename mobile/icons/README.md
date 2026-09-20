# Mobile PWA icons

Real PNG icons live here:

- `icon-192.png` — 192×192 home-screen icon (Android + iOS)
- `icon-512.png` — 512×512 splash / maskable icon

Until design ships the 熊宝 mascot exports, this directory is kept under version
control with a 1×1 transparent PNG so the manifest resolves at build time. The
placeholder must be replaced before the PWA is shipped to a public CDN.

The brand image generation pipeline (`octop/contrib/workbuddy/console/assets/brand/process_images.py`)
is the source of truth; reuse it for the mobile assets too.
