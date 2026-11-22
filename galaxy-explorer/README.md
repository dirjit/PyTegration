# Galaxy System Explorer

A single-file, zero-build 3D explorer that zooms from the Local Group down to the surface of a moon,
rendered as a photograph: HDR lighting, analytic shadows, atmospheric scattering and a virtual camera.
Open `index.html` in a browser (it loads Three.js r128 from cdnjs; everything else is inline).

## Scales

| Tab | What you see |
| --- | --- |
| Local Group | The Milky Way, Andromeda, Triangulum and 14 satellite and dwarf galaxies, placed from RA/Dec and distance |
| Milky Way | A schematic spiral (four arms, bar, bulge, halo, dust) with the Sun, Sagittarius A\* and nine landmarks at real galactic coordinates |
| Neighborhood | 37 stars within about 43 light-years at their real positions, against a sky of ~100 named bright stars |
| System | A live orrery for any of those stars: the Solar System (8 planets, Ceres, Pluto, Eris, 22 moons, belts), binaries and exoplanet systems |

## Rendering

- **Orbits.** Keplerian elements from JPL for the planets and Pluto. The Moon uses its mean elements plus the six largest periodic terms
  (Meeus ch. 47); Jupiter's four large moons use their mean longitudes. "Today" puts everything where it is now.
- **Orientation.** Each globe is oriented from its IAU pole and prime-meridian rate, so Earth's day side, Saturn's ring tilt and
  Uranus's sideways spin match the real sky for the date shown. Tidally locked moons keep one face to their planet.
- **Surfaces.** Baked on the GPU into equirectangular textures (up to 2048 px): Earth from real coastlines, mountain ranges and
  climate bands, with clouds, ocean glint and city lights on the night side; the Moon with its real maria and rayed craters;
  Mars with Tharsis, Valles Marineris, Hellas and its polar caps; Jupiter's belts and Great Red Spot; Saturn's polar hexagon;
  Io, Europa, Iapetus, Pluto's heart and more. Exoplanet surfaces are illustrative and chosen from size and temperature.
- **Analytic shadows.** Every shadow is computed per pixel from the overlap of the star's disk and the occluder's disk, which
  gives true umbra and penumbra: moon shadows on planets, planet shadows on moons and rings, ring shadows on Saturn and Uranus.
  Light bent through Earth's atmosphere turns an eclipsed Moon red.
- **Atmospheres.** Single-scattering Rayleigh and Mie, ray-marched per pixel with physical coefficients
  (Earth blue, Mars butterscotch, Venus and Titan haze, ice-giant limbs, Pluto's thin blue haze), also shadowed by eclipses.
- **Light.** Irradiance falls off as 1/r² from each star, coloured by its temperature. An HDR pipeline with auto exposure,
  bloom, diffraction-spike streaks, ACES tone mapping, vignette and sensor grain turns it into an image.

## Camera, director and darkroom

- **Camera:** Eye, Telescope (long lens, spikes) and Deep space (long exposure of stars and the Milky Way), with focal length,
  exposure, glow, grain and palettes: natural, Hubble SHO narrowband, JWST infrared, thermal, monochrome CCD.
- **Shot director:** nine preset shots composed by the explorer itself (Io's shadow on Jupiter, Saturn backlit, Earth at night,
  a solar eclipse seen from space, a blood Moon, crescent Venus, the galactic core, TRAPPIST-1, Uranus). The eclipse finder
  searches the orbits for the next alignment; at true scale its dates match real eclipses to about an hour.
- **Claude:** when the page runs as a claude.ai artifact, you can describe a shot in words. Claude drives the same tools
  (go to, frame, set time, find event, optics, display, capture) and writes the caption. In the darkroom, Claude can look at a
  captured frame, critique it and suggest adjustments that re-shoot it in one click. Saving a PNG uses the artifact download
  prompt. Outside claude.ai these features hide and the presets still work.

## Controls

Drag to orbit, pinch or scroll to zoom, right-drag or shift-drag to pan, tap to select. Search jumps to any object.
The time bar runs from minutes to centuries per second and can reverse.

## Accuracy notes

- Bodies are enlarged by default so they are visible; turn on **True-scale sizes** for real sizes, and real eclipse geometry.
- The Moon is good to a few tenths of a degree; Galilean moon phases are approximate; other moons' phases are illustrative.
- The galaxy view is a model drawn from published structure, not a survey map.
