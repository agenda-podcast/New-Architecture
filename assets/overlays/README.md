# Texture Overlays

PNG texture overlays for cinematic effects.

## Format

- PNG with alpha channel
- Minimum 1920x1080 (4K preferred)
- Seamlessly tileable (for grain)

## Subdirectories

- `grain/` - Film grain textures
- `dust/` - Dust and scratch effects
- `light-leaks/` - Light leak effects

## Required Overlays

### Grain
- [ ] `grain/grain-fine.png` - Fine grain
- [ ] `grain/grain-medium.png` - Medium grain
- [ ] `grain/grain-coarse.png` - Coarse grain

### Dust
- [ ] `dust/dust-light.png` - Light dust particles
- [ ] `dust/dust-heavy.png` - Heavy dust with scratches

### Light Leaks
- [ ] `light-leaks/leak-warm.png` - Warm tones
- [ ] `light-leaks/leak-cool.png` - Cool tones

## Sources

- **ProductionCrate**: https://productioncrate.com/ (free section)
- **FootageCrate**: https://footagecrate.com/ (free section)
- **Custom**: Create in Photoshop/GIMP

## Usage

In Blender Compositor:
1. Load as Image node
2. Mix with base image (Overlay/Screen/Add mode)
3. Factor: 0.05-0.30 for subtle effect

## License

All overlays must be:
- Free for commercial use
- Properly attributed
- CC0 or CC-BY preferred

See LICENSE.txt in each subdirectory.
