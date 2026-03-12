# BrickBuilder

A Blender addon for searching, importing, and placing LEGO parts directly from the LDraw library and Rebrickable database — right inside the 3D viewport.

BrickBuilder is part of the **BrickSuite** ecosystem, designed to work alongside EpicFigRig and other BrickSuite tools to create a complete LEGO animation pipeline in Blender.

> **Note:** EpicFigRig integration (automatic rigging of LDraw-imported parts) is **not yet available in v1.0**. LDraw imports at a different scale than Mecabricks exports, so AutoRig will not work correctly on parts placed by BrickBuilder yet. This is a known limitation and full EpicFigRig integration is planned for a future update.

---

## Features

- Search Rebrickable's parts library by name or part number
- Search the bundled LDraw parts index (22,000+ parts) simultaneously
- Results merged into a single thumbnail grid
- Filter results to minifig parts only
- Color picker with full Rebrickable color list and live search filter
- Place any part at the 3D cursor with one click
- Automatic stud snapping to the nearest existing part
- Full minifig assembly import — search `979` and place a complete standing minifigure
- LDraw shortcut files (assemblies) are automatically detected and imported as grouped objects
- Thumbnails fetched from Rebrickable CDN and cached locally
- Missing parts fetched live from the LDraw CDN (gkjohnson's mirror)

---

## Requirements

- Blender 5.0 or later
- A free Rebrickable API key — get one at [rebrickable.com/api](https://rebrickable.com/api)
- Internet connection for first-time part and thumbnail downloads

---

## Installation

1. Download the latest `BrickBuilder.zip` from the Releases page
2. In Blender go to **Edit → Preferences → Add-ons → Install**
3. Select the downloaded zip
4. Enable **BrickBuilder** in the addon list
5. Open preferences and paste your Rebrickable API key

The addon panel appears in the **Brick Suite** tab in the 3D viewport sidebar (press **N** to open).

---

## Usage

### Searching for Parts

Type a part name or number into the search box and press the refresh button. Results from both Rebrickable and the bundled LDraw index appear together in the thumbnail grid.

Parts sourced only from LDraw (like full minifig assemblies) show a **LDraw assembly** badge below the grid when selected.

Enable **Minifig parts only** to filter results to minifig-related categories.

### Placing a Part

1. Select a part in the grid
2. Choose a color from the color picker (click **Load Colors** on first use)
3. Click **Place Part**

The part appears at the 3D cursor. If another mesh is selected, BrickBuilder will attempt to snap the new part to the nearest stud automatically.

### Placing a Full Minifigure

Search for `979` — this is the LDraw shortcut for a complete standing minifigure. Select it and click **Place Part**. All sub-parts (torso, head, arms, legs, hands) import together and are grouped under a single Empty object so the whole figure moves as a unit.

### Colors

Click **Load Colors** in the color picker to fetch the full Rebrickable color list. Use the search field to filter by name. The color you select is applied to the part on import using the LDraw color code system.

---

## LDraw Parts Index

BrickBuilder ships with a bundled `parts.lst` index covering 22,000+ parts. This enables offline LDraw search with no setup required.

To update the index with a newer or more complete parts list, replace `parts.lst` in the addon folder with a freshly generated one. LDraw users can generate this file using `mklist.exe` from their LDraw installation, or the community can contribute updated files via pull request.

---

## Credits

**BrickBuilder** was built as part of the BrickSuite project.

**LDraw import engine** is based on the ExportLDraw addon by **Matthew Morrison (cuddlyogre)**
[github.com/cuddlyogre/ExportLDraw](https://github.com/cuddlyogre/ExportLDraw)
which was itself inspired by **ImportLDraw** by **Toby Lobster**
[github.com/TobyLobster/ImportLDraw](https://github.com/TobyLobster/ImportLDraw)

**LDraw parts CDN** provided by **gkjohnson's ldraw-parts-library mirror**
[github.com/gkjohnson/ldraw-parts-library](https://github.com/gkjohnson/ldraw-parts-library)

**Part data and thumbnails** provided by the **Rebrickable API**
[rebrickable.com](https://rebrickable.com)

**LDraw parts library** maintained by the **LDraw community**
[ldraw.org](https://www.ldraw.org)

**EpicFigRig** — the rigging system BrickBuilder is designed to work with — created by
**Reecey Bricks**, **JabLab**, **IX Productions**, **Citrine's Animations**, **Jambo**, **Owenator Productions**, and **Golden Ninja Ben**
[github.com/BlenderBricks/EpicFigRig](https://github.com/BlenderBricks/EpicFigRig)

---

## Contributing

Pull requests are welcome. See `DEVELOPER.md` for package structure, design decisions, and contribution guidelines.

If you have a more complete `parts.lst`, submitting it as a PR is one of the easiest ways to improve LDraw search coverage for everyone.

---

## License

BrickBuilder is released under the **GNU General Public License v3.0**.
See `LICENSE` for full terms.

LDraw parts data is licensed under the **Creative Commons Attribution License (CC BY 4.0)**.
Rebrickable data is subject to [Rebrickable's terms of service](https://rebrickable.com/api).
