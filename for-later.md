
- create_deferred_session() is iffy because the returned value is overly, weirdly complected with the original value. Can we do something better? I think .create_deferred_session() should return an object with a reference to the original http cache, but where cache writes are stored in-memory only. Then there should be a .commit_to(other: HttpCache) method which commits. during a deferred session, the deferred and original sessions should be almost entirely independent, with the exception that they both point to the same on-disk cache. Hence, reads and writes from the original session will appear in the deferred session. Also, I guess it should be called .create_write_deferred_session()

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

