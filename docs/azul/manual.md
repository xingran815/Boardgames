# Azul — Player Manual

*A game for 2 to 4 players · about 30–45 minutes · Game design by Michael Kiesling · Plan B Games / Next Move (German edition: Pegasus Spiele)*

This is an unofficial, plain-language player manual. It explains the complete rules in our own words for people who have never played a board game. It also adds a FAQ and some beginner tips. It follows the German rulebook (2018). That rulebook gives the same numbers as the published English rules. Where the rules are silent, this manual says so and marks its suggestion as a **house rule**.

Every point value in this manual was checked with the rules engine in `tools/azul/engine.py`.

---

## 1. The Story

Long ago, a king of Portugal saw the beautiful glazed wall tiles of a Spanish palace and wanted the same for his own palace. In Azul, you are a tile-layer decorating that palace wall.

---

## 2. Goal of the Game

Each player has their own **wall** to decorate, on their own **player board**. Every round, players take turns collecting **tiles** from the middle of the table. Tiles you collect wait in rows on your board until a row is full. At the end of each round, one tile from every full row moves onto your wall and scores points. Tiles you collect but cannot use cost you points.

The game ends after the round in which someone fills a complete horizontal row of their wall (5 tiles side by side). After some bonus points, **the player with the most points wins**.

### Words used in this manual

- **Turn:** one player's go. Players take turns one after another.
- **Clockwise:** the next player is the one on your left. Turns go around the table this way.
- **Round:** one cycle of the game: collect tiles, move tiles to walls, prepare the next round. A game has several rounds (usually 5 or 6).
- **Draw:** reach into the bag without looking and take tiles out at random.

All other game words are explained in section 3 when they first appear.

---

## 3. Components

| Item | Count | What it is |
|---|---|---|
| Tiles | 100 | Square plastic tiles, **20 in each of 5 colours** (see below). |
| Bag | 1 | A cloth bag. Tiles are drawn from it at random. |
| Factory displays | 9 | Round cardboard discs. Tiles are put on them to offer them to players. You use 5, 7 or 9 of them, depending on the number of players. |
| Player boards | 4 | One per player. Each board has two sides: a **coloured side** (normal game) and a **grey side** (variant, section 11). |
| Score markers | 4 | Small black cubes, one per player, that show your points on the score track. |
| Starting player marker | 1 | A square token with a "1" on it. It is **not** a tile and never goes on a wall. |

> **Edition note:** the photographed German rulebook has no separate component list. The counts of tiles (100, 20 per colour) and factory displays (up to 9) are stated in its setup. The 4 player boards and 4 score markers follow from the 4-player maximum and match the published English component list.

The box lid is also used during play: tiles that leave the game for a while are put in it (section 8).

**The five tile colours.** In this manual each colour also has a letter, so you never need colour alone:

| Letter | Colour | Look |
|---|---|---|
| B | blue | plain dark blue |
| Y | yellow | yellow with an orange-red pattern |
| R | red | plain red |
| K | black | black with a blue-green pattern |
| W | white | white with a light-blue snowflake (some players call it "light blue" or "turquoise") |

### Your player board

Every player board has the same four areas:

- **Score track:** the numbered spaces 0 to 100 along the edge. Your score marker moves along it.
- **Pattern lines:** five rows of empty spaces on the left, shaped like a staircase. Line 1 (top) has 1 space, line 2 has 2, line 3 has 3, line 4 has 4 and line 5 (bottom) has 5. Tiles you collect wait here.
- **Wall:** the 5 × 5 grid of spaces on the right. Each space on the coloured side shows the colour of the tile that belongs there. An arrow joins each pattern line to the **row** of the wall beside it: pattern line 1 belongs to wall row 1, line 2 to row 2, and so on.
- **Floor line:** seven spaces along the bottom. Each space has a minus number printed above it: **−1 −1 −2 −2 −2 −3 −3** (from left to right). Tiles you cannot use go here and cost points.

In this manual, a **row** of the wall goes across (left to right) and a **column** goes down (top to bottom). Rows and columns are numbered 1 to 5, from the top and from the left.

**The coloured wall.** Every row holds each of the 5 colours exactly once, and so does every column. Each row is the row above it shifted one space to the right:

| | Column 1 | Column 2 | Column 3 | Column 4 | Column 5 |
|---|---|---|---|---|---|
| Row 1 | blue (B) | yellow (Y) | red (R) | black (K) | white (W) |
| Row 2 | white (W) | blue (B) | yellow (Y) | red (R) | black (K) |
| Row 3 | black (K) | white (W) | blue (B) | yellow (Y) | red (R) |
| Row 4 | red (R) | black (K) | white (W) | blue (B) | yellow (Y) |
| Row 5 | yellow (Y) | red (R) | black (K) | white (W) | blue (B) |

