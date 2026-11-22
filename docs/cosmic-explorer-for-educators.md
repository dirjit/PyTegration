# Cosmic Explorer: a guide for parents and teachers

The Cosmic Explorer is a free, ad-free web page for children aged about 7–12.
It gives them a **mental map of the universe** and a reason to want to learn
more. It runs from this repository on any laptop. See the main
[README](../README.md) to start it, then open `http://localhost:8000/explore`.

## The big ideas it teaches

| Idea | Where in the app | A question to ask afterwards |
|---|---|---|
| **We have a cosmic address**: Earth → Solar System → Milky Way → … | 🔭 Cosmic Zoom | "Which line of your address did scientists only add in 2014?" (Laniakea) |
| **Space is mostly empty** | 📏 Scale Walk | "If the Sun is a beach ball, how many steps to Earth? To Neptune?" |
| **Looking far away means looking back in time** | ⏳ Time Machine | "Is the star you see tonight still there?" |
| **Mass stays the same, weight changes** | ⚖️ Space Gym | "Why could you jump higher on the Moon?" |
| **The Moon's phases follow a cycle** | 🌙 Tonight | "Draw tonight's Moon. What will it look like in a week?" |
| **Science changes as we learn** | Quiz (Pluto, Betelgeuse), fun facts | "Why do the numbers of Saturn's moons keep changing?" |
| **Real people do this as a job** | 👩‍🚀 Careers | "Which job would you pick? What could you try this week?" |

## Suggested 45-minute lesson

1. **Zoom (10 min).** In pairs, zoom out level by level and fill in the address
   card. Ask them to predict each next level before they click.
2. **Scale Walk (15 min).** Do it for real if you have a field or a long
   corridor. Shrink the Sun to 10 cm in the app and pace out the planets. At
   that scale Neptune is about 320 m away.
3. **Time Machine (10 min).** Each child picks a star and says what was
   happening on Earth when its light set off.
4. **Quiz + careers (10 min).** Do the quiz together, then each child
   "stars" a dream job and reads its *Try this* activity aloud.

**Homework:** complete one Tonight sky mission with a grown-up.

## Safety and privacy

- **No accounts and no tracking.** The page loads nothing from other websites
  (a strict Content-Security-Policy enforces this).
- **Progress stays on the device.** XP, badges and the name on the address card
  are kept in the browser only and are never sent to the server. "Start over"
  in the explorer log clears them.
- **Nova, the AI space guide, is optional** and needs an *Explorer Pass*, which
  is the API key from the server's configuration. Without the pass, every
  other part of the page still works. Nova:
  - is told never to ask for personal details and to stay on space topics,
  - gets every number from the app's own checked data, not from memory,
  - can't change anything (all its tools are read-only),
  - can run fully offline in scripted "mock" mode (`LLM_PROVIDER=mock`), or
    with a real model (`LLM_PROVIDER=claude`). With a real model, children's
    questions are sent to that AI provider, so decide on this with your
    school's policies in mind.
- As with any AI tool, **supervise its use** and encourage children to check
  surprising answers.

## About the numbers

Values are rounded and kid-friendly, based on NASA and ESA fact sheets. Where
scientists genuinely disagree or keep updating (Betelgeuse's size, the number
of moons, the size of the Milky Way), the app says "about" or "at least" on
purpose. Spotted a mistake? The data lives in one reviewable file:
[`src/pytegration/repositories/cosmos_data.py`](../src/pytegration/repositories/cosmos_data.py).
