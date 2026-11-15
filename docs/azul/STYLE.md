# Azul explainers: shared visual style

The look follows the game itself (box, rulebook, player boards, factory displays and bag): light, warm
parchment and cream surfaces, Portuguese azulejo blues, ochre-gold accents and dark-red headings. It
should feel like sitting at an Azul table, not like an app.

All artwork is **original**: simple flat geometric shapes drawn in code. Do not trace or copy the game's
printed tile art, logo, board artwork or factory display art.

## Palette

| Token | Hex | Used for |
|---|---|---|
| parchment | #EFE4CF | table / background (with soft mottling and a gentle vignette) |
| cream | #FAF5EA | panels, cards, caption plaques, player boards |
| sand | #EAD9BE | empty pattern-line slots, box-lid well |
| wall tray | #E6D6B8 | tray under the wall |
| deep blue | #1E3A72 | frames, board header band, score bar, "Next" pill, titles |
| cobalt | #2C5AA8 | floor-line slot edges, azulejo borders, factory centres |
| light blue | #9CC0E3 | azulejo borders, score-track ticks, "down" count badges |
| ochre-gold | #C08A2E | thin inner frame lines, ornamental rules (decoration only, never text) |
| gold on blue | #F4CD78 | text on deep blue (round label, box-lid count, active player name) |
| dark red | #9E2A22 | card headings ("Remember", "Five colours"), caption sub-lines, floor penalties |
| highlight red | #B32A1E | highlight frames, spotlight frames, arrows, negative pop-ups (like the rulebook) |
| ink | #1B2A4E | body text |
| warm brown | #68543C | small labels (PATTERN LINES, WALL, FLOOR LINE, CENTRE OF THE TABLE) |
| ochre plaque | #F1B852 | score number plaque, "+N" pop-ups, "across" count badges |

Contrast (WCAG): ink on parchment 11:1, warm brown labels 5.7:1, dark red on cream 6.9:1, light blue
and gold text on deep blue 5.8:1 and 7.3:1, pop-up text 8:1 or more. Gold is never used for text on a
light background.

## Fonts

Bundled in `tools/azul/fonts/` (Latin subsets, SIL Open Font License, see `OFL.txt`):

- **Cinzel Bold**: titles, card headings, caption key words, board names, BAG / BOX LID.
- **Caladea** Regular and Bold (a classic book serif, close to the rulebook's text face): everything else.

## Tiles

| Colour | Letter | Fill | Motif (centred, in the mark colour) |
|---|---|---|---|
| blue   | B | #2F62AC | ring with a centre dot, light blue |
| yellow | Y | #E9A238 | four-petal rosette with four dots, red-orange |
| red    | R | #D2492F | diamond with a diamond window, pale cream |
| black  | K | #24272F | lattice: plus sign and four small diamonds, light teal-blue |
| white  | W | #F4EFE2 (with #8FA8C4 outline) | eight-ray star of slim rhombi, light blue |

- Every tile also shows its letter (B Y R K W) in the bottom-left corner, so colour is never the only cue.
  Tiles have a thin inset frame and a soft glaze highlight along the top.
- Starting player marker: a cream tile with a deep-blue frame and the numeral "1".
- Wall spaces not yet tiled: a faint version of the colour, at about 35% strength, with the same motif.
- Grey-wall variant spaces: plain warm grey #C4BEB4.

## Components

- Player board: cream surface in a deep-blue frame with a gold inner line. A deep-blue header band
  holds the name, the 0-100 score track and the score on an ochre plaque. Pattern-line slots are sand
  with gold-tan edges; deep-blue arrows point to the wall; the floor line has cobalt-edged slots with
  the penalties printed under them in dark red: −1 −1 −2 −2 −2 −3 −3.
- Factory display: terracotta rim (#B05E34), cream ring with a circle of deep-blue beads, a gold ring
  and a cobalt centre with light rays.
- Centre of the table: a lighter parchment area with a thin gold-tan edge.
- Bag: washed cotton blue (#4F7CBE) with a cream print of small stars and diamonds, a cream drawstring
  and a cream label plaque.
- Box lid: deep blue with a light-blue inner line and a sand well for the tiles.

## Video overlays and cards

- Title card: azulejo-tile bands along the top and bottom, a cream panel in a deep-blue frame, kicker
  in dark red, title in Cinzel deep blue, subtitle in dark red, then the five tiles.
- "Remember" card: cream panel in a deep-blue frame, dark-red heading, small tile bullets. "Next: …" is a
  deep-blue pill with a gold edge and cream text.
- Captions: cream plaque in a deep-blue frame with a gold inner line; key word in Cinzel deep blue,
  sub-line in Caladea dark red.
- Arrows: highlight red with a cream halo and a red label pill (cream text), like the rulebook's arrows.
- Spotlight: the rest of the picture is washed with pale cream; the focus gets a highlight-red frame.
- Pop-ups: "+N" on an ochre pill with a deep-blue edge; "−N" on a highlight-red pill with cream text.
- Score bar: deep blue with a gold top edge; round text in gold, scores in cream.

## Words

Use the names in docs/azul/manual.md exactly (factory display, centre of the table, pattern line, wall,
floor line, box lid, starting player marker, score track).

## Status

The videos (`tools/azul/render.py`, `anim.py`) follow this file. The colour PDF
(`tools/build_azul_color_manual.py`) and the practice page (`docs/azul/learn.html`) still use the
earlier flat tile palette (blue #2F6FB5, yellow #E8B730, red #C8423A, black #2A2D34, white #EEF1F4 with
circle / four-point star / diamond / plus / square-ring marks); update them to this style when they are
next rebuilt.