---

## 4. Setup

1. **Player boards.** Each player takes a player board and puts it in front of them with the **coloured side** up. **All players use the same side**: either everyone plays on the coloured side, or everyone plays on the grey side (variant, section 11). **All player boards are identical**: everyone has the same wall pattern, the same pattern lines and the same floor line.
2. **Score markers.** Each player puts a score marker on space **0** of their score track.
3. **Factory displays.** Put factory displays in a circle in the middle of the table. The space inside the circle is the **centre of the table** (or just "the centre"). The number of factory displays depends on the number of players:

   | Players | 2 | 3 | 4 |
   |---|---|---|---|
   | Factory displays | 5 | 7 | 9 |

4. **Bag.** Put all 100 tiles in the bag and mix them.
5. **Starting player.** Choose who starts. (The rulebook suggests: whoever visited Portugal most recently.) That player is the **starting player** and takes the starting player marker.
6. **Fill the factory displays.** The starting player draws tiles from the bag and puts **exactly 4 tiles** on each factory display. Then put the bag aside.
7. Put unused player boards, score markers and factory displays back in the box. Keep the box lid nearby, empty.

You are ready to play.

---

## 5. How a Round Works

Every round has three phases, always in this order:

- **A. Factory offer:** players take turns collecting tiles and putting them on their pattern lines (section 6).
- **B. Wall-tiling:** full pattern lines move one tile to the wall and score; the floor line costs points (sections 7 and 8).
- **C. Preparing the next round:** refill the factory displays (section 9).

Then a new round begins with phase A, unless the game has ended (section 10).

---

## 6. Phase A: Factory Offer

At the start of this phase, the starting player puts the **starting player marker in the centre of the table**. Then the starting player takes the first turn. Turns go clockwise.

On your turn you **must take tiles**. Choose **one** of these two options:

**Option 1: take from a factory display.** Pick any factory display that has tiles. Pick one colour on it. Take **all** tiles of that colour from that display. Then push all the other tiles on that display into the centre of the table. The display is now empty.

**Option 2: take from the centre.** Pick one colour in the centre. Take **all** tiles of that colour from the centre. Leave the other tiles there.
If you are the **first player this round** to take tiles from the centre, you also take the **starting player marker**. Put it on the **leftmost empty space of your floor line**. It costs you points like a tile (section 8), but it also makes you the starting player of the next round.

You can't take only some tiles of a colour, and you can't take two colours.

### Placing the tiles you took

Right away, put **all** the tiles you just took into **one** of your five pattern lines:

- Fill the line **from right to left**: the first tile goes in the space next to the wall.
- A pattern line holds **one colour only**. If the line already has tiles, you may only add tiles of that same colour.
- You may **not** put a colour into a pattern line if the wall row beside that line **already has a tile of that colour**.
- When every space of a pattern line is filled, the line is **complete**.
- If you took more tiles than the line has empty spaces, fill the line and put the extra tiles on your **floor line**.

Instead of a pattern line, you may put all the tiles you took straight onto your floor line. You must do this if no pattern line can take that colour.

**The floor line.** Tiles go onto the floor line **from left to right**, into the leftmost empty space. They count as broken, and each costs the points printed above its space. If all 7 floor spaces are full, any further tiles go into the **box lid** instead. They cost nothing extra.

**Your aim in this phase:** complete as many pattern lines as you can. Only complete lines put tiles on your wall, and only tiles on the wall score points.

### End of phase A

Phase A ends when **every factory display and the centre of the table are empty**. Turns may go around the table several times before that happens.

### Example turns

1. Peter takes the 2 black tiles from a factory display. That display also had 1 yellow and 1 white tile; Peter pushes those into the centre.
2. Martin takes 1 yellow tile from another factory display and pushes its 3 red tiles into the centre.
3. Andrea takes the 3 red tiles from the centre. She is the first player this round to take from the centre, so she also takes the starting player marker and puts it on the leftmost space of her floor line.

### Example: where can the tiles go?

Andrea takes 2 yellow tiles. Her wall already has yellow in rows 2 and 3, and her pattern line 4 has 1 blue tile.

- Lines 2 and 3: **not allowed** (yellow is already in those wall rows).
- Line 4: **not allowed** (it already holds blue).
- Line 1: allowed. 1 yellow fills it; the second yellow goes to her floor line.
- Line 5: allowed. Both yellow tiles go there (3 spaces stay empty).
- Floor line: allowed. Both yellow tiles go on the floor line.

---

## 7. Phase B: Wall-Tiling and Scoring

All players can do this phase **at the same time**, each on their own board.

