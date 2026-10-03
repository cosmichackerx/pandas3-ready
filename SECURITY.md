# Security

pandas3-ready only reads `.py` and `.ipynb` files under the directory you give it and writes a report to stdout or the file you name. It has no runtime dependencies, never imports or executes the code it scans (it parses it with `ast`), and makes no network request, except the optional sticky pull request comment of the GitHub Action (GitHub API, only when you turn `comment` on).

The oracle in `tests/oracle/` installs pandas and lxml from PyPI in CI and runs small programs written in this repository.

Found a vulnerability (for example a crafted file that makes the parser hang or consume memory)? Please use GitHub's private vulnerability reporting for this repository ("Security" tab, "Report a vulnerability") instead of a public issue.
