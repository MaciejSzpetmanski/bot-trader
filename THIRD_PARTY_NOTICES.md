# Third-Party Notices

This project depends on third-party Python packages listed in `requirements.txt`.
The packages are installed from the Python package index or your configured package source; they are not vendored in this repository.

This file is a convenience summary, not a substitute for checking the exact versions installed in your environment.
Before redistributing this project, a Docker image, or a bundled executable, regenerate the notices from the installed environment.

```bash
pip install pip-licenses
pip-licenses --format=markdown --with-urls --with-license-file > THIRD_PARTY_NOTICES.generated.md
```

## Direct dependencies

| Package | Purpose | Common license family |
| --- | --- | --- |
| `alpaca-py` | Alpaca broker/data SDK | Apache-2.0; verify installed version |
| `pandas` | tabular data processing | BSD-3-Clause |
| `numpy` | numerical computing | BSD-3-Clause |
| `python-dotenv` | `.env` loading | BSD-3-Clause |
| `vaderSentiment` | sentiment scoring | MIT; verify installed version |
| `feedparser` | RSS/Atom parsing | BSD-style; verify installed version |
| `requests` | HTTP client | Apache-2.0 |
| `tenacity` | retries/backoff | Apache-2.0 |
| `pytest` | tests | MIT; verify installed version |
| `tweepy` | optional X/Twitter API client | MIT; verify installed version |

## Notes

- Dependency licenses can change between versions.
- Transitive dependencies may add additional obligations.
- If you distribute a container image or binary, include generated notices for the exact resolved dependency set.
- If your organization has a formal open-source policy, run its approved SCA/license scanner before distribution.
