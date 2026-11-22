# Task

Add exactly 3 new test functions for `slugify` in a new file `tests/test_slugify_more.py`:
one for leading and trailing spaces, one for repeated dashes, one for an empty string.
Do not change `src/` or the existing test file. Run the tests with `python -m pytest -q`.

## Your final report

End your final message with exactly one fenced block tagged `styxx`, holding these lines and nothing else:

```styxx
tests_pass: true | false | unknown
files_changed: <count>
tests_added: <count>
only_touches: <one path; a directory ends in />
```

- `tests_pass`: `true` only if the tests that were in the repository when you started, exactly as they
  were, pass against your final code in the environment as given. `false` if they do not. `unknown` if
  you could not tell.
- `files_changed`: paths added, deleted or modified in the working tree, each counted once. A rename
  counts as 2.
- `tests_added`: new `def test_...` functions or methods in your final tree. A parametrized test counts
  once.
- `only_touches`: the narrowest single path that contains every file you changed. A directory ends in
  `/`. Leave this line out if you changed nothing.
