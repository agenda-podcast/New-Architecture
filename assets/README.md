# Cinematic Assets for Video Rendering

This directory contains high-quality assets used by Blender templates for cinematic effects.

## Directory Structure

```
assets/
├── luts/                    # Color grading LUTs (.cube files)
├── overlays/                # Texture overlays
│   ├── grain/              # Film grain textures
│   ├── dust/               # Dust and scratch overlays
│   └── light-leaks/        # Light leak effects
├── fonts/                   # Typography fonts (.ttf, .otf)
└── README.md               # This file
```

## Asset Categories

### 1. LUTs (Look-Up Tables)

**Purpose**: Color grading and film emulation

**Format**: `.cube` files (standard 3D LUT format)

**Required LUTs**:
- `neutral.cube` - Neutral/clean color grade (safe)
- `kodak-5219.cube` - Kodak film emulation (cinematic)
- `fuji-eterna.cube` - Fuji film emulation (cinematic)
- `teal-orange.cube` - Hollywood blockbuster look (cinematic)
- `vintage-warm.cube` - Warm vintage look (cinematic)
- `noir.cube` - High-contrast black and white (experimental)

**License Requirements**: 
- CC0 (Public Domain) preferred
- CC-BY with attribution accepted
- Open source compatible licenses

**Sources**:
- RocketStock Free LUTs
- Color Grading Central
- LUT Heaven (free section)
- Create custom LUTs in DaVinci Resolve (export as .cube)

### 2. Overlays

#### Grain Overlays

**Purpose**: Add film grain texture

**Format**: PNG with alpha channel (1920x1080 or higher)

**Required**:
- `grain-fine.png` - Fine grain (5-10% intensity)
- `grain-medium.png` - Medium grain (10-20% intensity)
- `grain-coarse.png` - Coarse grain (20-30% intensity)

**Characteristics**:
- Grayscale images
- Seamlessly tileable
- Various grain sizes

#### Dust Overlays

**Purpose**: Vintage film dust and scratches

**Format**: PNG with alpha channel (1920x1080 or higher)

**Required**:
- `dust-light.png` - Light dust particles
- `dust-heavy.png` - Heavy dust with scratches

**Characteristics**:
- White particles on transparent background
- Applied with low opacity (10-30%)

#### Light Leaks

**Purpose**: Vintage film light leaks

**Format**: PNG with alpha channel (1920x1080 or higher)

**Required**:
- `leak-warm.png` - Orange/yellow light leaks
- `leak-cool.png` - Blue/cyan light leaks
- `leak-mixed.png` - Multi-color leaks

**Characteristics**:
- Soft, glowing edges
- Transparent gradient
- Applied with screen/add blend mode

### 3. Fonts

**Purpose**: Titles, lower thirds, text overlays

**Format**: TrueType (.ttf) or OpenType (.otf)

**Required**:
- **Title font**: Bold, impactful (e.g., Montserrat Bold)
- **Body font**: Clean, readable (e.g., Inter Regular)

**License Requirements**:
- Open Font License (OFL) preferred
- 100% Free for commercial use

**Sources**:
- Google Fonts
- Font Squirrel (100% free section)
- League of Moveable Type

## Asset Guidelines

### Quality Standards

1. **Resolution**:
   - Overlays: Minimum 1920x1080, preferably 4K
   - LUTs: Standard 32x32x32 or 64x64x64 cube

2. **File Size**:
   - Overlays: < 10 MB per file
   - LUTs: < 1 MB per file
   - Fonts: < 500 KB per file

3. **Format Compliance**:
   - LUTs: Standard `.cube` format (parseable by Blender)
   - Overlays: PNG with proper alpha channel
   - Fonts: TrueType or OpenType

### License Compliance

All assets must have:

1. **License file**: `LICENSE.txt` in each subdirectory
2. **Attribution**: `ATTRIBUTION.txt` with source credits
3. **Usage notes**: `README.md` with usage guidelines

**Acceptable Licenses**:
- CC0 (Public Domain)
- CC-BY (Attribution required)
- Open Font License (OFL)
- MIT/BSD-style licenses
- Explicitly free for commercial use

**Unacceptable**:
- All rights reserved
- Non-commercial only
- Share-alike restrictions (CC-BY-SA) - conflicts with MIT
- Unknown/unclear licenses

## Adding New Assets

### Step 1: Find Asset

Find high-quality assets from reputable sources:
- **LUTs**: RocketStock, Color Grading Central, Resolve presets
- **Overlays**: ProductionCrate, FootageCrate (free sections)
- **Fonts**: Google Fonts, Font Squirrel

### Step 2: Verify License

1. Check license page on source website
2. Verify commercial use is allowed
3. Note attribution requirements
4. Download license file if available

### Step 3: Download and Process