1. Go through your pattern lines **from top to bottom** (line 1 first, line 5 last).
2. For each **complete** pattern line: move its **rightmost tile** onto the wall space of **the same colour** in the row beside it. Score that tile right away (see below).
3. Skip every pattern line that is not complete. Its tiles stay where they are for the next round.
4. When you have gone through all five lines: from every pattern line whose rightmost space is now empty (the ones you just moved a tile from), put the remaining tiles in the **box lid**. Only those lines are emptied.
5. Score your floor line (section 8).

### How a new wall tile scores

Score each tile at the moment it is placed. Tiles placed earlier this phase (higher rows) already count.

- **No neighbours:** if the new tile does not touch any other tile on the wall horizontally or vertically, it scores **1 point**. (Touching only at a corner does not count.)
- **With neighbours:** otherwise, count two things:
  - **Across:** if the new tile touches a tile to its left or right, count all tiles in the unbroken line across that includes the new tile. Score that many points.
  - **Down:** if the new tile touches a tile above or below it, count all tiles in the unbroken line down that includes the new tile. Score that many points too.

  An empty space stops the count. If a tile has neighbours both across and down, it scores both counts, so it counts itself twice.

Move your score marker forward by the points right away.

### Scoring examples

- A tile with no neighbours: **1 point**.
- A yellow tile placed in row 2, with red and black right beside it: the unbroken line across is 3 tiles. **3 points.**
- A blue tile placed in row 3, with a yellow tile directly above it and nothing beside it: the unbroken line down is 2 tiles. **2 points.**
- A yellow tile placed in row 3, column 4. Across, it joins white, blue and red to make an unbroken line of 4. Down, it joins black and red above it to make an unbroken line of 3. **4 + 3 = 7 points.**
- Peter's complete lines are line 2 (2 red tiles) and line 4 (4 blue tiles). His wall is empty. Red goes to row 2 and scores **1**; blue goes to row 4 and scores **1**. He puts 1 red and 3 blue tiles in the box lid. His lines 3 and 5 are not complete and stay as they are.

---

## 8. The Floor Line (Penalties)

At the end of phase B, each player loses points for every item on their floor line. Each item loses the number printed above its space. The starting player marker counts as an item.

| Items on the floor line | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| Points lost in total | 1 | 2 | 4 | 6 | 8 | 11 | 14 |

- Your score **can never go below 0**. If a penalty would take you below 0, stop at 0.
- Then put every tile from your floor line in the **box lid**.
- If the starting player marker is on your floor line, keep it in front of you instead of putting it in the lid. You are the starting player of the next round.

**Example:** Peter has 4 tiles and the starting player marker on his floor line (5 items). He loses 1 + 1 + 2 + 2 + 2 = **8 points**.

---

## 9. Phase C: Preparing the Next Round

If nobody has completed a horizontal row of their wall, play another round:

1. The player who has the starting player marker draws tiles from the bag and puts **exactly 4 tiles** on each factory display again.
2. **If the bag runs empty** while filling, put **all tiles from the box lid** into the bag, mix them, and keep filling.
3. In the rare case that the bag **and** the box lid are both empty, stop. Start the new round anyway, even if some factory displays have fewer than 4 tiles or none.

The new round begins with phase A. The player with the starting player marker puts it in the centre and takes the first turn.

The box lid is only emptied into the bag when the bag runs out during filling, never at any other time.

---

## 10. End of the Game

The game ends **after phase B of the round** in which at least one player has completed at least one **horizontal row** on their wall (5 tiles across). Finish that whole round's phase B for all players first, including floor line penalties. Then do not play phase C. A full **column** does not end the game.

### End bonuses

Each player now scores extra points for their wall:

| Each … | Bonus |
|---|---|
| complete horizontal **row** (5 tiles across) | **+2** points |
| complete vertical **column** (5 tiles down) | **+7** points |
| **colour** with all 5 of its tiles on your wall | **+10** points |

**Example:** at the end, Ana's wall has 1 complete row, 2 complete columns, and all 5 blue tiles. Her bonus is 2 + 7 + 7 + 10 = **26 points**.

### Winner and tie-break

The player with the **most points** wins.

**Tie:** if players are tied for the most points, the tied player with **more complete horizontal rows** on their wall wins. If they are still tied, they **share the victory**.

---

## 11. Variant: The Grey Wall

If you like, all players can play on the **grey side** of their player boards. On the grey side, the wall spaces have no colours. Remember: all players use the same side.

The rules are exactly the same as the normal game, except for these points:

- **Free choice of space.** In phase B, when you move a tile from a complete pattern line to your wall, you may put it on **any empty space** in the wall row beside that line.
- **Column rule.** Each colour may appear **only once in each column** of your wall. (Each colour already may appear only once in each row; that rule is unchanged.)
- **Special case.** Sometimes there is no allowed space for the tile in its row, because every empty space of the row is in a column that already has that colour. Then you must put **all** tiles of that pattern line on your floor line. Floor line rules apply as normal: tiles beyond the 7th space go to the box lid.

