# State consistency profiles (offline)

Three new *deterministic* research profiles: implicit stale read, delayed replica, concurrent optimistic version update.

They are offline research prototypes and are **not** yet exposed via the main paid model runner. Reference success and a stale-replica mutant are checked for seeds 0–19.

Run `python -m unittest discover -s tests -v`. No API requests are made. Never infer real-world model difficulty from these tests alone.
