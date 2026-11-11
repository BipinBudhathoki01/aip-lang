# Build with us

AIP Lang is an early open-source project. Useful contributions include documentation, minimal bug reproductions, parser diagnostics, tests for generated code, and practical application examples.

Read [CONTRIBUTING.md](https://github.com/BipinBudhathoki01/aip-lang/blob/main/CONTRIBUTING.md), browse [open issues](https://github.com/BipinBudhathoki01/aip-lang/issues), and check the [roadmap](https://github.com/BipinBudhathoki01/aip-lang/blob/main/ROADMAP.md).

## Contribution flow

1. Fork and clone the repository.
2. Create a focused branch.
3. Install Python and Node dependencies using the quick start.
4. Make the change and run relevant checks.
5. Open a pull request describing the problem, behavior, and validation.

No API key is required to run tests. Maintainers review and merge pull requests.

```bash
python -m unittest discover -s tests -v
npm test
npm run lint
npm run build
```

For local documentation preview, install `requirements-docs.txt` and run `python -m mkdocs serve`. CI builds documentation with `--strict` and publishes it to GitHub Pages together with the static playground.

## Design

The playground uses Meta's MIT-licensed [Astryx](https://github.com/meta/astryx) design system with its neutral theme. The project is independent of Meta. Keep screens focused on reading prompts, inspecting their structure, and understanding results. Use accessible labels, visible focus states, and responsive layouts.
