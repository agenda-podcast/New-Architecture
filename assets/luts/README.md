# LUTs (Look-Up Tables)

Color grading LUTs for cinematic effects.

## Format

- `.cube` files (standard 3D LUT format)
- 32x32x32 or 64x64x64 resolution
- sRGB color space

## Required LUTs

- [ ] `neutral.cube` - Neutral/clean color grade
- [ ] `kodak-5219.cube` - Kodak film emulation
- [ ] `teal-orange.cube` - Hollywood blockbuster look
- [ ] `vintage-warm.cube` - Warm vintage look
- [ ] `noir.cube` - High-contrast B&W

## Sources

- **RocketStock Free LUTs**: https://www.rocketstock.com/free-after-effects-templates/35-free-luts-for-color-grading-videos/
- **Color Grading Central**: Free section
- **Custom**: Create in DaVinci Resolve and export as `.cube`

## Usage

In Blender Compositor, use Vector Curves node to apply LUT:
1. Add Vector Curves node
2. Load `.cube` file
3. Mix with original (0.5-1.0 factor)

## License

All LUTs must be:
- Free for commercial use
- CC0 or CC-BY licensed
- Properly attributed in ATTRIBUTION.txt

See LICENSE.txt for details on each LUT.
