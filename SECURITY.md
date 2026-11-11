# Security policy

AIP Lang is an early preview. There are no long-term support branches; security fixes target the latest main branch.

Do not report exploitable vulnerabilities or credentials in public issues. Use the repository's private vulnerability reporting feature if available, or the maintainer's private contact options at https://github.com/BipinBudhathoki01. If unavailable, use GitHub's reporting tools without disclosing exploit details publicly. No response-time guarantee is currently offered.

Include affected versions, reproduction steps, potential impact, and a minimal example without real secrets.

Treat prompts as source code you review before compilation. Generated code makes external API calls. Output validation does not prevent prompt injection or establish factual accuracy. The local playground binds to localhost and is not intended as a public multi-user execution service.