Scoring, floor penalties, the end of the game, bonuses and the tie-break are unchanged. The colour bonus (+10) counts tiles of that colour anywhere on your wall.

---

## 12. FAQ

**Can I put only some of my tiles in a pattern line and choose to drop the rest on the floor?**
The rules say all the tiles you take go into one pattern line, and only the extra tiles that don't fit go to the floor line. You may also put the whole group on the floor line. This manual (and the engine) reads it as: the chosen line is filled as far as it can be, and only the remainder goes to the floor.

**Can I choose the floor line even when a pattern line could take the tiles?**
Yes. The rulebook shows putting tiles straight onto the floor line as an allowed choice.

**Can I take tiles from the centre if it holds only the starting player marker?**
No. You must take tiles. The marker alone is not a choice. It is only taken together with tiles.

**What if my floor line is already full when I take the starting player marker?**
The rules don't cover this. *House rule:* keep the marker beside your board. You don't lose extra points for it, but you are still the starting player of the next round.

**What if nobody takes tiles from the centre all round?**
This is very rare (every factory display would need to hold 4 tiles of a single colour). The rules don't cover it. *House rule:* the same starting player starts the next round.

**My score goes past 100. What now?**
The score track ends at 100. The rules don't say what to do. *House rule:* keep going round the track and remember (or note) that you have passed 100.

**Does a pattern line keep its tiles if it isn't complete?**
Yes. Unfinished pattern lines keep their tiles into the next round. You can add more of the same colour later.

**Can I change the colour of a pattern line that has tiles?**
No. A line keeps its colour until it is complete and emptied in phase B.

**Do tiles I put on the wall in the same phase count for later tiles?**
Yes. Tiles are placed from the top line down. A tile already placed this phase counts as a neighbour for the tiles placed after it.

**What is the most I can lose on the floor line in one round?**
14 points: all 7 spaces filled. Extra tiles go to the box lid without costing more.

**Can my score drop below 0?**
No. It stops at 0.

**Does a full column end the game?**
No. Only a full horizontal row ends the game, at the end of that round's phase B.

**When does the bag get refilled?**
Only while filling factory displays in phase C (or setup), at the moment the bag runs empty. Then all tiles from the box lid go back into the bag.

**On the grey wall, may I take tiles into a pattern line whose colour has no space left in that row?**
Yes. The rules only forbid a colour that is already in that wall row. But if the line is complete in phase B and there is no allowed space, all of its tiles go to your floor line.

### Glossary: German rulebook → this manual

| German | English (this manual) |
|---|---|
| Fliese | tile |
| Beutel | bag |
| Manufakturplättchen | factory display |
| Tischmitte | centre of the table |
| Spielerablage | player board |
| Punktemarker | score marker |
| Punkteleiste | score track |
| Musterreihen | pattern lines |
| Wand | wall |
| Bodenreihe | floor line |
| Startspielermarker | starting player marker |
| (Schachtel-)Deckel | box lid |
| Musterphase | factory offer (phase A; literally "pattern phase") |
| Fliesungsphase | wall-tiling (phase B) |
| Vorbereiten der nächsten Runde | preparing the next round (phase C) |
| Wertung | scoring |
| Spielende | end of the game |
| Variante | variant |

---

## 13. Beginner Tips

*These are our own suggestions, **not rules**.*

- **Complete lines before the round ends.** An unfinished pattern line scores nothing this round. Start with the short lines (1, 2 and 3); they are easy to finish.
- **Count before you take.** Before taking 4 tiles of a colour, check which of your lines has room for 4. Extra tiles fall to the floor and cost points.
- **The floor line hurts fast.** The first two items cost 1 each, but the 6th and 7th cost 3 each.
- **Build next to your own tiles.** A tile that touches others scores more. Placing tiles in a cross (across and down) scores both counts.
- **The starting player marker has a price.** It costs at least 1 point, but going first next round lets you pick the best tiles. Sometimes that is worth it.
- **Watch what you leave in the centre.** Tiles pushed to the centre pile up. Late in the round, someone may be forced to take a big pile they can't use.
- **Watch your opponents' boards.** If someone needs exactly 3 red for their line 3, taking the red first can block them.
- **Bonuses are big.** A full column (+7) and a full colour (+10) are worth more than a full row (+2). Plan for them before someone ends the game.
- **Don't rush the end if you're behind.** Completing the first full row ends the game after that round.

---

*Azul is a trademark of Plan B Games / Next Move Games. This manual is an unofficial player aid written for personal use. It does not reproduce the rulebook's text or artwork.*
