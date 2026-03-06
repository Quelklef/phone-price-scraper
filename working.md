
- Readme changes:

  - Remove "Example known-good query"
  - Update CLI flags
  - Update sec 1 to make clear that the listed models and storages are just the default ranges, and that other ranges can be selected in the CLI
  - Recommend over-HTTP `nix run` first, and then local `nix run`, and then devshell for development only. Show flags with the over-HTTP `nix run` call example.
  - Add sample output by running `run-app -o` and turning the output CSV into an abbreviated markdown table. Include these rows: model, storage, condition, seller, minimum price (link to listing)
  - Add a new "Gotchas" section and note that multi-variant listings (eg, "Pixel 7 / 7 Pro 128GB") are excluded for the sake of simplicity.

  Add a note in AGENTS.md to keep the README up-to-date when code changes are amde.

- For the post-table price mismatch warning,
  - Show immediately after the "Price is verified ..." logline.
  - Show "scraper" instead of "scrapers" if it's just one

- Add tests to timing.py.

  This will require adding a new 'perf_time' dep with two implementations. The first is the real one with a 'get_time()' function that delegates to 'time.perf_counter()'. The second is a mock version with 'set_time()' and 'get_time().

  Then, add the following tests, using the mock perf time dep:

  1. For no data, _STATS has correct totals
  2. For a single recorded stage, _STATS has correct totals
  3. For multiple stages, some repeated, some overlapping/nested with others, _STATS has correct toals
  4. render_summary() returns something other than whitespace for no data
  5. render_summary() contains all the totals from _STATS (property test)
  6. _prune_redundant_rows() removes exactly those rows with duplicate paths (propery test)

- Repeatedly do the following until there is no more to do:

  - Find something that can be simplified, and make it simpler
  - Find something that should be factored out, and do so
  - Find something that should be made more readable/clear, and do so
  - Find something that deserves a comment, and give it one
  - Find something that can be optimized without architectural changes, and do it

  Then, verify we still have no mismatches and commit.
