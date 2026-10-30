"""Pure analytics core.

Rules for this package:
  * no I/O, no database, no web imports: data goes in as plain objects, results come out;
  * every function that selects or derives something "known at decision time" documents
    which information it is allowed to use, and has a leakage test proving it.
"""