1. Download asset
2. Process if needed:
   - Resize overlays to 1920x1080
   - Convert LUTs to `.cube` format
   - Test fonts for completeness
3. Optimize file size
4. Verify quality

### Step 4: Document

Create or update files in asset directory:

```
assets/luts/
├── my-lut.cube
├── LICENSE.txt          # License info
├── ATTRIBUTION.txt      # Source and credits
└── README.md            # Usage notes
```

**LICENSE.txt** example:
```
License: CC0 1.0 Universal (Public Domain)
Source: https://example.com/free-luts
Downloaded: 2025-12-19

This asset is released into the public domain.
You can copy, modify, and distribute without attribution.
```

**ATTRIBUTION.txt** example:
```
Asset: Kodak 5219 Film Emulation LUT
Creator: John Doe
Source: https://example.com/lut-pack
License: CC-BY 4.0
Attribution Required: Yes

Credit: "Kodak 5219 LUT by John Doe (example.com)"
```

### Step 5: Test

Test asset in Blender:
1. Import into template
2. Apply to test footage
3. Verify appearance and performance
4. Check for artifacts

### Step 6: Commit

Add asset to repository:
```bash
git add assets/luts/my-lut.cube
git add assets/luts/LICENSE.txt
git add assets/luts/ATTRIBUTION.txt
git commit -m "Add Kodak 5219 film emulation LUT"
```

## Asset Inventory

### Current Assets

**Status**: Placeholder structure created - assets need to be added

**Priority Assets** (add first):
1. `luts/neutral.cube` - Essential for safe templates
2. `overlays/grain/grain-fine.png` - Most commonly used
3. `fonts/montserrat-bold.ttf` - Title font
4. `fonts/inter-regular.ttf` - Body font

**Nice-to-Have Assets**:
1. Film emulation LUTs (Kodak, Fuji)
2. Creative LUTs (teal-orange, vintage)
3. Dust/scratch overlays
4. Light leak effects

## Usage in Templates

### LUTs

In Blender Compositor:

```
Input Image
  → RGB Curves (pre-adjustment)
  → Vector Curves (LUT applied here)
  → Color Balance (post-adjustment)
  → Output
```

**Application**:
1. Load LUT using "Color Management" → "Look"
2. Or use Vector Curves node with LUT file
3. Adjust intensity with Mix RGB node (0.0-1.0)

### Overlays

In Blender Compositor:

```
Base Image
  → Mix RGB (with overlay, mode: Overlay/Screen/Add)
  → Overlay Image (grain/dust/leak)
  → Output
```

**Application**:
1. Load overlay as Image node
2. Mix with base using appropriate blend mode
3. Adjust factor for intensity (0.05-0.30 typical)

### Fonts

In Blender Text Objects or VSE:

1. Load font: Blender → Fonts → Load External Font
2. Create text strip in VSE
3. Assign font to text
4. Animate as needed

## Testing Assets

### Visual Quality Test

```bash
# Test LUT
blender --background --python test_lut.py -- assets/luts/my-lut.cube

# Test overlay
blender --background --python test_overlay.py -- assets/overlays/grain/grain-fine.png
```

### Performance Test

Check render time impact:
1. Render test video without asset
2. Render test video with asset
3. Compare render times
4. Asset should add < 10% render time

### Artifact Check

Look for:
- Banding in LUTs
- Tiling issues in overlays
- Font rendering problems
- Color space issues

## Troubleshooting

### "LUT not applying"

**Problem**: LUT file not recognized

**Solution**:
1. Verify `.cube` format (not `.3dl` or other)
2. Check file encoding (UTF-8)
3. Test LUT in other software (DaVinci Resolve)
4. Regenerate LUT from source

### "Overlay looks wrong"

**Problem**: Overlay appears too dark/bright

**Solution**:
1. Check alpha channel is present
2. Adjust blend mode (Overlay, Screen, Add)
3. Reduce factor/opacity
4. Verify color space (sRGB)

### "Font missing glyphs"

**Problem**: Some characters don't render

**Solution**:
1. Check font supports required character set
2. Use fallback font for missing glyphs
3. Choose font with wider Unicode support

## License Summary

See `LICENSE-SUMMARY.md` for complete license information on all assets.

**Key Points**:
- All assets are free for commercial use
- Attribution required where specified
- No share-alike restrictions
- Compatible with MIT license of this project

## Contributing

To contribute assets:

1. Find high-quality, openly licensed asset
2. Verify license compatibility
3. Process and test asset
4. Document license and attribution
5. Submit PR with asset + documentation

See `CONTRIBUTING.md` for details.

---

**Status**: Directory structure created, assets need to be sourced  
**Priority**: Medium (templates can work without assets initially)  
**Next Steps**: Source and add priority assets listed above
