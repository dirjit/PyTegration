# Galaxy System Explorer

A single-file, zero-build 3D explorer that zooms from the Local Group down to individual
moons. Open `index.html` in a browser (it loads Three.js r128 from cdnjs).

## Scales

| Tab | What you see |
| --- | --- |
| Local Group | The Milky Way, Andromeda, Triangulum and 14 satellite and dwarf galaxies, placed from RA/Dec and distance |
| Milky Way | A schematic spiral (four arms, central bar, bulge, halo, dust) with the Sun, Sagittarius A\* and nine landmarks placed from real galactic coordinates |
| Neighborhood | 37 stars within about 43 light-years at their real positions, with height stems and distance rings |
| System | A live Keplerian orrery for any star above: the Solar System (8 planets, Ceres, Pluto, Eris, 26 moons, asteroid and Kuiper belts) plus binaries and exoplanet systems such as TRAPPIST-1, 55 Cancri and Tau Ceti |

## Controls

- Drag to orbit, pinch or scroll to zoom, right-drag or shift-drag to pan.
- Tap an object to select it and fly to it. The info card has the next step, such as **Enter system**.
- Search (magnifier) jumps to any planet, moon, star or galaxy from any scale.
- In System view the time bar sets speed from hours per second to centuries per second, reverses time, and **Today** snaps the Solar System to today's real planet positions.
- Display options: orbit lines, labels, moons, belts, habitable zone, true-scale sizes, galaxy rotation, distance grid, background stars.

## Data and accuracy

- Planet and Pluto orbits use the JPL "approximate positions" Keplerian elements (J2000). Moon orbits are circular.
- Exoplanet sizes marked *est.* are estimated from mass; surface textures for exoplanets are illustrative only. Unconfirmed planets are tagged *Candidate*.
- Body sizes are exaggerated by default so planets are visible. Turn on **True-scale sizes** for real sizes against real distances.
- The galaxy view is a model drawn from published structure, not a survey map.
